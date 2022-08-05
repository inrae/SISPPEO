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

"""Contains useful stuff for products."""

import bisect
from typing import List, Optional, Tuple, Union
import logging
import numpy as np
from pyproj import CRS, Transformer
from skimage.draw import disk
from xarray import DataArray

from sisppeo.utils.exceptions import InputError

# pylint: disable=invalid-name
# Ok for a custom type.
N = Union[int, float]


def get_enc(array, scale_factor, compression=False):
    min_ = np.nanmin(array)
    max_ = np.nanmax(array)
    if np.isnan(min_):
        enc = {'dtype': np.uint8, '_FillValue': 0}
    else:
        offset = min_ - 1
        min_, max_ = 1, max_ - offset
        if max_ <= 255 * scale_factor:
            dtype, fill_value = np.uint8, 0
        elif max_ <= 65535 * scale_factor:
            dtype, fill_value = np.uint16, 0
        elif max_ <= 4294967295 * scale_factor:
            dtype, fill_value = np.uint32, 0
        else:
            dtype, fill_value = np.uint64, 0
        enc = {'dtype': dtype, '_FillValue': fill_value,
               'scale_factor': scale_factor, 'add_offset': offset}
    if compression:
        enc.update({'zlib': True, 'complevel': 9})
        if min(_ for _ in array.shape if _ > 1) > 239:
            enc['chunksizes'] = [1, 60, 60]
    return enc


def get_grid(n: int) -> Tuple[int, int]:
    """Gets the number of rows and columns needed according the number of subplots."""
    rows = (n + 2) // 3
    if n <= 3:
        cols = n
    elif n == 4:
        cols = 2
    else:
        cols = 3
    return rows, cols


class CoordinatesMixin:
    """A Mixin which adds extra properties and methods related to coordinates."""
    __slots__ = ()

    @property
    def bounds(self) -> Tuple[N, ...]:
        """Returns the boundaries of this product: (xmin, ymin, xmax, ymax)."""
        return (self.x.values.min() - self.res / 2,
                self.y.values.min() - self.res / 2,
                self.x.values.max() + self.res / 2,
                self.y.values.max() + self.res / 2)

    @property
    def res(self) -> N:
        """Returns the spatial resolution of this product."""
        res = self.dataset.x.values[1] - self.dataset.x.values[0]
        if isinstance(res, float):
            if res.is_integer():
                res = int(res)
        return res

    @property
    def x(self) -> DataArray:
        """Returns x-coords."""
        return self.dataset.x

    @property
    def y(self) -> DataArray:
        """Returns y-coords."""
        return self.dataset.y

    def xy(self, i, j) -> Tuple[int, int]:
        """Gets (x, y) from (i, j)."""
        if 0 <= i < len(self.y) and 0 <= j < len(self.x):
            return self.x.values[j], self.y.values[i]
        else:
            msg = (f'i ({i}) must be in [0, {len(self.y)}] ; '
                   f'j ({j}) must be in [0, {len(self.x)}]')
            raise InputError(msg)

    def index(self, x, y) -> Tuple[N, N]:
        """Gets (i, j) from (x, y)"""
        if (self.bounds[0] <= x <= self.bounds[2]
                and self.bounds[1] <= y <= self.bounds[3]):
            j = bisect.bisect_right((self.x.values - self.res / 2).tolist(),
                                    x) - 1
            i = -bisect.bisect_left(sorted((self.y.values
                                            + self.res / 2).tolist()),
                                    y) + len(self.y) - 1
            return i, j
        else:
            msg = (f'x ({x}) must be in [{self.bounds[0]}, {self.bounds[2]}] ; '
                   f'y ({y}) must be in [{self.bounds[1]}, {self.bounds[3]}]')
            raise InputError(msg)

    def extract_point(self,
                      data_var: str,
                      coordinates: Tuple[N, N],
                      buffer: Optional[int] = None,
                      epsg: int = 4326,
                      mode: str = 'xy'):
        """Returns value(s) at the given coordinates.

        Args:
            data_var: The name of the variable/DataArray of interest (e.g., a
                band, aCDOM, etc).
            coordinates: A tuple of geographic or projected coordinates; see
                "mode".
            buffer: Optional; The radius (in pixels) of the circle (centered on
                coordinates) to extract. Defaults to None.
            epsg: Optional; The EPSG code. Defaults to 4326.
            mode: Optional; Either 'xy' or 'latlon'. Defaults to 'xy'.

        Returns:
            An xr.DataArray containing the wanted information.
        """
        if data_var not in self.data_vars:
            msg = (f'"{data_var}" is not a variable of this product; please, '
                   f'choose one from the following list: {self.data_vars}.')
            raise InputError(msg)
        if mode == 'latlon' or epsg != 4326:
            transformer = Transformer.from_crs(
                CRS.from_epsg(epsg),
                CRS.from_wkt(self.dataset.crs.attrs['crs_wkt'])
            )
            coordinates = transformer.transform(*coordinates)
        i, j = self.index(*coordinates)
        if buffer is None:
            res = self.dataset[data_var].isel(y=i, x=j)
        else:
            res = self.dataset[data_var].isel(
                y=slice(i - buffer, i + buffer + 1),
                x=slice(j - buffer, j + buffer + 1)
            )
            mask = np.full(res.isel(time=0).shape, np.nan)
            rr, cc = disk((buffer, buffer), buffer + 0.5)
            mask[rr, cc] = 1
            res *= mask
        return res

    def extract_points(self,
                       data_var: str,
                       lst_coordinates: List[Tuple[N, N]],
                       buffer: Optional[int] = None,
                       epsg: int = 4326,
                       mode: str = 'xy'):
        """Returns value(s) at each tuple of coordinates of the given list.

        Args:
            data_var: The name of the variable/DataArray of interest (e.g., a
                band, aCDOM, etc).
            lst_coordinates: A list of tuples of geographic or projected
                coordinates; see "mode".
            buffer: Optional; The radius (in pixels) of the circle (centered on
                coordinates) to extract. Defaults to None.
            epsg: Optional; The EPSG code. Defaults to 4326.
            mode: Optional; Either 'xy' or 'latlon'. Defaults to 'xy'.

        Returns:
            A list of xr.DataArray (one per coordinates tuple) containing the
            wanted information.
        """
        if data_var not in self.data_vars:
            msg = (f'"{data_var}" is not a variable of this product; please, '
                   f'choose one from the following list: {self.data_vars}.')
            raise InputError(msg)
        if mode == 'latlon' or epsg != 4326:
            transformer = Transformer.from_crs(
                CRS.from_epsg(epsg),
                CRS.from_wkt(self.dataset.crs.attrs['crs_wkt'])
            )
            lst_coordinates = [transformer.transform(*coordinates)
                               for coordinates in lst_coordinates]
        res = [self.extract_point(data_var, coordinates, buffer)
               for coordinates in lst_coordinates]
        return res


def normalize_arr(arr, min_, max_, new_max=255):
    """Normalize an array between 0 and new_max.

    Args:
        arr: The input array.
        min_: The value to consider as being the min of the array.
        max_: The value to consider as being the min of the array.
        new_max: The maximum value of the output array.
    """
    return new_max * (arr - min_) / (max_ - min_)
