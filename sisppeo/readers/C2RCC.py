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

"""This module contains a reader for C2RCC products.

This reader is dedicated to extract data from C2RCC products.

Example::

    reader = C2RCCReader(**config)
    reader.extract_bands()
    reader.create_ds()
    extracted_dataset = reader.dataset
"""

from collections import namedtuple
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Union
import logging
import numpy as np
import xarray as xr
from pyproj import CRS, Transformer
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info
from tqdm import tqdm

from sisppeo.readers.reader import Reader, Inputs
from sisppeo.utils.exceptions import GeometryError, InputError, ProductError

C2RCCInputs = namedtuple('C2RCCInputs', Inputs._fields + ('sensing_date',))


class C2RCCReader(Reader):
    """A reader dedicated to extract data from C2RCC products.

    Attributes:
        dataset: A dataset containing extracted data.
    """

    def __init__(self,
                 input_product: Path,
                 requested_bands: List[str],
                 geom: Optional['dict'] = None,
                 sensing_date: Optional[Union[str, datetime]] = None,
                 **_ignored) -> None:
        """See base class.

        Args:
            sensing_date: The sensing date (in UTC time) of the product.
        """
        super().__init__(input_product, requested_bands, geom)
        if sensing_date is None:
            raise InputError('"sensing_date" is missing!')
        for band in requested_bands:
            if band in ('B7', 'B8', 'B8A', 'B11', 'B12'):
                raise ProductError(f'{band} is not available in C2RCC products')
        if isinstance(sensing_date, str):
            try:
                sensing_date = datetime.strptime(sensing_date.replace('-', ''),
                                                '%Y%m%d')
            except ValueError:
                msg = '"sensing_date" must be in "YYYY-MM-DD" (or "YYYMMDD") format'
                raise InputError(msg)
        self._inputs = C2RCCInputs(*self._inputs, sensing_date)

    # pylint: disable=too-many-locals
    # More readable if geotransform is defined.
    def extract_bands(self) -> None:
        """See base class."""
        # Load data
        dataset = xr.open_dataset(self._inputs.input_product)

        # Get and store the CRS
        latlon_bbox = (dataset.lat.max().values, dataset.lon.min().values,
                       dataset.lat.min().values, dataset.lon.max().values)
        nx, ny = len(dataset.x), len(dataset.y)
        utm_crs_list = query_utm_crs_info(
            datum_name='WGS 84',
            area_of_interest=AreaOfInterest(
                west_lon_degree=latlon_bbox[1],
                south_lat_degree=latlon_bbox[2],
                east_lon_degree=latlon_bbox[3],
                north_lat_degree=latlon_bbox[0]
            )
        )
        utm_crs = CRS.from_epsg(utm_crs_list[0].code)
        self._intermediate_data['crs'] = utm_crs

        # Compute projected coordinates and get image boundaries
        xy_bbox = self._compute_proj_coords(latlon_bbox, nx, ny)

        # Get ROI and read data
        data = {}
        ij_bbox = self._extract_ROI(xy_bbox, nx, ny)
        for band in tqdm(self._inputs.requested_bands, unit='bands'):
            band_name = f'rhown_{band}'
            band_array = _extract_band(dataset, band_name, ij_bbox)
            data[band] = band_array.reshape(1, *band_array.shape)

        dataset.close()

        # Store outputs
        self._intermediate_data['data'] = data

    def create_ds(self) -> None:
        """See base class."""
        # Create the dataset
        ds = xr.Dataset(
            {key: (['time', 'y', 'x'], val) for key, val
             in self._intermediate_data['data'].items()},
            coords={
                # 'time': [datetime.strptime(
                #     self._intermediate_data['metadata']['attrs']['start_date'],
                #     '%d-%b-%Y %H:%M:%S.%f')],
                'time': [self._inputs.sensing_date],
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

        ds['product_metadata'] = xr.DataArray()

        ds.attrs['data_type'] = 'rho'
        self.dataset = ds

    # pylint: disable=invalid-name
    # ROI is a common abbreviation for a Region Of Interest.
    def _extract_ROI(self, xy_bbox, nx, ny) -> Tuple[int, int, int, int]:
        if self._inputs.ROI is not None:
            self._reproject_geom()
            x_min, y_min, x_max, y_max = self._intermediate_data['geom'].bounds
            x0, y0, x1, y1 = xy_bbox
            if (x_max < x0 or y_min > y0) or (x_min > x1 or y_max < y1):
                raise GeometryError('Wanted ROI is outside the input product')
            row_start = 0 if y_max > y0 else int(np.floor((y0 - y_max) / 20))
            col_start = 0 if x_min < x0 else int(np.floor((x_min - x0) / 20))
            row_stop = ny - 1 if y_min < y1 else int(
                np.floor((y0 - y_min) / 20))
            col_stop = nx - 1 if x_max > x1 else int(
                np.floor((x_max - x0) / 20))
        else:
            row_start, col_start = 0, 0
            row_stop, col_stop = ny - 1, nx - 1
        return row_start, col_start, row_stop, col_stop

    def _compute_proj_coords(self, latlon_bbox, nx, ny) -> Tuple[int, int, int, int]:
        utm_crs = self._intermediate_data['crs']
        proj = Transformer.from_crs(utm_crs.geodetic_crs, utm_crs)
        x_min, y_max = np.round(proj.transform(*latlon_bbox[:2])).astype(int)
        x_max, y_min = np.round(proj.transform(*latlon_bbox[2:])).astype(int)
        x = np.linspace(x_min, x_max, nx)
        y = np.linspace(y_max, y_min, ny)
        self._intermediate_data['x'] = x
        self._intermediate_data['y'] = y
        return x_min, y_max, x_max, y_min


def _extract_band(dataset, band, ij_bbox):
    row_start, col_start, row_stop, col_stop = ij_bbox
    band_array = dataset[band].values[row_start:row_stop + 1,
                                      col_start:col_stop + 1]
    return band_array
