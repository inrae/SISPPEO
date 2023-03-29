# -*- coding: utf-8 -*-
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
"""Contains various useful functions used by algorithms."""
from pathlib import Path
from typing import Tuple, Union

import yaml

from sisppeo.utils.exceptions import InputError

# pylint: disable=invalid-name
# Ok for a custom type.
P = Union[str, Path]


def load_calib(calibration: P,
               default_calibration_file: Path,
               default_calibration_name: str) -> Tuple[dict, str]:
    """Loads parameters for a given calibration name/file.

    Args:
        calibration: calibration name or path.
            1. If 'calibration' is a string, it refers to a calibration
            included in SISPPEO (this calibration name is an entry of
            the 'default_calibration_file').
            2. If 'calibration' is a path, it refers to a calibration
            given by the user, embedded in a standalone file
            (see the docs for the detailed structure of this file).
        default_calibration_file: path of the default calibration file
            (for a given algorithm).
        default_calibration_name: name of the default calibration
            (for a given algorithm).

    Returns:
        A dict of parameters (model coefficients) and the name of
        the chosen calibration.
    """
    if calibration is None:
        with open(default_calibration_file, 'r') as f:
            params = yaml.full_load(f)[default_calibration_name]
        name = default_calibration_name
    elif isinstance(calibration, str):
        with open(default_calibration_file, 'r') as f:
            params = yaml.full_load(f)[calibration]
        name = calibration
    elif isinstance(calibration, Path):
        with open(calibration, 'r') as f:
            params = yaml.full_load(f)
        name = 'custom'
    else:
        raise InputError(f'Invalid calibration: {calibration}')
    return params, name


def producttype_to_sat(product_type: str, mode: str) -> str:
    """Returns the satellite for the given product_type.

    Args:
        product_type: The type of the input satellite product
            (e.g. S2_ESA_L2A or L8_USGS_L1)

    Returns:
        The name of the satellite that matches the input product_type.
    """
    modes = ['specific', 'common']
    if mode not in modes:
        msg = f"{mode} isn't a valid parameter. Please use of the following: {modes}"
        raise InputError(msg)

    if mode == 'specific':
        return product_type.replace('_USGS_', '')
    else:
        return product_type.split('_')[0]


def get_sat_name(metadata: dict, product_type: str) -> str:
    """Returns the satellite name (e.g., 'S2A') for the given couple (metadata|product_type).

    Args:
        metadata: The dictionary in which metadata of the input
            satellite product are stored ("product_metadata.attrs").
        product_type: The type of the input satellite product
            (e.g. S2_ESA_L2A or L8_USGS_L1)
    """
    s2_names = {'Sentinel-2A': 'S2A', 'Sentinel-2B': 'S2B'}
    if product_type in ('S2_ESA_L1C', 'S2_ESA_L2A'):
        sat_name = s2_names[metadata['DATATAKE_1_SPACECRAFT_NAME']]
    elif product_type == 'S2_GRS':
        sat_name = s2_names[metadata['Level-1C_User_Product:General_Info:Product_Info:Datatake:SPACECRAFT_NAME']]
    elif product_type == 'L8_GRS':
        sat_name = producttype_to_sat(product_type)
    elif product_type == 'L7_GRS':
        sat_name = producttype_to_sat(product_type)
    elif product_type == 'L5_GRS':
        sat_name = producttype_to_sat(product_type)
    elif product_type == 'L4_GRS':
        sat_name = producttype_to_sat(product_type)
    # TODO add L4-5-7 retrieval
    else:
        print('not implemented yet')
        sat_name = None
    return sat_name
