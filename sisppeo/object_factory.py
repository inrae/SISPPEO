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

"""This module contains the ObjectFactory class.

The ObjectFactory class is an class used to store builders, algorithms and masks.
This allows a better modularity of the code by using the Factory Method
- a creational design pattern that separate the process of creating an object
from the code that depends on the interface of the object.

  Typical usage example:

  factory = ObjectFactory()
  factory.register_builder('toL3algo', L3AlgoBuilder())
  factory.register_builder('toL3mask', L3MaskBuilder())
  factory.register_builder('toTS', TimeSeriesBuilder())
  factory.register_builder(('reader', 'S2_GRS'), GRSReader)
"""
from typing import Any, Tuple, Union

# pylint: disable=invalid-name
# Ok for a custom type.
S = Union[str, Tuple[str, Any]]


class ObjectFactory:
    """Class used to store, instantiate and/or serve builders, algorithms and masks."""

    def __init__(self):
        """Inits ObjectFactory."""
        self._builders = {}

    def register_builder(self, key: S, builder) -> None:
        """Register an object inside the factory.

        It used to only store product's builder (L3algo, L3mask or TimeSeries)
        but finally it's also used to store algorithms and masks.

        Args:
            key: the key to further call the object.
            builder: the object to be registered.
        """
        self._builders[key] = builder

    def create(self, key: S, **kwargs):
        """Create (instantiate) the concrete object (stored) based on the key.

        Args:
            key: the key name to access the wanted builder/item.
            **kwargs: arguments needed to instantiate the builder/item.

        Returns:
            The wanted item (builder, algorithm...), instantiate with specific
            values.
        """
        builder = self._builders.get(key)
        if builder is None:
            raise ValueError(key)
        return builder(**kwargs)

    def serve(self, key: S):
        """Return an object stored in the factory.

        It is used with functions (no need of initialization) like masks.

        Args:
            key: the key name to access the wanted item.

        Returns:
            The wanted item (mask).
        """
        builder = self._builders.get(key)
        if builder is None:
            raise ValueError(key)
        return builder
