# -*- coding: utf-8 -*-
# Copyright 2020 Guillaume Morin, Pôle OFB-INRAE ECLA, UR RECOVER
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
"""This module gathers wc algorithms used for estimating transparency.

Each class of this module correspond to one algorithm. An algorithm can have
several calibrations (a calibration is a set of parameters), either
packaged within SISPPEO (these default calibrations are located in
'resources/wc_algo_calibration') or provided by the user.
Before its utilisation, an algorithm has to be instantiate with specific
settings like the product_type of further input products, the calibration
used, the band used (if needed), etc.

Example:

    algo1 = KDLee('S2_GRS', 'Lee_2009')
    out_array1 = algo1(red_array, rededge_array, nir_array, 'rho')

"""
from functools import partial
from pathlib import Path
from typing import List, Union

import numpy as np
import pandas as pd
import xarray as xr
from pvlib import solarposition
from pyproj import Transformer
from scipy.interpolate import griddata

from sisppeo.utils.algos import get_sat_name, load_calib
from sisppeo.utils.config import wc_algo_config, wc_calib
from sisppeo.utils.naming import get_requested_bands
from sisppeo.utils.exceptions import InputError

# pylint: disable=invalid-name
# Ok for a custom type.
P = Union[str, Path]
N = Union[int, float]


def sza(time_, lat_, lon_):
    return solarposition.get_solarposition(time=time_, latitude=lat_, longitude=lon_)['apparent_zenith'][0]


sza_vec = np.vectorize(sza)


def remove_neg(ref: xr.DataArray) -> xr.DataArray:  # OK+
    """ Returns xr.DataArray where negative values are np.nan

    :param ref: xr.DataArray of reflectances or other data
    :return: xr.DataArray results
    """
    ref_pos = xr.where(ref >= 0, ref, np.nan)
    return ref_pos


def load_ancillary_qaa_rgb(coef_name, ancillary_path, sat_name) -> pd.array:
    """ Returns pd.array of coef_name for satellite of name sat_name

        :param coef_name: coefficient name to be loaded
        :param ancillary_path: path to tabulated coefficients
        :param sat_name: satellite name
        :return: pd.array of coefficients
    """
    return pd.read_csv(ancillary_path / Path(coef_name + ".csv"), comment='#', index_col='sensor').loc[sat_name]


# TODO rename satellite in resources/ancillary/QAA-RGB
def compute_raman_scattering_correction(Rrs_B: xr.DataArray,
                                        Rrs_G: xr.DataArray,
                                        Rrs_R: xr.DataArray,
                                        blue_green_ratio: xr.DataArray,
                                        alpha: pd.array,
                                        beta1: pd.array,
                                        beta2: pd.array
                                        ) -> xr.DataArray:
    """ Computes rrs under surface @ 0- from Rrs @ 0+ in sr-1 with QAA
    following Lee et al., 2002 and updates v5 and v6 # STEP 0

    :param Rrs_B: xr.DataArray of Blue Rrs reflectances
    :param Rrs_G: xr.DataArray of Green Rrs reflectances
    :param Rrs_R: xr.DataArray of Red Rrs reflectances
    :param blue_green_ratio: xr.DataArray of scaled Blue/Green reflectances ratio
    :param alpha: pd.array of alpha raman correction coefficient
    :param beta1: pd.array of beta1 raman correction coefficient
    :param beta2: pd.array of beta2 raman correction coefficient
    """
    print(f'Raman scattering correction')
    rrs_cor_raman = []
    for i, band in enumerate([Rrs_B, Rrs_G, Rrs_R]):
        # TODO remove test print
        raman_factor = alpha[i] * blue_green_ratio + beta1[i] * Rrs_G ** beta2[i]
        rrs_cor_raman.append(band / (1 + raman_factor))
    return rrs_cor_raman


def compute_rrs(Rrs: xr.DataArray,  # OK
                T: float,
                yQ: float) -> xr.DataArray:
    """ Computes rrs under surface @ 0- from Rrs @ 0+ in sr-1 with QAA
    following Lee et al., 2002 and updates v5 and v6 # STEP 0

    :param Rrs: xr.DataArray of Rrs reflectances
    :param T: QAA rrs coefficient
    :param yQ: QAA rrs coefficient
    :return: xr.DataArray of rrs
    """
    rrs = Rrs / (T + yQ * Rrs)
    return rrs


def convert_reflectances(list_reflectances: list,
                         data_type: str) -> list:
    """ Converts Rhow to Rrs

    :param list_reflectances: list of xr.DataArray of Rrs reflectances
    :param data_type: type of data either rho or rrs
    :return: list of xr.DataArray of rrs
    """
    if data_type == 'rho':
        print("Converting reflectances : rhow to Rrs")
        list_reflectances = [x / np.pi for x in list_reflectances]
    return list_reflectances


def compute_u_wli(rrs_wli: xr.DataArray,  # OK
                  g: list) -> xr.DataArray:
    """U @ specific wl i from QAA
    following Lee et al., 2002 and updates v5 and v6 # STEP 1

    :param rrs_wli: xr.DataArray rrs at specific wl i in sr-1
    :param g: g parameter of function u
    :return: u xr.DataArray of parameter u at wl i
    """
    np.warnings.filterwarnings('ignore')
    return (- g[0] + np.sqrt(g[0] ** 2 + (4.0 * g[1] * rrs_wli))) / (2.0 * g[1])


