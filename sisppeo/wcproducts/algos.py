# Copyright 2020 Arthur Coqué, Guillaume Morin, Pôle OFB-INRAE ECLA, UR RECOVER
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

"""This module gathers algorithms for water optics and water color remote sensing.

Each class of this module correspond to one algorithm. An algorithm can have
several calibrations (a calibration is a set of parameters), either
packaged within SISPPEO (these default calibrations are located in
'resources/wc_algo_calibration') or provided by the user.
Before its utilisation, an algorithm has to be instantiate with specific
settings like the product_type of further input products, the calibration
used, the band used (if needed), etc.

    Typical usage example:

    algo1 = Ndwi('L8_GRS')
    out_array1 = algo1(input_array1, input_array2)

    algo2 = QAA(**config)
    out_array2 = algo2(*input_arrays, 'rrs')
"""

from pathlib import Path
from typing import Union

import xarray as xr

from sisppeo.utils.algos import producttype_to_sat
from sisppeo.utils.config import wc_algo_config as algo_config
from sisppeo.utils.exceptions import InputError

# pylint: disable=invalid-name
# Ok for a custom type.
P = Union[str, Path]
N = Union[int, float]


class Ndwi:
    """Normalized Difference Water Index.

    Algorithm computing the NDWI from green and nir bands, using either surface
    reflectances (rh   o, unitless) or remote sensing reflectances (Rrs,
    in sr-1).
    This index was presented by McFeeters (1996).

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: An empty dict, since there is no parametrisation for NDWI.
    """
    name = 'ndwi'

    def __init__(self, product_type, **_ignored) -> None:
        """Inits an 'Ndwi' instance for a given 'product_type'.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_ESA_L2A or L8_USGS_L1GT)
            **_ignored: Unused kwargs send to trash.
        """
        try:
            self.requested_bands = algo_config[self.name][
                producttype_to_sat(product_type)]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with {self.name}'
            raise InputError(msg) from invalid_product
        self.meta = {}

    def __call__(self,
                 green: xr.DataArray,
                 nir: xr.DataArray,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on input arrays (green and nir).

        Args:
            green: An array (dimension 1 * N * M) of reflectances in the green
                part of the spectrum (B3 @ 560 nm for S2 & @ 563 nm for L8).
            nir: An array (dimension 1 * N * M) of reflectances in the NIR part
                of the spectrum (B8 @ 833 nm for S2, B5 @ 865 nm for L8).

        Returns:
            An array (dimension 1 * N * M) of NDVI values.
        """
        ndwi = (green - nir) / (green + nir)
        return ndwi
