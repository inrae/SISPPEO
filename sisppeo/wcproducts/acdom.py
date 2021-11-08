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

"""This module gathers wc algorithms used for retrieving aCDOM (/[DOC]).

Each class of this module correspond to one algorithm. An algorithm can have
several calibrations (a calibration is a set of parameters), either
packaged within SISPPEO (these default calibrations are located in
'resources/wc_algo_calibration') or provided by the user.
Before its utilisation, an algorithm has to be instantiate with specific
settings like the product_type of further input products, the calibration
used, the band used (if needed), etc.

Example:

    algo = ACDOMBrezonik('S2_GRS', 'Brezonik_2015')
    out_array = algo(input_array, 'rrs')
"""

from pathlib import Path
from typing import Optional, Union

import numpy as np
import xarray as xr

from sisppeo.utils.algos import load_calib, producttype_to_sat
from sisppeo.utils.config import wc_algo_config as algo_config, wc_calib
from sisppeo.utils.exceptions import InputError

# pylint: disable=invalid-name
# Ok for a custom type.
P = Union[str, Path]
N = Union[int, float]


class ACDOMBrezonik:
    """CDOM absorption (in m-1) at 440 nm from Brezonik et al., 2015.

    Algorithm based on decreasing exponential short over long wavelength ratio
    to retrieve aCDOM (in m-1) from surface reflectances (rho, unitless) or
    remote sensing reflectances (Rrs, in sr-1) bands B2 MSI B6 MSI, bands B3
    and B4 OLI, bands B5 and B12 OLCI.
    This algorithm was published in Brezonik et al., 2015

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'acdom-brezonik.yaml'
    _default_calibration_name = 'Brezonik_2015'
    name = 'acdom-brezonik'

    def __init__(self,
                 product_type: str,
                 calibration: Optional[P] = None,
                 **_ignored) -> None:
        """Inits an 'ACDOMBrezonik' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_ESA_L2A or L8_USGS_L1GT)
            calibration: The calibration (set of parameters) used by the
                algorithm (default=_default_calibration_name).
            **_ignored: Unused kwargs sent to trash.
        """
        try:
            self.requested_bands = algo_config[self.name][
                producttype_to_sat(product_type)]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with {self.name}'
            raise InputError(msg) from invalid_product
        calibration_dict, calibration_name = load_calib(
            calibration,
            self._default_calibration_file,
            self._default_calibration_name
        )
        self._valid_limit = calibration_dict['validity_limit']
        try:
            params = calibration_dict[producttype_to_sat(product_type)]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with this calibration'
            raise InputError(msg) from invalid_product
        self.__dict__.update(params)
        self.meta = {'calibration': calibration_name,
                     'validity_limit': self._valid_limit,
                     **params}

    def __call__(self,
                 ref_shortwl: xr.DataArray,
                 ref_longwl: xr.DataArray,
                 data_type: str,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('ref').

        Args:
            ref_shortwl: An array (dimension 1 * N * M) of 'data_type'.
            ref_longwl: An array (dimension 1 * N * M) of 'data_type'.
            data_type: Either 'ref' or 'rrs' (respectively surface reflectance
                and remote sensing reflectance).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of acdom(440) (in m-1).
        """

        if data_type == 'rho':
            ref_shortwl = ref_shortwl / np.pi
            ref_longwl = ref_longwl / np.pi

        np.warnings.filterwarnings('ignore')
        ref_shortwl = ref_shortwl.where(ref_shortwl >= 0)
        ref_longwl = ref_longwl.where(ref_shortwl >= 0)

        # pylint: disable=no-member
        # Loaded in __init__ whit "__dict__.update".
        acdom = np.exp(self.a1 + self.a2 * np.log(ref_shortwl / ref_longwl))
        acdom = acdom.where((acdom >= 0) & (acdom <= self._valid_limit))
        return acdom