def compute_a_wl0(rrs_44x: xr.DataArray,  # OK
                  rrs_49x: xr.DataArray,
                  rrs_5xx: xr.DataArray,
                  rrs_6xx: xr.DataArray,
                  aw_wl0: float,
                  h: list
                  ) -> xr.DataArray:
    """Total absorption @ reference wl 0 with QAA
    following Lee et al., 2002 and updates v5 and v6

    :param rrs_44x: xr.DataArray of reflectances in violet band
    :param rrs_49x: xr.DataArray of reflectances in blue band
    :param rrs_5xx: xr.DataArray of reflectances in green band
    :param rrs_6xx: xr.DataArray of reflectances in red band
    :param aw_wl0: absorption of water @ reference wl0
    :param h: h parameters following Lee et al, 2005 QAAv5
    :return: xr.DataArray of absorption at wl 0 in m-1
    """
    np.warnings.filterwarnings('ignore')
    qt = (rrs_44x + rrs_49x) / (rrs_5xx + 5 * (rrs_6xx * (rrs_6xx / rrs_49x)))
    chi = np.log10(qt)
    return aw_wl0 + np.power(10.0, (h[0] + h[1] * chi + h[2] * np.power(chi, 2)))


def compute_a_wl0_rgb(rrs_B: xr.DataArray,
                      rrs_G: xr.DataArray,
                      rrs_R: xr.DataArray,
                      chi_coefs: pd.array,
                      aw: pd.array,
                      ) -> xr.DataArray:
    """Total absorption @ reference wl 0 with QAA
    following Lee et al., 2002 and updates v5 and v6 and Pitarch et al., 2022 configuration

    :param rrs_B: xr.DataArray of reflectances in blue band
    :param rrs_G: xr.DataArray of reflectances in green band
    :param rrs_R: xr.DataArray of reflectances in red band
    :param chi_coefs: pd.array of chi polynomial scaling
    :param aw: pd.array of water absorption at R,G,B bands
    :return: xr.DataArray of total absorption at wl 0 in m-1
    """
    np.warnings.filterwarnings('ignore')
    # TODO modify formula to put Q
    func_corr_chi = np.poly1d(chi_coefs)
    chi = np.log10(2 * rrs_B / (rrs_G + 5 * (rrs_R ** 2 / rrs_B)))
    aw_tot = aw[1] + np.power(10.0, func_corr_chi(chi))
    return aw_tot


def compute_bbp_wl0(a_wl0: xr.DataArray,
                    u_wl0: xr.DataArray,
                    bw_wl0: float) -> xr.DataArray:
    """Particulate backscattering @ reference wl0 from a and u with QAA
    following Lee et al., 2002 and updates v5 and v6

    :param a_wl0: xr.DataArray total absorption at reference wl 0 in m-1
    :param u_wl0: xr.DataArray u at reference wl 0
    :param bw_wl0: scattering coefficient of water at reference wl O in m-1
    :return: xr.DataArray of backscattering at wl 0 in m-1
    """
    return ((u_wl0 * a_wl0) / (1 - u_wl0)) - (bw_wl0 / 2)


def compute_eta(blue_green_ratio: xr.DataArray,
                l: list) -> float:
    """Particulate backscattering spectral slope from blue/green ratio with QAA
    following Lee et al., 2002 and updates v5 and v6

    :param blue_green_ratio: xr.DataArray blue on green ratio
    :param l: parameters of function computing spectral slope of bb eta
    :return: spectral slope eta of bbp dimensionless []
    """
    return l[0] * (1 + l[1] * np.exp(l[2] * blue_green_ratio))


def compute_bbp(bbp_wl0: xr.DataArray,
                wl: float,
                wl0: float,
                eta: xr.DataArray) -> xr.DataArray:
    """Particulate backscattering spectral slope from blue/green ratio with QAA
    following Lee et al., 2002 and updates v5 and v6

    :param bbp_wl0: backscattering of water @ reference wl0 in m-1
    :param eta: spectral slope of bbp calculated above
    :param wl: target wavelength for bbp to be computed in nm
    :param wl0: reference wavelength wl0 in nm
    :return: Particulate backscattering at target wl in m-1
    """
    return bbp_wl0 * np.power((wl0 / wl), eta)


def compute_a(u: xr.DataArray,
              bbp_wli: xr.DataArray,
              bw_wli: float) -> xr.DataArray:
    """ Total absorption coefficient at wl i

    :param u: u from u_wli function
    :param bbp_wli: Particles Backscattering at target wli in m-1
    :param bw_wli: Scattering of water at target wli in m-1
    :return: Total absorption at target wl in m-1
    """
    return ((1 - u) * (bbp_wli + bw_wli / 2)) / u


def compute_solar_zenith_angle(coord_x: xr.DataArray,
                               coord_y: xr.DataArray,
                               time_acq: xr.DataArray,
                               epsg_product: int) -> np.ndarray:
    """ Solar Zenith Angle calculated on scene from coordinates and time of acquisition

    :param coord_x: coordinates x ref. epsg_product
    :param coord_y: coordinates y ref. epsg_product
    :param time_acq: time of acquisition
    :param epsg_product: epsg code of product
    :return: np.ndarray of SZA on scene in degree
    """
    #TODO: fix the treatment on cube timeserie dataset
    x, y, time_img = coord_x, coord_y, time_acq
    transformer = Transformer.from_crs(epsg_product, 4326)
    if len(x) == 1 and len(y) == 1 and len(time_img) == 1:
        lat_sh, lon_sh = transformer.transform(x, y)
        angles_table = sza_vec(time_img, lat_sh, lon_sh)
    else:
        res = x[1] - x[0]
        xc, yc = np.meshgrid(np.arange(x[0], x[-1] + 1, res),
                             np.arange(y[0], y[-1] - 1, -res))
        div_x, div_y = int(np.sqrt(xc.shape[0])), int(np.sqrt(xc.shape[1]))
        ind_x = np.append(np.arange(0, len(x), div_x), len(x) - 1)
        ind_y = np.append(np.arange(0, len(y), div_y), len(y) - 1)
        pos_x = [x[i] for i in ind_x]
        pos_y = [y[i] for i in ind_y]
        x_shrunk, y_shrunk = np.meshgrid(pos_x, pos_y)
        lat_sh, lon_sh = transformer.transform(x_shrunk.ravel(), y_shrunk.ravel())
        angles = sza_vec(time_img, lat_sh, lon_sh)
        angles_table = griddata((x_shrunk.ravel(), y_shrunk.ravel()), angles, (xc, yc))
    return angles_table


