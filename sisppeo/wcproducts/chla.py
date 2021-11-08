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

"""This module gathers wc algorithms used for estimating Chl-a concentrations.

Each class of this module correspond to one algorithm. An algorithm can have
several calibrations (a calibration is a set of parameters), either
packaged within SISPPEO (these default calibrations are located in
'resources/wc_algo_calibration') or provided by the user.
Before its utilisation, an algorithm has to be instantiate with specific
settings like the product_type of further input products, the calibration
used, the band used (if needed), etc.

Example:

    algo1 = CHLAGons('S2_GRS', 'Gons_2004')
    out_array1 = algo1(red_array, rededge_array, nir_array, 'rho')

    algo2 = CHLAGittelson('L8_GRS', '3_bands', 'Gitelson_2008')
    out_array2 = algo2(red_array, rededge_array, nir_array, 'rrs')
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


class CHLAGons:
    """Chlorophyll-a concentration (in mg/m3) from 3 red bands after Gons et al., 1999, 2002, 2004

    Red edge algorithm to retrieve Chlorophyll-a concentration (in mg/m3) from
    surface reflectances (rho, unitless) or remote sensing reflectances (Rrs,
    in sr-1) at 665nm B4 MSI, 704nm B5 MSI and 783nm B7 MSI.
    This algorithm was published in Gons et al., 1999, 2002, 2004

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'chla-gons.yaml'
    _default_calibration_name = 'Gons_2004'
    name = 'chla-gons'

    def __init__(self,
                 product_type: str,
                 calibration: Optional[P] = None,
                 **_ignored) -> None:
        """Inits an 'CHLAGons' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_ESA_L2A or L8_USGS_L1GT)
            calibration: Optional; The calibration (set of parameters) used by
                the algorithm (default=_default_calibration_name).
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
                 ref_red: xr.DataArray,
                 ref_rededge: xr.DataArray,
                 ref_nir: xr.DataArray,
                 data_type: str,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('ref').

        Args:
            ref_red: An array (dimension 1 * N * M) of 'data_type'.
            ref_redegde: An array (dimension 1 * N * M) of 'data_type'.
            ref_nir: An array (dimension 1 * N * M) of 'data_type'.
            data_type: Either 'ref' or 'rrs' (respectively surface reflectance
                and remote sensing reflectance).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of chl-a (in mg/m3).
        """

        if data_type == 'rho':
            ref_red = ref_red / np.pi
            ref_rededge = ref_rededge / np.pi
            ref_nir = ref_nir / np.pi

        np.warnings.filterwarnings('ignore')
        ref_red = ref_red.where(ref_red >= 0)
        ref_rededge = ref_rededge.where(ref_red >= 0)
        ref_nir = ref_red.where(ref_nir >= 0)

        bb783 = ref_nir.where(ref_nir >= 0).copy()
        # pylint: disable=no-member
        # Loaded in __init__ whit "__dict__.update".
        bb783 = (self.a * bb783) / (0.082 - 0.6 * bb783)
        aphy = ref_rededge / ref_red * (self.aw705 + bb783) - self.aw665 \
            - np.power(bb783, self.p)
        chla = aphy / self.aphy_star
        chla = chla.where((chla >= 0) & (chla <= self._valid_limit))
        return chla


