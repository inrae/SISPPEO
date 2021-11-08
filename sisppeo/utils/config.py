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

"""Contains paths and configs used in other parts of the code."""

from pathlib import Path

import yaml

root = Path(__file__).parent.parent.resolve()

resources = root / 'resources'

land_calib = resources / 'land_algo_calibration'
with open(resources / 'land_algo_config.yaml', 'r') as f:
    land_algo_config = yaml.full_load(f)

wc_calib = resources / 'wc_algo_calibration'
with open(resources / 'wc_algo_config.yaml', 'r') as f:
    wc_algo_config = yaml.full_load(f)

with open(resources / 'mask_config.yaml', 'r') as f:
    mask_config = yaml.full_load(f)

with open(resources / 'sat_config.yaml', 'r') as f:
    sat_config = yaml.full_load(f)

with open(root / 'workspace.yaml', 'r') as f1:
    dict_workspace = yaml.full_load(f1)
    folder_str = dict_workspace['active_workspace']
    if folder_str is None:
        user_folder, user_algo_config, user_mask_config = None, {}, {}
    else:
        user_folder = Path(folder_str)
        if not user_folder.exists():
            print(f'The registered workspace ({folder_str}) does not exist.')
            user_folder = None
            user_algo_config = {}
            user_mask_config = {}
        else:
            with open(user_folder / 'resources/algo_config.yaml', 'r') as f2:
                user_algo_config = {} if (data := yaml.full_load(f2)) is None else data
            with open(user_folder / 'resources/mask_config.yaml', 'r') as f2:
                user_mask_config = {} if (data := yaml.full_load(f2)) is None else data
            user_calib = user_folder / 'resources/algo_calibration'
