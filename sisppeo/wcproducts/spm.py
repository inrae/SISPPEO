# -*- coding: utf-8 -*-
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
"""This module gathers wc algorithms used for estimating SPM concentrations.

Each class of this module correspond to one algorithm. An algorithm can have
several calibrations (a calibration is a set of parameters), either
packaged within SISPPEO (these default calibrations are located in
'resources/wc_algo_calibration') or provided by the user.
Before its utilisation, an algorithm has to be instantiate with specific
settings like the product_type of further input products, the calibration
used, the band used (if needed), etc.

Example:

    algo1 = SPMNechad('S2_GRS', 'B4', 'Nechad_2016')
    out_array2 = algo1(input_array, 'rho')

    algo2 = SPMGet('L8_GRS', 'GET_2018')
    out_array2 = algo2(red_array, nir_array, 'rrs')
"""
from pathlib import Path
from typing import Optional, Union

import numpy as np
import xarray as xr

from sisppeo.utils.algos import load_calib
from sisppeo.utils.naming import get_requested_bands
from sisppeo.utils.config import wc_algo_config, wc_calib
from sisppeo.utils.exceptions import InputError

# pylint: disable=invalid-name
# Ok for a custom type.
P = Union[str, Path]
N = Union[int, float]


def _nechad(rho, a, c):
    ssc = a * rho / (1 - (rho / c))
    return ssc


class SPMNechad:
    """Semi-analytical algorithm to retrieve SPM concentration (in mg/l) from reflectance.

    Semi-analytical algorithm to retrieve SPM concentrations (in mg/L) from
    surface reflectances (rho, unitless) or remote sensing reflectances (Rrs,
    in sr-1).
    This algorithm was presented in Nechad et al., 2010 and 2016.

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_band = 'B4'
    _default_calibration_file = wc_calib / 'spm_nechad.yaml'
    _default_calibration_name = 'Nechad_2016'
    name = 'spm-nechad'

    def __init__(self,
                 product_type: str,
                 requested_band: str = _default_band,
                 calibration: Optional[P] = None,
                 **_ignored) -> None:
        """Inits an 'SPMNechad' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_ESA_L2A or L8_USGS_L1GT).
            requested_band: Optional; The band used by the algorithm (
                default=_default_band).
            calibration: The calibration (set of parameters) used by the
                algorithm (default=_default_calibration_name).
            **_ignored: Unused kwargs sent to trash.
        """
        _, prod = get_requested_bands(algo_config=wc_algo_config,
                                      product_type=product_type,
                                      name=self.name)
        self.requested_bands = [requested_band]
        calibration_dict, calibration_name = load_calib(
            calibration,
            self._default_calibration_file,
            self._default_calibration_name
        )
        self._valid_limit = calibration_dict['validity_limit']
        try:
            params = calibration_dict[prod][
                requested_band]
        except KeyError as invalid_input:
            msg = (f'{product_type} or {requested_band} is not allowed with '
                   f'{self.name}/this calibration')
            raise InputError(msg) from invalid_input
        self.__dict__.update(params)
        self.meta = {'band': requested_band,
                     'calibration': calibration_name,
                     'validity_limit': self._valid_limit,
                     **params}

    def __call__(self,
                 rho: xr.DataArray,
                 data_type: str,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('rho').

        Args:
            rho: An array (dimension 1 * N * M) of 'data_type'.
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
                and remote sensing reflectance).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of SPM concentration (in mg/L).
        """

        if data_type == 'rrs':
            rho = np.pi * rho

        np.warnings.filterwarnings('ignore')
        # pylint: disable=no-member
        # Loaded in __init__ with "__dict__.update".
        spm = _nechad(rho, self.a, self.c)
        spm = spm.where((rho >= 0) & (spm >= 0) & (spm < self._valid_limit))
        return spm