class CHLAGitelson:
    """Chlorophyll-a concentration (in mg/m3) from 3 red bands after Gitelson et al., 2008

    Red edge algorithm to retrieve Chlorophyll-a concentration (in mg/m3) from
    surface reflectances (rho, unitless) or remote sensing reflectances (Rrs,
    in sr-1) at 665nm B4 MSI, 705nm B5 MSI and 740nm B6 MSI.
    This algorithm was published in Gitelson et al., 2008

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'chla-gitelson.yaml'
    _default_calibration_name = 'Gitelson_2008'
    _default_design = '3_bands'
    name = 'chla-gitelson'

    def __init__(self,
                 product_type: str,
                 design: str = _default_design,
                 calibration: Optional[P] = None,
                 **_ignored) -> None:
        """Inits an 'CHLAGitelson' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_ESA_L2A or L8_USGS_L1GT)
            calibration: The calibration (set of parameters) used by the
                algorithm (default=_default_calibration_name).
            **_ignored: Unused kwargs sent to trash.
        """
        self._design = design
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
                     'design': design,
                     'validity_limit': self._valid_limit,
                     **params}

    def __call__(self,
                 ref_red: xr.DataArray,
                 ref_rededge: xr.DataArray,
                 ref_nir: xr.DataArray,
                 data_type: str,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('ref').

        Args:
            ref_red: An array (dimension 1 * N * M) of 'data_type'.
            ref_redegde: An array (dimension 1 * N * M) of 'data_type'.
            ref_nir: An array (dimension 1 * N * M) of 'data_type'.
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
                and remote sensing reflectance).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of chl-a (in mg/m3).
        """

        if data_type == 'rho':
            ref_red = ref_red / np.pi
            ref_rededge = ref_rededge / np.pi
            ref_nir = ref_nir / np.pi

        np.warnings.filterwarnings('ignore')
        ref_red = ref_red.where(ref_red >= 0)
        ref_rededge = ref_rededge.where(ref_red >= 0)
        ref_nir = ref_red.where(ref_nir >= 0)
        print(self._design, self._valid_limit)
        if self._design == '3_bands':
            print('3 bands selected')
            # pylint: disable=no-member
            # Loaded in __init__ whit "__dict__.update".
            chla = self.a_3bands + self.b_3bands \
                * (1 / ref_red - 1 / ref_rededge) * ref_nir
        else:
            print('2 bands selected')
            # pylint: disable=no-member
            # Loaded in __init__ whit "__dict__.update".
            chla = self.a_2bands + self.b_2bands * (1 / ref_red) * ref_nir
        chla = chla.where((chla >= 0) & (chla <= self._valid_limit))
        return chla


class CHLAGurlin:
    """Chlorophyll-a concentration (in mg/m3) from 3 red bands after Gurlin et al., 2011

    Red edge algorithm to retrieve Chlorophyll-a concentration (in mg/m3) from
    surface reflectances (rho, unitless) or remote sensing reflectances (Rrs,
    in sr-1) at 665nm B4 MSI, 704nm B5 MSI and 783nm B7 MSI.
    This algorithm was published in Gons et al., 1999, 2002, 2004

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'chla-gurlin.yaml'
    _default_calibration_name = 'Gurlin_2011'
    name = 'chla-gurlin'

    def __init__(self,
                 product_type: str,
                 calibration: Optional[P] = None,
                 **_ignored) -> None:
        """Inits an 'CHLAGurlin' instance with specific settings.

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
                 ref_red: xr.DataArray,
                 ref_rededge: xr.DataArray,
                 data_type: str,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('ref').

        Args:
            ref_red: An array (dimension 1 * N * M) of 'data_type'.
            ref_redegde: An array (dimension 1 * N * M) of 'data_type'.
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
                and remote sensing reflectance).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of chl-a (in mg/m3).
        """
        np.warnings.filterwarnings('ignore')
        ref_red = ref_red.where(ref_red >= 0)
        ref_rededge = ref_rededge.where(ref_red >= 0)
        # pylint: disable=no-member
        # Loaded in __init__ whit "__dict__.update".
        chla = self.a * pow(ref_rededge / ref_red, 2) + self.b \
            * (ref_rededge / ref_red) + self.c
        chla = chla.where((chla >= 0) & (chla <= self._valid_limit))
        return chla


class CHLAOC:
    """Chlorophyll-a concentration (in mg/m3) from polynomial maximum band ratio by O'Reilly et al., 1998 and updates

    Blue/green algorithm to retrieve Chlorophyll-a concentration (in mg/m3) from
    surface reflectances (rho, unitless) or remote sensing reflectances (Rrs,
    in sr-1)
    This algorithm was published in O'Reilly 1998, 2000
    calibration OC2 for OLI from Franz et al., 2015, OC3 for OLI O'Reilly and Werdell, 2019
    MSI Pahlevan et al., 2020 after O'Reilly and Werdell, 2019

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'chla-oc.yaml'
    _default_calibration_name = 'OC3'
    name = 'chla-oc'

    def __init__(self,
                 product_type: str,
                 calibration: Optional[P] = None,
                 **_ignored) -> None:
        """Inits an 'CHLAOC' instance with specific settings.

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
        self._version = calibration_name
        try:
            params = calibration_dict[producttype_to_sat(product_type)]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with this calibration'
            raise InputError(msg) from invalid_product
        self.__dict__.update(params)
        self.meta = {'calibration': self._version,
                     'validity_limit': self._valid_limit,
                     **params}

    def __call__(self,
                 ref_violet: xr.DataArray,
                 ref_blue: xr.DataArray,
                 ref_green: xr.DataArray,
                 data_type: str,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('ref').

        Args:
            ref_violet: An array (dimension 1 * N * M) of 'data_type'.
            ref_blue: An array (dimension 1 * N * M) of 'data_type'.
            ref_green: An array (dimension 1 * N * M) of 'data_type'.
            data_type: Either 'ref' or 'rrs' (respectively surface reflectance
                and remote sensing reflectance).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of chl-a (in mg/m3).
        """

        np.warnings.filterwarnings('ignore')
        if data_type == 'rho':
            ref_violet = ref_violet / np.pi
            ref_blue = ref_blue / np.pi
            ref_green = ref_green / np.pi

        if self._version == 'OC3':
            print(f'{self._version} is used')
            max_ratio = np.log(np.maximum(ref_violet.values, ref_blue.values)
                               / ref_green)
            # np.log(max(Rrs_B1, Rrs_B2) / Rrs_B3))
        else:   # self._version == 'OC2'
            print(f'{self._version} is used')
            max_ratio = np.log(ref_blue.values / ref_green)
        # pylint: disable=no-member
        # Loaded in __init__ whit "__dict__.update".
        chla = np.power(10, self.a0 + self.a1 * max_ratio + self.a2
                        * np.power(max_ratio, 2) + self.a3
                        * np.power(max_ratio, 3) + self.a4
                        * np.power(max_ratio, 4))
        chla = chla.where((chla >= 0) & (chla <= self._valid_limit))
        return chla