def compute_zsd(rrs_idx: xr.DataArray,
                kd_idx: xr.DataArray,
                Crt=0.013) -> xr.DataArray:
    """ Compute Secchi disk depth Zsd in m

        :param rrs_idx: Remote sensing reflectance at band x
        :param kd_idx: Diffuse attenuation at band x
        :param Crt: optical criterion
        :return: Secchi disk depth Zsd in m
    """
    u = np.abs(0.14 - rrs_idx.data) / Crt
    zsd_array = 1. / (2.5 * kd_idx.data) * np.log(u)
    return zsd_array


class QAALee:
    """ Quasi Analytical Algorithm QAA from Lee for retrieving IOPs
    from surface reflectances (rho, dimension less) or remote sensing reflectances (Rrs,
    in sr-1) and solar zenithal angle calculated from time and coordinates.
    This algorithm was adapted from Lee et al., 2013, 2015 with QAA from Lee et al, 2005 and updates

    Attributes:
        name: The name of the algorithm used. This is the key used by
          L3AlgoBuilder and that you must provide in config or when using
          the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'qaa-lee.yaml'
    _default_calibration_name = 'Lee_2009_QAAv5'
    name = 'qaa-lee'

    def __init__(self,
                 product_type: str,
                 calibration: P = _default_calibration_name,
                 **_ignored) -> None:
        """ Inits an 'KDLee' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_GRS, S2_ESA_L2A or L8_USGS_L1GT)
            calibration: Optional; The calibration (set of parameters) used
                by the algorithm (default=_default_calibration_name).
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
        self._product_type = product_type
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
                 ref_44x: xr.DataArray,
                 ref_49x: xr.DataArray,
                 ref_5xx: xr.DataArray,
                 ref_6xx: xr.DataArray,
                 data_type: str,
                 epsg_code: int,
                 **_ignored) -> List[xr.DataArray]:
        """Runs the algorithm on input arrays (B1 coastal aerosol, B2 blue, B3 red, B4 and green).

        Args:
            ref_443: An array (dimension 1 * N * M) of reflectances in the deep
              blue and violet part of the spectrum (B1 @ 442 nm for S2 & @ 443
              nm for L8).
            ref_490: An array (dimension 1 * N * M) of reflectances in the blue
              part of the spectrum (B2 @ 492 nm for S2 & @ 482.5 nm for L8).
            ref_5xx: An array (dimension 1 * N * M) of reflectances in the green
              part of the spectrum (B3 @ 560 nm for S2 & @ 562.5 nm for L8).
            ref_665: An array (dimension 1 * N * M) of reflectances in the red
              part of the spectrum (B4 @ 665 nm for S2 & @ 655 nm for L8).
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
              and remote sensing reflectance).
            epsg_code: epsg code from data to transform the grid coordinates into lat-lon
              for the solar zenithal angle calculation.
            **_ignored: Unused kwargs sent to trash.

        Returns:
            A list of arrays (dimension 1 * N * M) of non water absorption coefficients anw, total bacscattering
            coefficients bb and particulate backscattering coefficients bbp at several wavelengths.
        """

        print(f'Running QAALee with calibration : {self.meta["calibration"]}')

        list_reflectances = convert_reflectances([ref_44x, ref_49x, ref_5xx, ref_6xx], data_type=data_type)

        # QAA processing
        # STEP 1
        list_rrs = list(map(partial(compute_rrs, T=self.T, yQ=self.yQ), list_reflectances))
        rrs_44x, rrs_49x, rrs_5xx, rrs_6xx = list(map(remove_neg, list_rrs))
        list_rrs = list(map(remove_neg, list_rrs))
        list_u_wli = list(map(partial(compute_u_wli, g=self.g), list_rrs))
        id5xx = self.wl.index(self.wl0[0])
        id6xx = self.wl.index(self.wl0[1])

        if 'QAAv6' in self.meta['calibration']:
            print(f'Computing QAA started with QAAv 6\n!!! Beware: using QAAv6 is not recommended !!!')
            # STEP 2
            a_wl0 = xr.where(ref_6xx < 0.0015,
                             compute_a_wl0(rrs_44x, rrs_49x, rrs_5xx, rrs_6xx, self.aw[id5xx], self.h),
                             self.aw[id6xx] + self.k[0] * np.power((rrs_6xx / (rrs_44x + rrs_49x)), self.k[1]))
            # STEP 3
            bbp_wl0 = xr.where(ref_6xx < 0.0015,
                               compute_bbp_wl0(a_wl0, list_u_wli[id5xx], self.bw[id5xx]),
                               compute_bbp_wl0(a_wl0, list_u_wli[id6xx], self.bw[id6xx]))
        elif 'QAAv5' in self.meta['calibration']:
            print(f'Computing QAA started with QAAv5')
            # STEP 2
            a_wl0 = compute_a_wl0(rrs_44x, rrs_49x, rrs_5xx, rrs_6xx, self.aw[id5xx], self.h)
            # STEP 3
            bbp_wl0 = compute_bbp_wl0(a_wl0, list_u_wli[id5xx], self.bw[id5xx])
        else:
            print('precise either QAAv5 or QAAv6 in the chosen calibration')

        # STEP 5
        eta = compute_eta(rrs_44x / rrs_5xx, self.l)

        list_a_wl = []
        list_bb_wl = []
        list_bbp_wl = []
        for i, wl in enumerate(self.wl):
            print(f' - computing QAA @ {wl}[nm] with aw({wl})={self.aw[i]}[m-1], bw({wl})={self.bw[i]}[m-1]')
            # STEP 6
            if 'QAAv6' in self.meta['calibration']:
                bbp_wl = xr.where(ref_6xx < 0.0015,
                                  compute_bbp(bbp_wl0, wl, self.wl0[0], eta),
                                  compute_bbp(bbp_wl0, wl, self.wl0[1], eta))
            else:
                bbp_wl = compute_bbp(bbp_wl0, wl, self.wl0[0], eta)
            # STEP 7
            bbp_wl = bbp_wl.where((bbp_wl >= 0) & (bbp_wl <= self._valid_limit))
            bb_wl = bbp_wl + self.bw[i] / 2
            a_wl = compute_a(list_u_wli[i], bb_wl, self.bw[i])
            a_wl = a_wl.where((a_wl >= 0) & (a_wl <= self._valid_limit))
            a_wl_cor = a_wl.where(a_wl >= self.aw[i], other=self.aw[i])
            a_wl_cor = a_wl_cor.where(~np.isnan(a_wl), other=np.nan)
            a_wl_cor, bb_wl_cor, bbp_wl_cor = list(map(remove_neg, [a_wl_cor, bb_wl, bbp_wl]))
            list_a_wl += [a_wl_cor]
            list_bb_wl += [bb_wl_cor]
            list_bbp_wl += [bbp_wl_cor]
            # End of QAA process
        return list_a_wl + list_bb_wl + list_bbp_wl


