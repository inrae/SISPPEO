# -*- coding: utf-8 -*-
# Copyright 2020 Arthur Coqué, Pierre Manchon, Pôle OFB-INRAE ECLA, UR RECOVER
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
"""This module gathers wc algorithms used for retrieving near surface bloom intensity.

Each class of this module correspond to one algorithm. An algorithm can have
several calibrations (a calibration is a set of parameters), either
packaged within SISPPEO (these default calibrations are located in
'resources/wc_algo_calibration') or provided by the user.
Before its utilisation, an algorithm has to be instantiate with specific
settings like the product_type of further input products, the calibration
used, the band used (if needed), etc.

Example:

    algo = BLOOM('L5', 'Ho_2019')
    out_array = algo(input_arrays, 'rho')
"""
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import xarray as xr

from sisppeo.utils.naming import get_requested_bands
from sisppeo.utils.algos import load_calib
from sisppeo.utils.config import wc_algo_config
from sisppeo.utils.config import wc_calib
from sisppeo.utils.exceptions import InputError

# pylint: disable=invalid-name
# Ok for a custom type.
P = Union[str, Path]
N = Union[int, float]


def _mask_clouds(array: xr.DataArray,
                 quality_assessment: xr.DataArray,
                 cloud_mask_values: List
                 ) -> xr.DataArray:
    for cloud_mask_value in cloud_mask_values:
        array = np.where(quality_assessment == cloud_mask_value, np.nan, array)
    return array


class BLOOM:
    _default_calibration_file = wc_calib / 'bloom-ho.yaml'
    _default_calibration_name = 'Ho_2019'
    name = 'bloom-ho'

    def __init__(self,
                 product_type,
                 calibration: Optional[P] = None,
                 **_ignored) -> None:
        self.cloud_mask_values = None
        self.requested_bands, prod = get_requested_bands(algo_config=wc_algo_config,
                                                         product_type=product_type,
                                                         name=self.name)


        calibration_dict, calibration_name = load_calib(calibration,
                                                        self._default_calibration_file,
                                                        self._default_calibration_name)
        self._valid_limit = calibration_dict['validity_limit']
        try:
            params = calibration_dict[prod]
        except KeyError as invalid_input:
            msg = (f'{product_type} or {self.requested_bands} is not allowed with '
                   f'{self.name}/this calibration')
            raise InputError(msg) from invalid_input
        self.__dict__.update(params)
        self.meta = {'band': self.requested_bands,
                     'calibration': calibration_name,
                     'validity_limit': self._valid_limit,
                     **params}

    def __call__(self,
                 blue: xr.DataArray,
                 green: xr.DataArray,
                 red: xr.DataArray,
                 nir: xr.DataArray,
                 swir1: xr.DataArray,
                 mask: xr.DataArray,
                 data_type: str,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('ref').

                Args:
                    blue: An array (dimension 1 * N * M) of 'data_type'.
                    green: An array (dimension 1 * N * M) of 'data_type'.
                    red: An array (dimension 1 * N * M) of 'data_type'.
                    nir: An array (dimension 1 * N * M) of 'data_type'.
                    swir1: An array (dimension 1 * N * M) of 'data_type'.
                    mask: An array (dimension 1 * N * M) of 'data_type'.
                    data_type: Either 'ref' or 'rrs' (respectively surface reflectance
                        and remote sensing reflectance).
                    **_ignored: Unused kwargs sent to trash.

                Returns:
                    An array (dimension 1 * N * M) of bloom (between 0 and 0.1).
        """
        if data_type == 'rrs':
            blue = np.pi * blue
            green = np.pi * green
            red = np.pi * red
            nir = np.pi * nir
            swir1 = np.pi * swir1

        np.warnings.filterwarnings('ignore')
        # pylint: disable=no-member
        # Loaded in __init__ with "__dict__.update".
        # Isolate the high confidence cloud mask from the BQA band and apply it to every other bands
        _blue = _mask_clouds(blue, mask, self.cloud_mask_values)
        _green = _mask_clouds(green, mask, self.cloud_mask_values)
        _red = _mask_clouds(red, mask, self.cloud_mask_values)
        _nir = _mask_clouds(nir, mask, self.cloud_mask_values)
        _swir1 = _mask_clouds(swir1, mask, self.cloud_mask_values)

        # Create an array of the minimum value from each of the 3 arrays
        _min_arr = np.fmin(np.fmin(_blue, _green), _red)

        # when I replace by nan it impacts the other arrays during the calculation int + nan = nan so since the
        # 3 arrays complete each other, they cancel each other out at the same time (the False are replaced by NAN
        # so all the calculated values will be NAN)
        _h_arr = np.where(_min_arr == _blue, ((_green-_blue)/(_red+_green-(2*_blue))), 0) +\
            np.where(_min_arr == _green, (((_red-_green)/(_red+_blue-(2*_green)))+2), 0) +\
            np.where(_min_arr == _red, (((_blue-_red)/(_green+_blue-(2*_red)))+1), 0)

        # Compute the G value by assigning 1 or 0 if H is lesser or greater than 1.6
        _g_arr = np.where(np.where(_h_arr == 0, np.nan, _h_arr) < 1.6, 1, 0)

        # Compute the result (between 0 and 0.1) for each elements
        _bloom = np.where(_g_arr == 0, np.nan, _g_arr*(_nir-(1.03*_swir1)))

        # Mask out every value i don't want
        bloom = np.where((_bloom < self._valid_limit[0]) | (_bloom > self._valid_limit[1]), np.nan, _bloom)
        return xr.DataArray(bloom, coords=blue.coords, dims=blue.dims, attrs=blue.attrs)