class CHLALins:
    """Chlorophyll-a concentration (in mg/m3) from NIR/Red bands ratio after Lins et al., 2017

    Red edge algorithm to retrieve Chlorophyll-a concentration (in mg/m3) from
    surface reflectances (rho, unitless) or remote sensing reflectances (Rrs,
    in sr-1) at 665nm B4 MSI, 705nm B5 MSI
    This algorithm was published in Lins et al., 2017

    Attributes:
        name: The name of the algorithm used. This is the key used by
          L3AlgoBuilder and that you must provide in config or when using
          the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'chla-lins.yaml'
    _default_calibration_name = 'Lins_2017'
    name = 'chla-lins'

    def __init__(self,
                 product_type: str,
                 calibration: Optional[P] = None,
                 **_ignored) -> None:
        """Inits an 'CHLALins' instance with specific settings.

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
                 ref_red: xr.DataArray,
                 ref_rededge: xr.DataArray,
                 data_type: str,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('ref').

        Args:
            ref_red: An array (dimension 1 * N * M) of 'data_type'.
            ref_redegde: An array (dimension 1 * N * M) of 'data_type'.
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
                and remote sensing reflectance).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of chl-a (in mg/m3).
        """
        np.warnings.filterwarnings('ignore')
        ref_red = ref_red.where(ref_red >= 0)
        ref_rededge = ref_rededge.where(ref_red >= 0)
        # pylint: disable=no-member
        # Loaded in __init__ whit "__dict__.update".
        chla = self.p * (ref_rededge / ref_red) + self.q
        chla = chla.where((chla >= 0) & (chla <= self._valid_limit))
        return chla


class NDCI:
    """Normalized Difference Chlorophyll Index

    NDCI from surface reflectances (rho, unitless) or remote sensing reflectances (Rrs,
    in sr-1) at 665nm B4 MSI, 704nm B5 MSI

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: An empty dict, since there is no parametrisation for NDWI.
    """
    name = 'ndci'

    def __init__(self, product_type: str, **_ignored) -> None:
        """Inits an 'Ndci' instance for a given 'product_type'.

        Args:
            product_type: The type of the input satellite product (e.g.
              S2_ESA_L2A or L8_USGS_L1GT)
            **_ignored: Unused kwargs send to trash.
        """
        try:
            self.requested_bands = algo_config[self.name][
                producttype_to_sat(product_type)]
        except KeyError as unvalid_product:
            msg = f'{product_type} is not allowed with {self.name}'
            raise InputError(msg) from unvalid_product
        self.meta = {}

    def __call__(self,
                 ref_red: xr.DataArray,
                 ref_nir: xr.DataArray,
                 **_ignored) -> xr.DataArray:
        """Runs the algorithm on the input array ('ref').

        Args:
            ref_red: An array (dimension 1 * N * M) of 'data_type'.
            ref_nir: An array (dimension 1 * N * M) of 'data_type'.
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
                and remote sensing reflectance).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of NDCI values.
        """
        np.warnings.filterwarnings('ignore')
        red = ref_red.where(ref_red >= 0)
        nir = ref_nir.where(ref_nir >= 0)

        return (nir - red) / (nir + red)