class SPMHan:
    """Switching Semi-analytical algorithm to retrieve SPM (in mg/l) from reflectance.

    Switching Semi-analytical algorithm to retrieve suspended particulate
    matter (in mg/l) from surface reflectances (rho, unitless) or remote
    sensing reflectances (Rrs, in sr-1).
    This algorithm was published in Han et al., 2016

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'spm_han.yaml'
    _default_calibration_name = 'Han_2016'
    name = 'spm-han'

    def __init__(self,
                 product_type: str,
                 calibration: Optional[P] = None,
                 **_ignored) -> None:
        """Inits an 'SPMHan' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_ESA_L2A or L8_USGS_L1GT)
            calibration: The calibration (set of parameters) used by the
                algorithm (default=_default_calibration_name).
            **_ignored: Unused kwargs sent to trash.
        """
        self.requested_bands, prod = get_requested_bands(algo_config=wc_algo_config,
                                                         product_type=product_type,
                                                         name=self.name)
        calibration_dict, calibration_name = load_calib(
            calibration,
            self._default_calibration_file,
            self._default_calibration_name
        )
        self._valid_limit = calibration_dict['validity_limit']
        try:
            params = calibration_dict[prod]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with this calibration'
            raise InputError(msg) from invalid_product
        self.__dict__.update(params)
        self.meta = {'calibration': calibration_name,
                     'validity_limit': self._valid_limit,
                     **params}

    def __call__(self,
                 refl_red: xr.DataArray,
                 data_type: str,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('rho').

        Args:
            refl_red: An array (dimension 1 * N * M) of 'data_type'.
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
                and remote sensing reflectance).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of SPM concentration (in mg/L).
        """
        if data_type == 'rho':
            refl_red = refl_red / np.pi
            print(data_type)

        np.warnings.filterwarnings('ignore')
        rrs_red = refl_red.where(refl_red >= 0)
        # pylint: disable=no-member
        # Loaded in __init__ whit "__dict__.update".
        spm_low = _nechad(rrs_red, self.a_low, self.c_low)
        spm_high = _nechad(rrs_red, self.a_high, self.c_high)

        w_low = np.log10(self.switch_sup) - np.log10(rrs_red)
        w_high = np.log10(rrs_red) - np.log10(self.switch_inf)
        spm_mixing = (w_low * spm_low + w_high * spm_high) / (w_low + w_high)

        spm = rrs_red.where(rrs_red > self.switch_inf, spm_low)
        spm = spm.where(rrs_red < self.switch_sup, spm_high)
        spm = spm.where((rrs_red <= self.switch_inf)
                        | (rrs_red >= self.switch_sup), spm_mixing)
        spm = spm.where((spm >= 0) & (spm <= self._valid_limit))
        return spm


class SPMGet:
    """Switching Semi-analytical algorithm to retrieve SPM (in mg/l) from reflectance.

    Switching Semi-analytical algorithm to retrieve suspended particulate
    matter (in mg/l) from surface reflectances (rho, unitless) or remote
    sensing reflectances (Rrs, in sr-1).
    This algorithm was calibrated on GET radiometric database in 2018.

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'spm_get.yaml'
    _default_calibration_name = 'GET_2018'
    name = 'spm-get'

    def __init__(self,
                 product_type: str,
                 calibration: Optional[P] = None,
                 **_ignored) -> None:
        """Inits an 'SPMGet' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_ESA_L2A or L8_USGS_L1GT)
            calibration: The calibration (set of parameters) used by the
                algorithm (default=_default_calibration_name).
            **_ignored: Unused kwargs sent to trash.
        """
        self.requested_bands, prod = get_requested_bands(algo_config=wc_algo_config,
                                                         product_type=product_type,
                                                         name=self.name)
        calibration_dict, calibration_name = load_calib(
            calibration,
            self._default_calibration_file,
            self._default_calibration_name
        )
        self._switch_inf = calibration_dict['switch_inf']
        self._switch_sup = calibration_dict['switch_sup']
        self._valid_limit = calibration_dict['validity_limit']
        try:
            params = calibration_dict[prod]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with this calibration'
            raise InputError(msg) from invalid_product
        self.__dict__.update(params)
        self.meta = {'calibration': calibration_name,
                     'switch inf': self._switch_inf,
                     'switch sup': self._switch_sup,
                     'validity_limit': self._valid_limit,
                     **params}

    def __call__(self,
                 refl_red: xr.DataArray,
                 refl_nir: xr.DataArray,
                 data_type: str,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('rho').

        Args:
            refl_red: An array (dimension 1 * N * M) of 'data_type'.
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
                and remote sensing reflectance).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of SPM concentration (in mg/L).
        """
        if data_type == 'rrs':
            refl_red = np.pi * refl_red
            refl_nir = np.pi * refl_nir

        np.warnings.filterwarnings('ignore')
        rho_red = refl_red.where(refl_red >= 0)
        rho_nir = refl_red.where(refl_nir >= 0)

        # pylint: disable=no-member
        # Loaded in __init__ whit "__dict__.update".
        spm_low = _nechad(rho_red, self.a_nechad, self.c_nechad)
        spm_high = self.coef_br * np.power((rho_nir / rho_red), self.exp_br)

        w = ((rho_red - self._switch_inf)
             / (self._switch_sup - self._switch_inf))
        spm_mixing = (1 - w) * spm_low + w * spm_high

        spm = rho_red.where(rho_red > self._switch_inf, spm_low)
        spm = spm.where(rho_red < self._switch_sup, spm_high)
        spm = spm.where((rho_red <= self._switch_inf)
                        | (rho_red >= self._switch_sup), spm_mixing)
        spm = spm.where((spm >= 0) & (spm <= self._valid_limit))
        return spm


