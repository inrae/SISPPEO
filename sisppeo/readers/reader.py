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

"""This module contains the Reader class.

The Reader class is an abstract class (a blueprint) inherited by every readers.
A reader is an object used to extract bands (radiometric data) and metadata
from satellite products (or a subset of products). It also allows one to
perform resampling operations. There is a reader for each 'product_type'.
"""

from abc import ABC, abstractmethod
from collections import namedtuple
from pathlib import Path
from typing import List, Optional

import fiona
from pyproj import CRS, Transformer
from shapely.geometry import shape
from shapely.ops import transform
from shapely.wkt import loads

Inputs = namedtuple('Inputs', 'input_product requested_bands ROI')
ROI = namedtuple('ROI', 'geom srid')


class Reader(ABC):
    """Abstract class inherited by every specific reader."""

    def __init__(self,
                 input_product: Path,
                 requested_bands: List[str],
                 geom: Optional[dict] = None,
                 **_ignored) -> None:
        """Inits Reader with specific settings.

        Args:
            input_product: The path of the input product (multispectral
              spaceborne imagery).
            requested_bands: A list of bands to be extracted.
            geom: A dict containing geographical information that define the
                ROI. 4 keys: geom (a shapely.geom object), shp (a path to an
                ESRI shapefile), wkt (a path to a wkt file) and srid (an EPSG
                code).
            **_ignored: Unused kwargs sent to trash.
        """
        self._inputs = Inputs(input_product, requested_bands, _load_geom(geom))
        self._intermediate_data = {
            'data': None,
            'metadata': None,
            'x': None,
            'y': None
        }
        self.dataset = None

    @abstractmethod
    def extract_bands(self) -> None:
        """Opens the input product and extracts bands and metadata."""

    @abstractmethod
    def create_ds(self) -> None:
        """Creates a xr.Dataset out of Reader params and extracted information."""

    def _reproject_geom(self) -> None:
        transformer = Transformer.from_crs(
            self._inputs.ROI.srid,
            self._intermediate_data['crs'].to_epsg(),
            always_xy=True
        )
        self._intermediate_data['geom'] = transform(
            transformer.transform,
            self._inputs.ROI.geom
        )


def _load_geom(geom_dict):
    if geom_dict is None:
        return None
    elif (geom := geom_dict.get('geom')) is not None:
        if (srid := geom_dict.get('srid')) is None:
            srid = 4326
    elif (wkt_file := geom_dict.get('wkt')) is not None:
        with open(wkt_file, 'r') as f:
            wkt = f.readlines()[0]
        geom = loads(wkt)
        if (srid := geom_dict.get('srid')) is None:
            srid = 4326
    elif (shp_file := geom_dict.get('shp')) is not None:
        with fiona.open(shp_file) as collection:
            geom = shape(collection[0]['geometry'])
            srid = CRS.from_wkt(collection.crs_wkt).to_epsg()
    else:
        return None
    return ROI(geom, srid)
