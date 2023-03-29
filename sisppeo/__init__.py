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
import sys

import shapely.speedups

# flake8: noqa: F401
from sisppeo._version import __version__
from sisppeo.main import generate
from sisppeo.utils.registration import check_algoconfig

# If the python version is too old, the code will not execute
if f'{sys.version_info[0]}.{sys.version_info[1]}' != "3.8":
    raise Exception("Python 3.8 is required.")

# Activate shapely speedups
if shapely.speedups.available:
    shapely.speedups.enable()
else:
    print('It appears there is a problem with the shapely install, disabling it for now')
    shapely.speedups.disable()
