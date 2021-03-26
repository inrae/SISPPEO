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

"""In this module are defined object factories containing algos, masks and readers."""

from sisppeo.object_factory import ObjectFactory
from sisppeo.readers import (GRSReader, L8USGSL1C1Reader, L8USGSL2Reader,
                             S2ESAReader, S2THEIAReader)
from sisppeo.utils.registration import (register_algos, register_masks)

algo_catalog = ObjectFactory()
register_algos(algo_catalog)

mask_catalog = ObjectFactory()
register_masks(mask_catalog)

reader_catalog = ObjectFactory()
reader_catalog.register_builder('S2_ESA_L1C', S2ESAReader)
reader_catalog.register_builder('S2_ESA_L2A', S2ESAReader)
reader_catalog.register_builder('S2_THEIA', S2THEIAReader)
reader_catalog.register_builder('L8_GRS', GRSReader)
reader_catalog.register_builder('S2_GRS', GRSReader)
reader_catalog.register_builder('L8_USGS_L1C1', L8USGSL1C1Reader)
reader_catalog.register_builder('L8_USGS_L2', L8USGSL2Reader)
