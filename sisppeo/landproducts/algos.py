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

"""This module gathers algorithms for land cover remote sensing.

Each class of this module correspond to one algorithm. An algorithm can have
several calibrations (a calibration is a set of parameters), either
packaged within SISPPEO (these default calibrations are located in
'resources/land_algo_calibration') or provided by the user.
Before its utilisation, an algorithm has to be instantiate with specific
settings like the product_type of further input products, the calibration
used, the band used (if needed), etc.

Example::

    algo = NDVI('L8_GRS')
    out_array = algo(input_array1, input_array2)
"""

from pathlib import Path
from typing import Union

from xarray import DataArray
import logging
from sisppeo.utils.algos import producttype_to_sat
from sisppeo.utils.config import land_algo_config as algo_config
from sisppeo.utils.exceptions import InputError

# pylint: disable=invalid-name
# Ok for a custom type.
P = Union[str, Path]
N = Union[int, float]


class Ndvi:
    """Normalized Difference Vegetation Index.

    Algorithm computing the NDVI from red and NIR bands, using either surface
    reflectances (rho, unitless) or remote sensing reflectances (Rrs, in sr-1).

    Attributes:
        name: The name of the algorithm used. This is the key used by
          L3AlgoBuilder and that you must provide in config or when using
          the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    name = 'ndvi'

    def __init__(self, product_type: str, **_ignored) -> None:
        """Inits an 'Ndvi' instance for a given 'product_type'.

        Args:
            product_type: The type of the input satellite product (e.g.
              S2_ESA_L2A or L8_USGS_L1GT)
            **_ignored: Unused kwargs sent to trash.
        """
        try:
            self.requested_bands = algo_config[self.name][
                producttype_to_sat(product_type)]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with {self.name}'
            raise InputError(msg) from invalid_product
        self.meta = {}

    def __call__(self, red: DataArray,
                 nir: DataArray,
                 **_ignored) -> DataArray:
        """Runs the algorithm on input arrays (red and nir).

        Args:
            red: An array (dimension 1 * N * M) of reflectance in the red part
              of the spectrum (B4 @ 665 nm for S2 & @ 655 nm for L8).
            nir: An array (dimension 1 * N * M) of reflectance in the NIR part
              of the spectrum (B8 @ 833 nm for S2, B5 @ 865 nm for L8).

        Returns:
            A list composed of an array (dimension 1 * N * M) of NDVI values.
        """
        ndvi = (nir - red) / (nir + red)
        return ndvi


class Nbr:
    """Normalized Burn Ratio

    Algorithm computing the NBR from NIR and SWIR2 bands, using either surface
    reflectances (rho, unitless) or remote sensing reflectances (Rrs, in sr-1).

    Attributes:
        name: The name of the algorithm used. This is the key used by
          L3AlgoBuilder and that you must provide in config or when using
          the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    name = 'nbr'

    def __init__(self, product_type: str, **_ignored) -> None:
        """Inits an 'Nbr' instance for a given 'product_type'.

        Args:
            product_type: The type of the input satellite product (e.g.
              S2_ESA_L2A or L8_USGS_L1GT)
            **_ignored: Unused kwargs sent to trash.
        """
        try:
            self.requested_bands = algo_config[self.name][
                producttype_to_sat(product_type)]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with {self.name}'
            raise InputError(msg) from invalid_product
        self.meta = {}

    def __call__(self, swir: DataArray,
                 nir: DataArray,
                 **_ignored) -> DataArray:
        """Runs the algorithm on input arrays (nir and swir).

        Args:
            nir: An array (dimension 1 * N * M) of reflectance in the NIR part
              of the spectrum (B8 @ 833 nm for S2, B5 @ 865 nm for L8).
            swir: An array (dimension 1 * N * M) of reflectance in the swir part
              of the spectrum (B12 @ 2202 nm for S2, B7 @ 2200 nm for L8)
        Returns:
            An array (dimension 1 * N * M) of NBR values.
        """
        nbr = (nir - swir) / (nir + swir)
        return nbr