class QAArgb:
    """ Quasi Analytical Algorithm QAA  from Lee adapted by Pitarch et al., 2021 to RGB channels of High Resolution Satellites
    for  retrieving IOPs from surface reflectances (rho, dimension less) or remote sensing reflectances (Rrs, in sr-1).
    This algorithm was coded following Pitarch et al., 2021 with QAA modified after Lee et al, 2005 and updates

    Attributes:
        name: The name of the algorithm used. This is the key used by
          L3AlgoBuilder and that you must provide in config or when using
          the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'qaa-rgb.yaml'
    _default_calibration_name = 'Pitarch_2021_QAArgb'
    name = 'qaa-rgb'

    def __init__(self,
                 product_type: str,
                 calibration: P = _default_calibration_name,
                 **_ignored) -> None:
        """ Inits an 'QAArgb' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_GRS, S2_ESA_L2A or L8_USGS_L1GT)
            calibration: Optional; The calibration (set of parameters) used
                by the algorithm (default=_default_calibration_name).
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
        self._product_type = product_type
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
                 ref_B: xr.DataArray,
                 ref_G: xr.DataArray,
                 ref_R: xr.DataArray,
                 data_type: str,
                 product_metadata: dict,
                 **_ignored) -> List[xr.DataArray]:
        """Runs the algorithm on input arrays (coastal aerosol, blue, red, and green).

        Args:
            ref_B: An array (dimension 1 * N * M) of reflectances in the blue
              part of the spectrum (e.g. B2 @ 492 nm for S2 & @ 482.5 nm for L8).
            ref_G: An array (dimension 1 * N * M) of reflectances in the green
              part of the spectrum (e.g. B3 @ 560 nm for S2 & @ 562.5 nm for L8).
            ref_R: An array (dimension 1 * N * M) of reflectances in the red
              part of the spectrum (e.g. B4 @ 665 nm for S2 & @ 655 nm for L8).
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
              and remote sensing reflectance).
            product_metadata: A dict inherited from Level2A product.
            **_ignored: Unused kwargs sent to trash.

        Returns:
            A list of arrays (dimension 1 * N * M) of non water absorption coefficients anw, total bacscattering
            coefficients bb and particulate backscattering coefficients bbp at blue, green and red bands.
        """

        print(f'Running QAArgb with calibration : {self.meta["calibration"]}')
        if type(product_metadata) is dict:
            sat_name = get_sat_name(product_metadata, self._product_type)
        else:
            sat_name = product_metadata
        ancillary_path = Path(__file__).parent.parent.resolve() / 'resources/ancillary/QAA_RGB/'
        idx5xx = 1 #default index of green band
        list_coefs = ['bg_ratio', 'alpha', 'beta1', 'beta2', "chi_coefs", "aw", "bbw", "central_wl"]
        bg_ratio, alpha, beta1, beta2, chi_coefs, aw, bbw, central_wl = list(
            map(partial(load_ancillary_qaa_rgb, ancillary_path=ancillary_path, sat_name=sat_name), list_coefs))

        list_reflectances = convert_reflectances([ref_B, ref_G, ref_R], data_type=data_type)

        # blue green ration scaling to avoid HRS mismatch
        func_corr_rrs_bg_ratio = np.poly1d(bg_ratio)
        blue_green_ratio = func_corr_rrs_bg_ratio(list_reflectances[0] / list_reflectances[1])

        # QAA STEP 1
        list_rrs = list(map(partial(compute_rrs, T=self.T, yQ=self.yQ), list_reflectances))
        list_rrs = list(map(remove_neg, list_rrs))
        # compute raman scattering corrections
        rrs_B, rrs_G, rrs_R = compute_raman_scattering_correction(*list_rrs, blue_green_ratio=blue_green_ratio,
                                                                  alpha=alpha, beta1=beta1, beta2=beta2)
        list_rrs = [rrs_B, rrs_G, rrs_R]
        list_u_wli = list(map(partial(compute_u_wli, g=self.g), list_rrs))
        a_wl0 = compute_a_wl0_rgb(*list_rrs, chi_coefs, aw)
        # STEP 3
        bbp_wl0 = compute_bbp_wl0(a_wl0, list_u_wli[idx5xx], bbw[idx5xx] * 2)
        # STEP 5
        eta = compute_eta(blue_green_ratio, self.l)

        list_a_wl = []
        list_bb_wl = []
        list_bbp_wl = []
        for i, wl in enumerate(central_wl):
            print(f' - computing QAA rgb @ {wl}[nm] with aw({wl})={aw[i]}[m-1], bw({wl})={bbw[i] * 2}[m-1]')
            # STEP 6
            bbp_wl = compute_bbp(bbp_wl0, wl, central_wl[1], eta)
            bbp_wl = bbp_wl.where((bbp_wl >= 0) & (bbp_wl <= self._valid_limit))
            bb_wl = bbp_wl + bbw[i]
            a_wl = compute_a(list_u_wli[i], bb_wl, bbw[i] * 2)
            a_wl = a_wl.where((a_wl >= 0) & (a_wl <= self._valid_limit))
            a_wl_cor = a_wl.where(a_wl >= aw[i], other=aw[i])
            a_wl_cor = a_wl_cor.where(~np.isnan(a_wl), other=np.nan)
            a_wl_cor, bb_wl_cor, bbp_wl_cor = list(map(remove_neg, [a_wl_cor, bb_wl, bbp_wl]))
            list_a_wl += [a_wl_cor]
            list_bb_wl += [bb_wl_cor]
            list_bbp_wl += [bbp_wl_cor]
        return list_a_wl + list_bb_wl + list_bbp_wl


