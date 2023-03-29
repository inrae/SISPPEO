# -*- coding: utf-8 -*-
# Copyright 2022 Arthur Coqué, Pierre Manchon, Pôle OFB-INRAE ECLA, UR RECOVER
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""This module contains a reader for L8_USGS_L1C1 products with tif files.

    Typical usage example:

    reader = L8USGSL1C1Reader(**config)
    reader.extract_bands()
    reader.create_ds()
"""
import io
import tarfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List

import numpy as np
import rasterio
import xarray as xr
from pyproj import CRS
from rasterio.windows import Window
from tqdm import tqdm

from sisppeo.readers.reader import Reader
from sisppeo.utils.naming import names_dict_l8l1c1
from sisppeo.utils.readers import (_digital_number_to_reflectance,
                                   _extract_rad_coefs, get_ij_bbox)


class L8USGSL1C1Reader(Reader):
    """A reader dedicated to extract data from L8_USGS_L1C1 products.

    Attributes:
        dataset: A dataset containing extracted data.
    """
    def __init__(self, input_product: Path, requested_bands: List[str], **_ignored):
        super().__init__(input_product=input_product, requested_bands=requested_bands,
                         names_dict=names_dict_l8l1c1, **_ignored)

    def extract_bands(self) -> None:
        """See base class."""
        # Check if data are compressed
        compressed = False
        if self._inputs.input_product.suffix in ('.tgz', '.gz'):
            compressed = True

        # Load metadata
        metadata = self._load_metadata_from_MTL(compressed)

        # Filter bands
        if compressed:
            root_path = f'tar://{str(self._inputs.input_product.resolve())}!/'
            with tarfile.open(self._inputs.input_product) as archive:
                requested_bands = [
                    (root_path + [_ for _ in archive.getnames() if _.endswith(f'_{band}.TIF')][0], band)
                    for band in self._inputs.requested_bands
                ]
        else:
            requested_bands = [
                (list(self._inputs.input_product.glob(f'*_{band}.TIF'))[0],
                 band) for band in self._inputs.requested_bands
            ]

        # Extract data
        data = {}
        for path, band in tqdm(requested_bands, unit='bands'):
            # If the band is the quality band (used for masks), don't transform the DNs in surface reflectance
            _bqa = False
            if band == 'BQA':
                _bqa = True
            with rasterio.open(path) as subdataset:
                if self._intermediate_data['x'] is None:    # 1st extracted band
                    # Store the CRS
                    self._intermediate_data['crs'] = CRS.from_epsg(
                        # pylint: disable=no-member
                        # False positive.
                        subdataset.crs.to_epsg()
                    )
                    band_array, xy_bbox = self._extract_first_band(subdataset, metadata, band, _bqa)
                else:   # other extracted bands
                    band_array = _extract_nth_band(subdataset, metadata, band, _bqa, xy_bbox)
                data[band] = band_array.reshape(1, *band_array.shape)
        print('')

        # Store outputs
        self._intermediate_data['data'] = data
        self._intermediate_data['metadata'] = metadata

    def create_ds(self) -> None:
        """See base class."""
        # Create the dataset
        ds = xr.Dataset(
            {key: (['time', 'y', 'x'], val) for key, val in self._intermediate_data['data'].items()},
            coords={'x': ('x', self._intermediate_data['x']),
                    'y': ('y', self._intermediate_data['y']),
                    'time': [datetime.fromisoformat(
                        self._intermediate_data['metadata']['MTL']['PRODUCT_METADATA']['DATE_ACQUIRED'] + 'T' +
                        self._intermediate_data['metadata']['MTL']['PRODUCT_METADATA']['SCENE_CENTER_TIME'][:-2])]
                    }
        )
        crs = self._intermediate_data['crs']
        # Set up coordinate variables
        ds.x.attrs['axis'] = 'X'
        ds.x.attrs['long_name'] = f'x-coordinate ({crs.name})'
        ds.x.attrs['standard_name'] = "projection_x_coordinate"
        ds.x.attrs['units'] = 'm'
        ds.y.attrs['axis'] = 'Y'
        ds.y.attrs['long_name'] = f'y-coordinate ({crs.name})'
        ds.y.attrs['standard_name'] = "projection_y_coordinate"
        ds.y.attrs['units'] = 'm'
        ds.time.attrs['axis'] = 'T'
        ds.time.attrs['long_name'] = 'time'

        # Set up the 'grid mapping variable'
        ds['crs'] = xr.DataArray(name='crs', attrs=crs.to_cf())

        # Store metadata
        ds['product_metadata'] = xr.DataArray()
        for key, val in {f'{key1}:{key2}': val for key1
                         in self._intermediate_data['metadata']['tags'] for key2, val
                         in self._intermediate_data['metadata']['tags'][key1].items()}.items():
            ds.product_metadata.attrs[key] = val

        ds.attrs['data_type'] = 'rho'
        self.dataset = ds

    # pylint: disable=invalid-name
    # MTL is the name given by the USGS to the file containing metadata.
    def _load_metadata_from_MTL(self, compressed):
        if compressed:
            with tarfile.open(self._inputs.input_product) as archive:
                path = [_ for _ in archive.getnames()
                        if _.endswith('MTL.txt')][0]
                with io.TextIOWrapper(archive.extractfile(path)) as f:
                    lines = f.readlines()
        else:
            path = list(self._inputs.input_product.glob('*MTL.txt'))[0]
            with open(path) as f:
                lines = f.readlines()
        metadata = defaultdict(dict)
        key = None
        for line in lines[1:-2]:
            line = line.lstrip(' ').rstrip('\n').replace('"', '').split(' = ')
            if line[0] == 'GROUP':
                metadata['MTL'][line[1]] = {}
                key = line[1]
            elif line[0] == 'END_GROUP':
                continue
            else:
                metadata['MTL'][key][line[0]] = line[1]
        return metadata

    def _compute_x_coords(self, x0, x1):
        x_start = x0 + 15
        x_stop = x1 - 15
        self._intermediate_data['x'] = np.arange(x_start, x_stop + 1, 30)

    def _compute_y_coords(self, y0, y1):
        y_start = y0 - 15
        y_stop = y1 + 15
        self._intermediate_data['y'] = np.arange(y_start, y_stop - 1, -30)

    # pylint: disable=too-many-locals
    # More readable when creating an 'out_res' alias.
    def _extract_first_band(self, subdataset, metadata, band, btype):
        if self._inputs.ROI is not None:
            self._reproject_geom()
            row_start, col_start, row_stop, col_stop = get_ij_bbox(subdataset, self._intermediate_data['geom'])
            arr = subdataset.read(1, window=Window.from_slices((row_start, row_stop + 1), (col_start, col_stop + 1)))
            # Update internal coords
            x0, y0 = subdataset.transform * (col_start, row_start)
            x1, y1 = subdataset.transform * (col_stop + 1, row_stop + 1)
        else:
            arr = subdataset.read(1)
            # Update internal coords
            x0, y0 = subdataset.transform * (0, 0)
            x1, y1 = subdataset.transform * (subdataset.width, subdataset.height)
        if btype:
            band_array = arr
        else:
            rad_coefs = _extract_rad_coefs(metadata['MTL'], band)
            # Turn DNs into TOA reflectances
            # If it is BQA, extract nth band, if it is not do so but turn dn into toa in the process
            band_array = _digital_number_to_reflectance(arr, *rad_coefs)
        # Compute projected coordinates
        self._compute_x_coords(x0, x1)
        self._compute_y_coords(y0, y1)
        # Update internal coords
        x1 -= 1
        y1 += 1
        return band_array, [x0, y0, x1, y1]


def _extract_nth_band(subdataset, metadata, band, btype, xy_bbox):
    x0, y0, x1, y1 = xy_bbox
    row_start, col_start = subdataset.index(x0, y0)
    row_stop, col_stop = subdataset.index(x1, y1)
    arr = subdataset.read(1, window=Window.from_slices((row_start, row_stop + 1), (col_start, col_stop + 1)))
    if btype:
        band_array = arr
    else:
        rad_coefs = _extract_rad_coefs(metadata['MTL'], band)
        # Turn DNs into TOA reflectances
        # If it is BQA, extract nth band, if it is not do so but turn dn into toa in the process
        band_array = _digital_number_to_reflectance(arr, *rad_coefs)
    return band_array
