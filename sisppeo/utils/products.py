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

"""This module contains useful stuff for products."""

import bisect
from typing import Tuple, Union

import numpy as np
from xarray import DataArray

from sisppeo.utils.exceptions import InputError

# pylint: disable=invalid-name
# Ok for a custom type.
N = Union[int, float]


def get_enc(array, scale_factor, compression=False):
    min_ = np.nanmin(array)
    max_ = np.nanmax(array)
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
        enc.update({'zlib': True, 'complevel': 9, 'chunksizes': [1, 60, 60]})
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
            msg = (f'i must be in [0, {len(self.y)}] ; '
                   f'j must be in [0, {len(self.x)}]')
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
            msg = (f'x must be in [{self.bounds[0]}, {self.bounds[2]}] ; '
                   f'y must be in [{self.bounds[1]}, {self.bounds[3]}]')
            raise InputError(msg)