class KDLee:
    """ Diffuse attenuation coefficient for downwelling irradiance Kd at visible bands
    from surface reflectances (rho, dimension less) or remote sensing reflectances (Rrs,
    in sr-1) and solar zenithal angle calculated from time and coordinates.
    This algorithm was adapted from Lee et al., 2013, 2015 with QAA from Lee et al, 2005 and updates

    Attributes:
        name: The name of the algorithm used. This is the key used by
          L3AlgoBuilder and that you must provide in config or when using
          the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'kd-lee.yaml'
    _default_calibration_name = 'Lee_2013_QAAv5'
    name = 'kd-lee'

    def __init__(self,
                 product_type: str,
                 calibration: P = _default_calibration_name,
                 **_ignored) -> None:
        """ Inits an 'KDLee' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_GRS, S2_ESA_L2A or L8_USGS_L1GT)
            calibration: Optional; The calibration (set of parameters) used
                by the algorithm (default=_default_calibration_name).
                Required informations in calibration yaml:
                Version_name:
                    qaa_version: "required" qaa_version_name set in qaa yaml for a correct switching in QAAversion processing
                    validity_limit: "required"
                    sat_key:
                        wl: "required" list of wl
                        bw: "required" list of bw @ wl
                        gamma: "required" integer
                        m: "required" list of param from Lee et al., 2013 for Kd equation
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
        self._qaa_version = calibration_dict['qaa_version']
        self._product_type = product_type
        try:
            params = calibration_dict[prod]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with this calibration'
            raise InputError(msg) from invalid_product
        self.__dict__.update(params)
        self.meta = {'calibration': calibration_name,
                     'validity_limit': self._valid_limit,
                     'qaa_version': self._qaa_version,
                     **params}

    def __call__(self,
                 ref_44x: xr.DataArray,
                 ref_49x: xr.DataArray,
                 ref_5xx: xr.DataArray,
                 ref_6xx: xr.DataArray,
                 data_type: str,
                 epsg_code: int,
                 product_metadata: dict,
                 **_ignored) -> List[xr.DataArray]:
        """Runs the algorithm on input arrays (coastal aerosol, blue, red, and green).

        Args:
            ref_443: An array (dimension 1 * N * M) of reflectances in the deep
              blue and violet part of the spectrum (B1 @ 442 nm for S2 & @ 443
              nm for L8).
            ref_490: An array (dimension 1 * N * M) of reflectances in the blue
              part of the spectrum (B2 @ 492 nm for S2 & @ 482.5 nm for L8).
            ref_5xx: An array (dimension 1 * N * M) of reflectances in the green
              part of the spectrum (B3 @ 560 nm for S2 & @ 562.5 nm for L8).
            ref_665: An array (dimension 1 * N * M) of reflectances in the red
              part of the spectrum (B4 @ 665 nm for S2 & @ 655 nm for L8).
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
              and remote sensing reflectance).
            epsg_code: epsg code from data to transform the grid coordinates into lat-lon
              for the solar zenithal angle calculation.
            product_metadata: A dict inherited from Level2A product.
            **_ignored: Unused kwargs sent to trash.

        Returns:
            A list of arrays (dimension 1 * N * M) of diffuse attenuation coefficients Kd at several wavelengths..
        """
        print(f'Running KDLee with calibration {self.meta["calibration"]}')
        print(f'calling QAALee with calibration {self._qaa_version}')

        list_reflectances = convert_reflectances([ref_44x, ref_49x, ref_5xx, ref_6xx], data_type=data_type)

        self.qaa = QAALee(product_type=self._product_type, calibration=self._qaa_version)  # self.meta['qaa_version']
        list_qaa_all_bands = self.qaa(*list_reflectances, 'rrs', epsg_code)
        print('Computing kd started')
        print('computing solar zenithal angle')
        sza_table = compute_solar_zenith_angle(ref_5xx.x, ref_5xx.y, ref_5xx.time, epsg_code)

        list_kd = []
        for i, wl in enumerate(self.wl):
            print(f' - computing Kd @ {wl}[nm] with bw({wl})={self.bw[i]}[m-1]')
            a_wl, bb_wl = list_qaa_all_bands[i], list_qaa_all_bands[i + len(list_reflectances)]
            # bb_wl = bbp_wl + self.bw[i] / 2 # to be added if bb is not available from qaa output
            kd = (1 + self.m[0] * sza_table) * a_wl + self.m[1] * (1 - self.gamma * (self.bw[i] / 2) / bb_wl) * (
                    1 - self.m[2] * np.exp(-self.m[3] * a_wl)) * bb_wl
            kd = remove_neg(kd)
            kd = kd.where(kd <= self._valid_limit)
            list_kd.append(kd)
        return list_kd