class TURBIDogliotti:
    """Switching Semi-analytical algorithm to retrieve Turbidity (in FNU) from reflectance.

    Switching Semi-analytical algorithm to retrieve Turbidity (in FNU) from
    surface reflectances (rho, unitless) or remote sensing reflectances (Rrs,
    in sr-1).
    This algorithm was published in Dogliotti et al., 2015

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'turbi_dogliotti.yaml'
    _default_calibration_name = 'Dogliotti_2015'
    name = 'turbi-dogliotti'

    def __init__(self,
                 product_type: str,
                 calibration: Optional[P] = None,
                 **_ignored) -> None:
        """Inits an 'TURBIDogliotti' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_ESA_L2A or L8_USGS_L1GT)
            calibration: The calibration (set of parameters) used by the
                algorithm (default=_default_calibration_name).
            **_ignored: Unused kwargs sent to trash.
        """
        self.requested_bands, prod = get_requested_bands(algo_config=wc_algo_config,
                                                         product_type=product_type,
                                                         name=self.name)
        calibration_dict, calibration_name = load_calib(
            calibration,
            self._default_calibration_file,
            self._default_calibration_name
        )
        self._switch_inf = calibration_dict['switch_inf']
        self._switch_sup = calibration_dict['switch_sup']
        self._valid_limit = calibration_dict['validity_limit']
        try:
            params = calibration_dict[prod]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with this calibration'
            raise InputError(msg) from invalid_product
        self.__dict__.update(params)
        self.meta = {'calibration': calibration_name,
                     'switch inf': self._switch_inf,
                     'switch sup': self._switch_sup,
                     'validity_limit': self._valid_limit,
                     **params}

    def __call__(self,
                 rho_red: xr.DataArray,
                 rho_nir: xr.DataArray,
                 data_type: str,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('rho').

        Args:
            rho_red: An array (dimension 1 * N * M) of 'data_type'.
            rho_nir: An array (dimension 1 * N * M) of 'data_type'.
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
                and remote sensing reflectance).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of Turbidity (in FNU).
        """

        if data_type == 'rrs':
            rho_red = np.pi * rho_red
            rho_nir = np.pi * rho_nir

        np.warnings.filterwarnings('ignore')
        rho_red = rho_red.where(rho_red >= 0)
        rho_nir = rho_red.where(rho_nir >= 0)
        # pylint: disable=no-member
        # Loaded in __init__ whit "__dict__.update".
        t_low = _nechad(rho_red, self.a_low, self.c_low)
        t_high = _nechad(rho_nir, self.a_high, self.c_high)
        w = ((rho_red - self._switch_inf)
             / (self._switch_sup - self._switch_inf))
        t_mixing = (1 - w) * t_low + w * t_high

        turb = rho_red.where(rho_red > self._switch_inf, t_low)
        turb = turb.where(rho_red < self._switch_sup, t_high)
        turb = turb.where((rho_red <= self._switch_inf)
                          | (rho_red >= self._switch_sup), t_mixing)
        turb = turb.where((turb >= 0) & (turb <= self._valid_limit))
        return turb
