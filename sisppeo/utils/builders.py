# Copyright 2021 Arthur Coqué, Pôle OFB-INRAE ECLA, UR RECOVER
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

"""Contains a useful function used in main.py."""

from typing import List, Tuple


def get_variables(algo_config, algo_name) -> Tuple[List[str], List[str]]:
    """Read variable (=output of a given algorithm) (long_)names from config.

    Args:
        algo_config: A configuration dict (loaded from a YAML file,
            e.g. wc_algo_config.yaml).
        algo_name: The name of the algorithm.
    """
    long_name = algo_config[algo_name]['long_name']
    output = algo_config[algo_name]['output']
    ancillary = algo_config[algo_name].get('ancillary', None)
    if isinstance(output, str):
        output = [output]
        long_name = [long_name]
    if ancillary is None:
        ancillary = []
    elif isinstance(ancillary, str):
        ancillary = [ancillary]
    return output + ancillary, long_name