class KDrgb:
    """ Diffuse attenuation coefficient for downwelling irradiance Kd at blue, green, red bands
    from surface reflectances (rho, dimension less) or remote sensing reflectances (Rrs,
    in sr-1) and solar zenithal angle calculated from time and coordinates.
    This algorithm was adapted from Lee et al., 2013 with QAArgb from Pitarch et al, 2021

    Attributes:
        name: The name of the algorithm used. This is the key used by
          L3AlgoBuilder and that you must provide in config or when using
          the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'kd-rgb.yaml'
    _default_calibration_name = 'Lee_2013_QAArgb'
    name = 'kd-rgb'

    def __init__(self,
                 product_type: str,
                 calibration: P = _default_calibration_name,
                 **_ignored) -> None:
        """ Inits an 'KDLee' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_GRS, S2_ESA_L2A or L8_USGS_L1GT)
            calibration: Optional; The calibration (set of parameters) used
                by the algorithm (default=_default_calibration_name).
                Required informations in calibration yaml:
                Version_name:
                    qaa_version: "required" qaa_version_name set in qaa yaml for a correct switching in QAAversion processing
                    validity_limit: "required"
                    sat_key:
                        gamma: "required" integer
                        m: "required" list of param from Lee et al., 2013 for Kd equation
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
        self._qaa_version = calibration_dict['qaa_version']
        self._product_type = product_type
        try:
            params = calibration_dict[prod]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with this calibration'
            raise InputError(msg) from invalid_product
        self.__dict__.update(params)
        self.meta = {'calibration': calibration_name,
                     'validity_limit': self._valid_limit,
                     'qaa_version': self._qaa_version,
                     **params}

    def __call__(self,
                 ref_B: xr.DataArray,
                 ref_G: xr.DataArray,
                 ref_R: xr.DataArray,
                 data_type: str,
                 product_metadata: dict,
                 **_ignored) -> List[xr.DataArray]:
        """Runs the algorithm on input arrays (Blue, Green, Red).

        Args:
            ref_B: An array (dimension 1 * N * M) of reflectances in the blue
              part of the spectrum (B2 @ 492 nm for S2 & @ 482.5 nm for L8).
            ref_G: An array (dimension 1 * N * M) of reflectances in the green
              part of the spectrum (B3 @ 560 nm for S2 & @ 562.5 nm for L8).
            ref_R: An array (dimension 1 * N * M) of reflectances in the red
              part of the spectrum (B4 @ 665 nm for S2 & @ 655 nm for L8).
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
              and remote sensing reflectance).
            product_metadata: A dict inherited from Level2A product.
            **_ignored: Unused kwargs sent to trash.

        Returns:
            A list of arrays (dimension 1 * N * M) of diffuse attenuation coefficients Kd at blue, green, red bands.
        """

        print(f'Running KDrgb with calibration {self.meta["calibration"]}')
        print(f'calling QAArgb with calibration {self._qaa_version}')
        if type(product_metadata) is dict:
            sat_name = get_sat_name(product_metadata, self._product_type)
        else:
            sat_name = product_metadata
        ancillary_path = Path(__file__).parent.parent.resolve() / 'resources/ancillary/QAA_RGB/'
        list_coefs = ["bbw", "central_wl"]
        bbw, central_wl = list(map(partial(load_ancillary_qaa_rgb, ancillary_path=ancillary_path, sat_name=sat_name),
                                   list_coefs))

        idx5xx = 1 # default green band index

        list_reflectances = convert_reflectances([ref_B, ref_G, ref_R], data_type=data_type)

        self.qaa = QAArgb(product_type=self._product_type, calibration=self._qaa_version)
        list_qaa_outputs = self.qaa(*list_reflectances, data_type='rrs', product_metadata=product_metadata)

        print('Computing kd started')
        list_kd = []
        for i, wl in enumerate(central_wl):
            print(f' - computing Kd @ {wl}[nm] with bw({wl})={bbw[i] * 2}[m-1]')
            a_wl, bb_wl = list_qaa_outputs[i], list_qaa_outputs[i + len(list_reflectances)]
            # bb_wl = bbp_wl + self.bw[i] / 2 # to be added if bb is not available from qaa output
            kd = a_wl + self.m[1] * (1 - self.gamma * bbw[i] / bb_wl) * (
                    1 - self.m[2] * np.exp(-self.m[3] * a_wl)) * bb_wl
            kd = remove_neg(kd)
            kd = kd.where(kd <= self._valid_limit)
            list_kd.append(kd)
        return list_kd


