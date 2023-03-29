# -*- coding: utf-8 -*-
# Copyright 2020 Arthur Coqué, Pôle OFB-INRAE ECLA, UR RECOVER
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
"""This module contains a reader for L8_USGS_L2C1 products with hdf files.

    Typical usage example:

    reader = L8USGSL2C1HDFReader(**config)
    reader.extract_bands()
    reader.create_ds()
    extracted_dataset = reader.dataset
"""
import io
import os
import shutil
import tarfile
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List

import numpy as np
import rasterio
import rasterio.features
import rioxarray
import xarray as xr
from pyproj import CRS
from rasterio.windows import Window
from tqdm import tqdm

from sisppeo.readers.reader import Reader
from sisppeo.utils.naming import names_dict_ll2
from sisppeo.utils.readers import (_digital_number_to_reflectance,
                                   _extract_rad_coefs, decode_data,
                                   get_ij_bbox, get_ij_bbox_from_ds)


class LXUSGSL2Reader(Reader):
    """A reader dedicated to extract data from L8_USGS_L2C1 products (.hdf).

    Attributes:
        dataset: A dataset containing extracted data.
    """
    def __init__(self, input_product: Path, requested_bands: List[str], **_ignored):
        super().__init__(input_product=input_product, requested_bands=requested_bands,
                         names_dict=names_dict_ll2, **_ignored)

    def extract_bands(self) -> None:
        """See base class."""
        # Load data
        self.tmp = None
        compressed = False
        hdf_path = None
        if self._inputs.input_product.suffix == '.gz':   # .tar.gz
            compressed = True
            self.tmp = tempfile.mkdtemp(prefix='SISPPEO')
            with tarfile.open(self._inputs.input_product) as tar:
                for file in tar.getnames():
                    if file.endswith('.hdf'):
                        hdf_path = file
                        tar.extract(file, self.tmp)
            if hdf_path:
                with tarfile.open(self._inputs.input_product) as tar:
                    for file in tar.getnames():
                        for b in self._inputs.requested_bands:
                            if b in file:
                                tar.extract(file, self.tmp)
                # extracted files still opened here
                ds = rioxarray.open_rasterio(os.path.join(self.tmp, os.path.basename(hdf_path)))
            else:
                ds = None
        else:
            with rasterio.Env(RAW_CHECK_FILE_SIZE=False):
                ds = rioxarray.open_rasterio(self._inputs.input_product)

        # BYPASS
        if ds:
            # Delete and rename field names
            ds = ds.squeeze('band')
            ds = ds.rename({'spatial_ref': 'crs'})
            available_bands = ds.data_vars

            # Extract data
            for band in available_bands:
                if band not in self._inputs.requested_bands:
                    ds = ds.drop(band)
                else:
                    if band != 'pixel_qa':
                        # Apply corrections
                        ds[band].values = decode_data(ds[band].values, ds[band].attrs['scale_factor'],
                                                      ds[band].attrs['_FillValue'],
                                                      ds[band].attrs['add_offset'])
                        # Reset values
                        ds[band].attrs.pop('_FillValue')
                        ds[band].attrs['scale_factor'] = 1
                        ds[band].attrs['add_offset'] = 0

            # Add time dimension and CRS informations
            ds = ds.expand_dims(time=[np.datetime64(ds.attrs['AcquisitionDate'])])
            proj, _, zone = CRS.from_wkt(ds.crs.crs_wkt).coordinate_operation.name.split(' ')
            if zone[:-1] == 'S':
                epsg = CRS.from_proj4(f'+proj={proj.lower()} +zone={zone[:-1]} +south').to_epsg()
            else:
                epsg = CRS.from_proj4(f'+proj={proj.lower()} +zone={zone[:-1]}').to_epsg()
            crs = CRS.from_epsg(epsg)

            ds['crs'] = xr.DataArray(name='crs', attrs=crs.to_cf())
            self._intermediate_data['crs'] = crs

            # Fit data to geom's bbox if given
            if self._inputs.ROI is not None:
                ds = ds.rio.write_crs(epsg)
                self._reproject_geom()  # Has a side effect to store the geom inside of intermediate_data['geom']
                # bounds: bottom left/top right coords: x/y: width:height
                row_start, row_stop, col_start, col_stop = get_ij_bbox_from_ds(ds, self._intermediate_data['geom'])
                ds = ds.sel(y=slice(col_start, col_stop), x=slice(row_start, row_stop))

            # Store outputs
            self._intermediate_data['data'] = ds
            self._intermediate_data['metadata'] = self._load_metadata_from_MTL(compressed)
        else:
            # Load metadata
            metadata = self._load_metadata_from_MTL(compressed)
            # Filter bands
            if compressed:
                root_path = f'tar://{str(self._inputs.input_product.resolve())}!/'
                with tarfile.open(self._inputs.input_product) as archive:
                    requested_bands = [
                        (root_path + [_ for _ in archive.getnames() if _.endswith(f'_{band}.tif')][0], band)
                        for band in self._inputs.requested_bands
                    ]
            else:
                requested_bands = [
                    (list(self._inputs.input_product.glob(f'*_{band}.tif'))[0],
                     band) for band in self._inputs.requested_bands
                ]

            # Extract data
            data = {}
            for path, band in tqdm(requested_bands, unit='bands'):
                # # If the band is the quality band (used for masks), don't transform the DNs in surface reflectance
                # _bqa = False
                # if band == 'BQA':
                #     _bqa = True
                btype=True
                with rasterio.open(path) as subdataset:
                    if self._intermediate_data['x'] is None:  # 1st extracted band
                        # Store the CRS
                        self._intermediate_data['crs'] = CRS.from_epsg(
                            # pylint: disable=no-member
                            # False positive.
                            subdataset.crs.to_epsg()
                        )
                        band_array, xy_bbox = self._extract_first_band(subdataset, metadata, band, btype)
                    else:  # other extracted bands
                        band_array = _extract_nth_band(subdataset, metadata, band, btype, xy_bbox)
                    data[band] = band_array.reshape(1, *band_array.shape)
            print('')

            # Store outputs
            self._intermediate_data['data'] = data
            self._intermediate_data['metadata'] = metadata

        # Supression du temp
        shutil.rmtree(self.tmp)

    def create_ds(self) -> None:
        """See base class."""
        if type(self._intermediate_data['data']).__name__ == 'Dataset':
            # Create the dataset
            ds = self._intermediate_data['data']
            crs = self._intermediate_data['crs']
            # Set up coordinate variables
            ds.x.attrs['axis'] = 'X'
            ds.x.attrs['long_name'] = f'x-coordinate ({crs.name})'
            ds.x.attrs['standard_name'] = 'projection_x_coordinate'
            ds.x.attrs['units'] = 'm'
            ds.y.attrs['axis'] = 'Y'
            ds.y.attrs['long_name'] = f'y-coordinate ({crs.name})'
            ds.y.attrs['standard_name'] = 'projection_y_coordinate'
            ds.y.attrs['units'] = 'm'
            ds.time.attrs['axis'] = 'T'
            ds.time.attrs['long_name'] = 'time'

            # Store metadata
            ds['product_metadata'] = xr.DataArray()
            for key, val in self._intermediate_data['metadata']['tags'].items():
                ds.product_metadata.attrs[key] = val
            for key, val in {
                f'{key1}:{key2}': val for key1
                in self._intermediate_data['metadata']['MTL'] for key2, val
                in self._intermediate_data['metadata']['MTL'][key1].items()
            }.items():
                ds.product_metadata.attrs[key] = val

            ds.attrs['data_type'] = 'rho'
            self.dataset = ds
        else:
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
            del ds

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
            path = list(self._inputs.input_product.parent.glob('*MTL.txt'))[0]
            with open(path, 'r') as f:
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

    def _compute_x_coords(self, x0, x1):
        x_start = x0 + 15
        x_stop = x1 - 15
        self._intermediate_data['x'] = np.arange(x_start, x_stop + 1, 30)

    def _compute_y_coords(self, y0, y1):
        y_start = y0 - 15
        y_stop = y1 + 15
        self._intermediate_data['y'] = np.arange(y_start, y_stop - 1, -30)


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
