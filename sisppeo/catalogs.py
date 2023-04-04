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
"""Defines dicts containing algos, masks and readers."""
from sisppeo.readers import (C2RCCReader, GRSReader, L4USGSL1C1Reader,
                             L5USGSL1C1Reader, L7USGSL1C1Reader,
                             L8USGSL1C1Reader, LXUSGSL2Reader, S2ESAReader,
                             S2THEIAReader)
from sisppeo.utils.registration import register_algos, register_masks

algo_catalog = {}
register_algos(algo_catalog)

mask_catalog = {}
register_masks(mask_catalog)

reader_catalog = {
    'S2_ESA_L1C': S2ESAReader,
    'S2_ESA_L2A': S2ESAReader,
    'S2_THEIA': S2THEIAReader,
    'L4_GRS': GRSReader,
    'L5_GRS': GRSReader,
    'L7_GRS': GRSReader,
    'L8_GRS': GRSReader,
    'S2_GRS': GRSReader,
    'S2_C2RCC': C2RCCReader,
    'L8_C2RCC': C2RCCReader,
    'L4_USGS_L1C1': L4USGSL1C1Reader,
    'L5_USGS_L1C1': L5USGSL1C1Reader,
    'L7_USGS_L1C1': L7USGSL1C1Reader,
    'L8_USGS_L1C1': L8USGSL1C1Reader,
    'L4_USGS_L2': LXUSGSL2Reader,
    'L5_USGS_L2': LXUSGSL2Reader,
    'L7_USGS_L2': LXUSGSL2Reader,
    'L8_USGS_L2': LXUSGSL2Reader,
    'L8_USGS_L2CDRC1': LXUSGSL2Reader,
    'L8_USGS_L2CDR': LXUSGSL2Reader,
    'L8_USGS_L2THEIA': LXUSGSL2Reader,
}

sat_products = reader_catalog.keys()
theia_masks_names = ('CLM', 'MG2', 'SAT')