class ZSDLee:
    """ Secchi disk depth from surface reflectances (rho, dimension less) or remote sensing reflectances (Rrs,
    in sr-1) and solar zenithal angle calculated from time and coordinates.
    This algorithm was adapted from Lee et al., 2015, 2016 with QAA from Lee et al, 2005 and updates

    Attributes:
        name: The name of the algorithm used. This is the key used by
          L3AlgoBuilder and that you must provide in config or when using
          the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'zsd-lee.yaml'
    _default_calibration_name = 'Lee_2015_QAAv5'
    name = 'zsd-lee'

    def __init__(self,
                 product_type: str,
                 calibration: P = _default_calibration_name,
                 **_ignored) -> None:
        """ Inits an 'ZSDLee' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_GRS, S2_ESA_L2A or L8_USGS_L1GT)
            calibration: Optional; The calibration (set of parameters) used
                by the algorithm (default=_default_calibration_name).
                Required informations in calibration yaml:
                Version_name:
                    kd_version: "required" kd_version_name set in kd yaml for a correct switching to the desired QAAversion processing
                    validity_limit: "required" integer
                    sat_key:
                        wl: "required" list of central wavelengths
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
        self._kd_version = calibration_dict['kd_version']
        self._product_type = product_type
        try:
            params = calibration_dict[prod]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with this calibration'
            raise InputError(msg) from invalid_product
        self.__dict__.update(params)
        self.meta = {'calibration': calibration_name,
                     'validity_limit': self._valid_limit,
                     'kd_version': self._kd_version,
                     **params}

    def __call__(self,
                 ref_44x: xr.DataArray,
                 ref_49x: xr.DataArray,
                 ref_5xx: xr.DataArray,
                 ref_6xx: xr.DataArray,
                 data_type: str,
                 epsg_code: int,
                 product_metadata: dict,
                 **_ignored) -> List[xr.DataArray]:
        """Runs the algorithm on input arrays (coastal aerosol, blue, red, and green).

        Args:
            ref_443: An array (dimension 1 * N * M) of reflectances in the deep
              blue and violet part of the spectrum (B1 @ 442 nm for S2 & @ 443
              nm for L8).
            ref_490: An array (dimension 1 * N * M) of reflectances in the blue
              part of the spectrum (B2 @ 492 nm for S2 & @ 482.5 nm for
              L8).
            ref_5xx: An array (dimension 1 * N * M) of reflectances in the green
              part of the spectrum (B3 @ 560 nm for S2 & @ 562.5 nm for L8).
            ref_665: An array (dimension 1 * N * M) of reflectances in the red
              part of the spectrum (B4 @ 665 nm for S2 & @ 655 nm for L8).
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
              and remote sensing reflectance).
            epsg_code: epsg code from data to transform the grid coordinates into lat-lon
              for the solar zenithal angle calculation.
            product_metadata: A dict inherited from Level2A product.
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An arrar (dimension 1 * N * M) of Secchi disk depth Zsd (in m).
        """

        print(f'Running ZSDLee with calibration {self.meta["calibration"]}')
        print(f'calling KDLee with calibration {self._kd_version}')
        if type(product_metadata) is dict:
            sat_name = get_sat_name(product_metadata, self._product_type)
        else:
            sat_name = product_metadata

        list_reflectances = convert_reflectances([ref_44x, ref_49x, ref_5xx, ref_6xx], data_type=data_type)

        print('Computing zsd started')
        self.kd = KDLee(product_type=self._product_type, calibration=self._kd_version)
        list_kd_all_bands = self.kd(*list_reflectances, 'rrs', epsg_code,
                                    product_metadata=product_metadata)
        # used for later coordinates propagation
        data_time, data_x, data_y = list_reflectances[0].time, list_reflectances[0].x, list_reflectances[0].y
        # kd_da and rrs_da are concatenated DataArrays of kd and rrs at 4 bands with time dropped
        rrs_da = xr.concat(list_reflectances, dim='bands')
        #rrs_da = rrs_da.isel(time=0)

        kd_da = xr.concat(list_kd_all_bands, dim='bands')
        #kd_da = kd_da.isel(time=0)
        kd_da = kd_da.where(~np.isnan(kd_da), 1000)
        # creates a mask where existing kd = 1 and else 0
        mask_kd = kd_da.sum(dim='bands')
        nan_value = 1000 * len(list_reflectances)
        mask_kd = mask_kd.where(mask_kd == nan_value, 1).where(mask_kd < nan_value, 0)
        # find and return the index of the minimum kd between bands
        argmin_kd_da = kd_da.argmin(dim="bands", skipna=True).rename('idx')
        argmin_kd_da = argmin_kd_da.where(mask_kd != 0)

        # creates the da for storing results
        zsd_res = xr.DataArray(data=-1000, dims=["time", "y", "x"], coords=[data_time, data_y, data_x])
        for idx in np.arange(len(list_reflectances)):
            print(f' - computing Zsd @ {self.wl[idx]}[nm]')
            zsd_values = compute_zsd(rrs_da.isel(bands=idx), kd_da.isel(bands=idx))
            zsd_idx = xr.DataArray(zsd_values, dims=["time", "y", "x"], coords=[data_time, data_y, data_x])
            # creates the da for the band idx at px set in argmin_kd_da
            zsd_array = zsd_idx.where(argmin_kd_da == idx)
            # incrementally implement the zsd at band idx in the product
            zsd_res = zsd_res.where((argmin_kd_da != idx) | (zsd_res > 0), zsd_array)
        print(f'successfully combined Zsd for final product')
        # masks the result
        zsd = zsd_res.where(mask_kd == 1).where(zsd_res > 0)
        return zsd


