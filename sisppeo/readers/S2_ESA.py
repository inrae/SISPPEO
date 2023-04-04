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

"""This module contains a reader for S2_ESA products.

This reader is dedicated to extract data from both S2_ESA_L1C and S2_ESA_L2A.

Example::

    reader = S2ESAReader(**config)
    reader.extract_bands()
    reader.create_ds()
    extracted_dataset = reader.dataset
"""

import warnings
from collections import namedtuple
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from zipfile import ZipFile

import numpy as np
import rasterio
import xarray as xr
from pyproj import CRS
from rasterio.windows import Window
from tqdm import tqdm

from sisppeo.readers.reader import Inputs, Reader
from sisppeo.utils.exceptions import InputError
from sisppeo.utils.readers import (decode_data, get_ij_bbox,
                                   resample_band_array,
                                   resize_and_resample_band_array)

warnings.filterwarnings('ignore', category=rasterio.errors.NotGeoreferencedWarning)

S2ESAInputs = namedtuple('S2ESAInputs',
                         Inputs._fields + ('out_resolution',))


class S2ESAReader(Reader):
    """A reader dedicated to extract data from both S2_ESA_L1C and S2_ESA_L2A products.

    Attributes:
        dataset: A dataset containing extracted data.
    """

    def __init__(self,
                 input_product: Path,
                 requested_bands: List[str],
                 geom: Optional['dict'] = None,
                 out_resolution: Optional[int] = None,
                 **_ignored) -> None:
        """See base class.

        Args:
            out_resolution: The wanted resolution of the output product. Used
              when performing resampling operations.
        """
        super().__init__(input_product=input_product, requested_bands=requested_bands, geom=geom)
        if out_resolution not in (None, 10, 20, 60):
            raise InputError('"out_resolution" must be in (10, 20, 60)')
        self._inputs = S2ESAInputs(*self._inputs, out_resolution)

    def extract_bands(self) -> None:
        """See base class."""
        # Load data
        if self._inputs.input_product.suffix == '.zip':
            with ZipFile(self._inputs.input_product) as archive:
                xml_path = [_ for _ in archive.namelist()
                            if _.lstrip(f'{self._inputs.input_product.stem}'
                                        '.SAFE').startswith('/MTD_MSI')][0]
            dataset = rasterio.open(
                f'zip://{str(self._inputs.input_product.resolve())}!/' + xml_path
            )
        else:
            dataset = rasterio.open(
                list(self._inputs.input_product.glob('MTD_MSI*.xml'))[0]
            )

        # Load metadata
        metadata = {'tags': dataset.tags()}

        # Filter subdatasets (and map bands)
        requested_bands = []
        for path in dataset.subdatasets[:-1]:
            with rasterio.open(path) as subdataset:
                bands = [
                    (i + 1, band) for i, band in enumerate(
                        [_.split(', ')[0] for _ in subdataset.descriptions]
                    ) if band in self._inputs.requested_bands
                ]
                if bands:
                    requested_bands.append((path, bands))

        # Extract data
        data = {}
        for path, bands in requested_bands[::-1]:
            with rasterio.open(path) as subdataset:
                for i, band in tqdm(bands, unit='bands'):
                    # Set the default resolution
                    if self._inputs.out_resolution is None:
                        self._inputs = self._inputs._replace(
                            out_resolution=subdataset.res[0])
                    if self._intermediate_data['x'] is None:
                        if ((out_res := self._inputs.out_resolution)
                                > (in_res := subdataset.res[0])):
                            msg = (f'"out_resolution" must be <= {in_res} ; '
                                   f'here, out_resolution={out_res}')
                            raise InputError(msg)
                        self._intermediate_data['crs'] = CRS.from_epsg(
                            subdataset.crs.to_epsg()
                        )
                        band_array, xy_bbox = self._extract_first_band(
                            subdataset,
                            i
                        )
                    else:
                        band_array = self._extract_nth_band(subdataset, i,
                                                            xy_bbox)
                    data[band] = band_array.reshape(1, *band_array.shape)
        dataset.close()
        print('')

        # Store outputs
        self._intermediate_data['data'] = data
        self._intermediate_data['metadata'] = metadata

    def create_ds(self) -> None:
        """See base class."""
        # Create the dataset
        ds = xr.Dataset(
            {key: (['time', 'y', 'x'], val) for key, val
             in self._intermediate_data['data'].items()},
            coords={
                'x': ('x', self._intermediate_data['x']),
                'y': ('y', self._intermediate_data['y']),
                'time': [datetime.fromisoformat(self._intermediate_data[
                    'metadata']['tags']['PRODUCT_START_TIME'][:-1])]
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
        for key, val in self._intermediate_data['metadata']['tags'].items():
            ds.product_metadata.attrs[key] = val

        ds.attrs['data_type'] = 'rho'
        self.dataset = ds

    def _compute_x_coords(self, x0, x1):
        out_res = self._inputs.out_resolution
        x_start = x0 + out_res / 2
        x_stop = x1 - out_res / 2
        self._intermediate_data['x'] = np.arange(x_start, x_stop + 1, out_res)

    def _compute_y_coords(self, y0, y1):
        out_res = self._inputs.out_resolution
        y_start = y0 - out_res / 2
        y_stop = y1 + out_res / 2
        self._intermediate_data['y'] = np.arange(y_start, y_stop - 1, -out_res)

    # pylint: disable=too-many-locals
    # False positive.
    def _extract_first_band(self, subdataset, i):
        if self._inputs.ROI is not None:
            self._reproject_geom()
            row_start, col_start, row_stop, col_stop = get_ij_bbox(
                subdataset,
                self._intermediate_data['geom']
            )
            arr = subdataset.read(
                i,
                window=Window.from_slices((row_start, row_stop + 1),
                                          (col_start, col_stop + 1))
            )
            # Update internal coords
            x0, y0 = subdataset.transform * (col_start, row_start)
            x1, y1 = subdataset.transform * (col_stop + 1, row_stop + 1)
        else:
            arr = subdataset.read(i)
            # Update internal coords
            x0, y0 = subdataset.transform * (0, 0)
            x1, y1 = subdataset.transform * (subdataset.width,
                                             subdataset.height)
        # Get encoding parameters
        scale_factor = 1 / _get_quantification_value(subdataset.tags())
        fill_value = float(subdataset.tags()['SPECIAL_VALUE_NODATA'])
        # Decode extracted data
        band_array = decode_data(arr, scale_factor, fill_value)
        if (out_res := self._inputs.out_resolution) != subdataset.res[0]:
            band_array = resample_band_array(band_array, subdataset.res[0],
                                             out_res)
        # Compute projected coordinates
        self._compute_x_coords(x0, x1)
        self._compute_y_coords(y0, y1)
        # Update internal coords
        x1 -= 1
        y1 += 1
        return band_array, [x0, y0, x1, y1]

    # pylint: disable=too-many-locals
    # More readable if coordonates are explicitely extracted from the bbox.
    def _extract_nth_band(self, subdataset, i, xy_bbox):
        x0, y0, x1, y1 = xy_bbox
        row_start, col_start = subdataset.index(x0, y0)
        row_stop, col_stop = subdataset.index(x1, y1)
        arr = subdataset.read(
            i,
            window=Window.from_slices(
                (row_start, row_stop + 1),
                (col_start, col_stop + 1)
            )
        )
        # Get encoding parameters
        scale_factor = 1 / _get_quantification_value(subdataset.tags())
        fill_value = float(subdataset.tags()['SPECIAL_VALUE_NODATA'])
        # Decode extracted data
        band_array = decode_data(arr, scale_factor, fill_value)
        ij_bbox = [row_start, col_start, row_stop, col_stop]
        if (out_res := self._inputs.out_resolution) != subdataset.res[0]:
            band_array = resize_and_resample_band_array(band_array, ij_bbox,
                                                        subdataset.res[0],
                                                        out_res)
        return band_array


def _get_quantification_value(metadata):
    """Gets the quantification value (to compute correct reflectances)"""
    if metadata['PROCESSING_LEVEL'] == 'Level-1C':
        quantification_value = float(metadata['QUANTIFICATION_VALUE'])
    else:   # L2A
        quantification_value = float(metadata['BOA_QUANTIFICATION_VALUE'])
    return quantification_value
