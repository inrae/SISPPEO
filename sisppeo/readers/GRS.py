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
"""This module contains a reader for GRS products.

This reader is dedicated to extract data from S2_GRS, L4_GRS, L5_GRS, L7_GRS
and L8_GRS products.

    Typical usage example:

    reader = GRSReader(**config)
    reader.extract_bands()
    reader.create_ds()
    extracted_dataset = reader.dataset
"""
from collections import namedtuple
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
import xarray as xr
from affine import Affine
from pyproj import CRS
from tqdm import tqdm

from sisppeo.readers.reader import Inputs, Reader
from sisppeo.utils.exceptions import GeometryError
from sisppeo.utils.naming import names_dict_GRS

GRSInputs = namedtuple('GRSInputs', Inputs._fields + ('product_type', 'flags', 'grs_bands'))


class GRSReader(Reader):
    """A reader dedicated to extract data from both S2_GRS, L4_GRS, L5_GRS,
    L7_GRS and L8_GRS products.

    Attributes:
        dataset: A dataset containing extracted data.
    """
    # pylint: disable=too-many-arguments
    # Six is reasonable in this case.
    def __init__(self,
                 input_product: Path,
                 product_type: str,
                 requested_bands: List[str],
                 geom: Optional[dict] = None,
                 glint_corrected: bool = True,
                 flags: bool = False,
                 **_ignored) -> None:
        """See base class.

        Args:
            glint_corrected: A boolean that tells the reader to extract bands
                with sunglint (False) or the ones corrected from sunglint
                (True).
            flags: A boolean telling the reader whether or not to use a GRS
                mask named "flags" (="Flags for aquatic color purposes"),
                useful for extracting water surfaces.
        """
        if 'S2' in product_type:
            from sisppeo.utils.naming import names_dict_s2 as names_dict
            self._res = 20
        elif 'L8' in product_type:
            from sisppeo.utils.naming import names_dict_l8_GRS as names_dict
            self._res = 30
        else:
            from sisppeo.utils.naming import names_dict_l457 as names_dict
            self._res = 30
        names_dict.update(names_dict_GRS)
        super().__init__(input_product=input_product, requested_bands=requested_bands, names_dict=names_dict, geom=geom)
        self._inputs = GRSInputs(*self._inputs, product_type, flags,
                                 'Rrs' if glint_corrected else 'Rrs_g')

    # pylint: disable=too-many-locals
    # More readable if geotransform is defined.
    def extract_bands(self) -> None:
        """See base class."""
        # Load data
        dataset = xr.open_dataset(self._inputs.input_product)

        # Load metadata
        metadata = {'attrs': dataset.attrs, 'tags': dataset.metadata.attrs}

        # Load geotransform and get image boundaries
        i2m = [float(_) for _ in dataset.crs.i2m.split(',')]
        geotransform = (i2m[4], i2m[0], i2m[1], i2m[5], i2m[2], i2m[3])
        fwd = Affine.from_gdal(*geotransform)
        x0, y0 = float(i2m[4]), float(i2m[5])
        x1, y1 = fwd * (dataset.x.values[-1] + 1, dataset.y.values[-1] + 1)
        xy_bbox = [x0, y0, x1, y1]

        # Store the CRS
        self._intermediate_data['crs'] = CRS.from_wkt(dataset.crs.wkt)

        # Get ROI and read data
        data = {}
        ij_bbox = self._extract_ROI(xy_bbox, len(dataset.x), len(dataset.y))
        for band in tqdm(self._inputs.requested_bands, unit='bands'):
            if band not in names_dict_GRS.values():
                band_name = f'{self._inputs.grs_bands}_{band}'
            else:
                band_name = band
            band_array = _extract_band(dataset, band_name, ij_bbox)
            data[band] = band_array.reshape(1, *band_array.shape)
        print('')

        # Mask data
        if self._inputs.flags:
            mask = _extract_band(dataset, 'flags', ij_bbox)
            for band in data:
                data[band] = np.where(mask == 0, data[band], np.nan)

        # Compute projected coordinates
        self._compute_proj_coords(fwd, ij_bbox)

        dataset.close()

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
                'time': [datetime.strptime(
                    self._intermediate_data['metadata']['attrs']['start_date'],
                    '%d-%b-%Y %H:%M:%S.%f')],
                'x': ('x', self._intermediate_data['x']),
                'y': ('y', self._intermediate_data['y'])
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

        ds.attrs['data_type'] = 'rrs'
        ds.attrs['grs_bands'] = self._inputs.grs_bands
        if self._inputs.flags:
            ds.attrs['suppl_masks'] = 'GRS_flags'
        self.dataset = ds

    # pylint: disable=invalid-name
    # ROI is a common abbreviation for a Region Of Interest.
    def _extract_ROI(self, xy_bbox, nx, ny):
        if self._inputs.ROI is not None:
            self._reproject_geom()
            x_min, y_min, x_max, y_max = self._intermediate_data['geom'].bounds
            x0, y0, x1, y1 = xy_bbox
            if (x_max < x0 or y_min > y0) or (x_min > x1 or y_max < y1):
                raise GeometryError('Wanted ROI is outside the input product')
            row_start = 0 if y_max > y0 else int(np.floor((y0 - y_max)
                                                          / self._res))
            col_start = 0 if x_min < x0 else int(np.floor((x_min - x0)
                                                          / self._res))
            row_stop = ny - 1 if y_min < y1 else int(
                np.floor((y0 - y_min) / self._res))
            col_stop = nx - 1 if x_max > x1 else int(
                np.floor((x_max - x0) / self._res))
        else:
            row_start, col_start = 0, 0
            row_stop, col_stop = ny - 1, nx - 1
        return row_start, col_start, row_stop, col_stop

    def _compute_proj_coords(self, fwd, ij_bbox):
        row_start, col_start, row_stop, col_stop = ij_bbox
        x_start, y_start = fwd * (col_start, row_start)
        x_stop, y_stop = fwd * (col_stop + 1, row_stop + 1)
        x = np.arange(x_start + self._res / 2, x_stop - 1, self._res)
        y = np.arange(y_start - self._res / 2, y_stop + 1, -self._res)
        self._intermediate_data['x'] = x
        self._intermediate_data['y'] = y


def _extract_band(dataset, band, ij_bbox):
    row_start, col_start, row_stop, col_stop = ij_bbox
    band_array = dataset[band].values[row_start:row_stop + 1,
                                      col_start:col_stop + 1]
    return band_array