class ZSDrgb:
    """ Secchi disk depth from surface reflectances (rho, dimension less) or remote sensing reflectances (Rrs,
    in sr-1).
    This algorithm was adapted from Lee et al., 2015, 2016 with QAArgb by Pitarch et al., 2021 after Lee et al, 2005 and updates

    Attributes:
        name: The name of the algorithm used. This is the key used by
          L3AlgoBuilder and that you must provide in config or when using
          the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = wc_calib / 'zsd-rgb.yaml'
    _default_calibration_name = 'Pitarch_2021_QAArgb'
    name = 'zsd-rgb'

    def __init__(self,
                 product_type: str,
                 calibration: P = _default_calibration_name,
                 **_ignored) -> None:
        """ Inits an 'ZSDrgb' instance with specific settings.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_GRS, S2_ESA_L2A or L8_USGS_L1GT)
            calibration: Optional; The calibration (set of parameters) used
                by the algorithm (default=_default_calibration_name).
                Required informations in calibration yaml:
                Version_name:
                    kd_version: "required" kd_version_name set in kd yaml for a correct switching to the desired QAAversion processing
                    validity_limit: "required" integer
                    sat_key: available satellite
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
        self._kd_version = calibration_dict['kd_version']
        self._product_type = product_type
        try:
            params = calibration_dict[prod]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with this calibration'
            raise InputError(msg) from invalid_product
        self.__dict__.update(params)
        self.meta = {'calibration': calibration_name,
                     'validity_limit': self._valid_limit,
                     'kd_version': self._kd_version,
                     **params}

    def __call__(self,
                 ref_B: xr.DataArray,
                 ref_G: xr.DataArray,
                 ref_R: xr.DataArray,
                 data_type: str,
                 product_metadata: dict,
                 **_ignored) -> List[xr.DataArray]:
        """Runs the algorithm on input arrays (coastal aerosol, blue, red, and green).

        Args:
            ref_B: An array (dimension 1 * N * M) of reflectances in the blue
              part of the spectrum (B2 @ 492 nm for S2 & @ 482.5 nm for
              L8).
            ref_G: An array (dimension 1 * N * M) of reflectances in the green
              part of the spectrum (B3 @ 560 nm for S2 & @ 562.5 nm for L8).
            ref_R: An array (dimension 1 * N * M) of reflectances in the red
              part of the spectrum (B4 @ 665 nm for S2 & @ 655 nm for L8).
            data_type: Either 'rho' or 'rrs' (respectively surface reflectance
              and remote sensing reflectance).
            product_metadata: A dict inherited from Level2A product.
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An array (dimension 1 * N * M) of Secchi disk depth Zsd (in m).
        """
        #[print(f"{i}") for i in product_metadata.items()]
        print(f'Running ZSDrgb with calibration {self.meta["calibration"]}')
        print(f'calling KDrgb with calibration {self._kd_version}')
        if type(product_metadata) is dict:
            sat_name = get_sat_name(product_metadata, self._product_type)
        else:
            sat_name = product_metadata
        ancillary_path = Path(__file__).parent.parent.resolve() / 'resources/ancillary/QAA_RGB/'
        list_coefs = ["zsd_coefs", "central_wl"]
        zsd_coefs, central_wl = list(map(partial(load_ancillary_qaa_rgb, ancillary_path=ancillary_path, sat_name=sat_name),
                                   list_coefs))
        list_reflectances = convert_reflectances([ref_B, ref_G, ref_R], data_type=data_type)

        self.kd = KDrgb(product_type=self._product_type, calibration=self._kd_version, )
        list_kd_all_bands = self.kd(*list_reflectances, 'rrs', product_metadata=product_metadata)

        print('Computing zsd started')
        # used for later coordinates propagation
        data_time, data_x, data_y = list_reflectances[0].time, list_reflectances[0].x, list_reflectances[0].y
        # kd_da and rrs_da are concatenated DataArrays of kd and rrs at 4 bands with time dropped
        rrs_da = xr.concat(list_reflectances, dim='bands')
        #rrs_da = rrs_da.isel(time=0)

        kd_da = xr.concat(list_kd_all_bands, dim='bands')
        #kd_da = kd_da.isel(time=0)
        kd_da = kd_da.where(~np.isnan(kd_da), 1000)
        # creates a mask where all existing kd == 1 and else == 0
        mask_kd = kd_da.sum(dim='bands')
        nan_value = 1000 * len(list_reflectances)
        mask_kd = mask_kd.where(mask_kd == nan_value, 1).where(mask_kd < nan_value, 0)
        # find and return the index of the minimum kd between bands
        argmin_kd_da = kd_da.argmin(dim="bands", skipna=True).rename('idx')
        argmin_kd_da = argmin_kd_da.where(mask_kd != 0)

        # creates the da for storing results
        zsd_res = xr.DataArray(data=-1000, dims=["time", "y", "x"], coords=[data_time, data_y, data_x])
        for idx in np.arange(len(list_reflectances)):
            print(f' - computing Zsd @ {central_wl[idx]}[nm]')
            zsd_values = compute_zsd(rrs_da.isel(bands=idx), kd_da.isel(bands=idx))
            zsd_idx = xr.DataArray(zsd_values, dims=["time", "y", "x"], coords=[data_time, data_y, data_x])
            # creates the da for the band idx at px set in argmin_kd_da
            zsd_array = zsd_idx.where(argmin_kd_da == idx)
            # incrementally implement the zsd at band idx in the product
            zsd_res = zsd_res.where((argmin_kd_da != idx) | (zsd_res > 0), zsd_array)
        print(f'successfully combined Zsd for final product')
        # rescaling to avoid HRS mismatch
        func_corr_zsd = np.poly1d(zsd_coefs)
        zsd_res.data = func_corr_zsd(zsd_res)
        # masks the result
        zsd = zsd_res.where(mask_kd == 1).where(zsd_res > 0)
        return zsd
