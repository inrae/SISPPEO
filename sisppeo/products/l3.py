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

"""This module gathers classes related to L3 products.

In this module are defined L3 products : the abstract class L3Product and its
child classes L3AlgoProduct and L3MaskProduct. Basically, these classes wrap
a well formated xarray Dataset and offer a few useful methods.

Example::

    S2_ndvi = L3AlgoProduct(dataset)
    S2_ndvi.plot()
    S2_ndvi.save(path_to_file)

    s2cloudless_mask = L3MaskProduct(dataset)
    s2cloudless_mask.save(path_to_file)
"""

import warnings
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import xarray as xr
from matplotlib import pyplot as plt

from sisppeo.utils.exceptions import InputError
from sisppeo.utils.products import CoordinatesMixin, get_enc

warnings.filterwarnings('ignore', category=xr.SerializationWarning)

# pylint: disable=invalid-name
# Ok for a custom type.
N = Union[int, float]
P = List[Union[Path, str]]


@dataclass
class L3Product(ABC, CoordinatesMixin):
    """Abstract class inherited by both L3AlgoProduct and L3MaskProduct.

    Attributes:
        dataset: A dataset containing processed data.
    """
    __slots__ = 'dataset',
    dataset: xr.Dataset

    @classmethod
    @abstractmethod
    def from_file(cls, filename: Union[str, Path]):
        """Loads and returns a L3Product from file.

        Args:
            filename: The path to the L3Product (saved as a netCDF file).
        """

    @property
    def title(self) -> str:
        """Returns the title of the underlying dataset."""
        return self.dataset.attrs['title']

    @property
    def product_type(self) -> str:
        """Returns the product_type of the product used to get this dataset."""
        return self.dataset.attrs['title'].rsplit(' ', 1)[1]

    @property
    def data_vars(self):
        """Returns a list of DataArrays corresponding to variables."""
        return [data_var for data_var in self.dataset.data_vars
                if data_var not in ('crs', 'product_metadata')]

    def plot(self, data_var) -> None:
        """Plots a given variable.

        data_var: The name of the variable/DataArray of interest (e.g., a
                band, aCDOM, etc).
        """
        if data_var not in self.data_vars:
            msg = (f'"{data_var}" is not a variable of this product; please, '
                   f'choose one from the following list: {self.data_vars}.')
            raise InputError(msg)
        self.dataset[data_var].plot()
        plt.show()

    @abstractmethod
    def save(self, filename: P) -> None:
        """Saves this product into a netCDF file.

        Args:
            filename: Path of the output file.
        """


@dataclass
class L3AlgoProduct(L3Product):
    """An L3Product embedding data obtained by using a wc/land algorithm.

    Attributes:
        dataset: A dataset containing processed data.
    """
    __slots__ = ()

    @classmethod
    def from_file(cls, filename):
        return L3AlgoProduct(xr.open_dataset(filename))

    @property
    def algo(self) -> str:
        """Returns the name of the algorithm used to get this dataset."""
        return self.title.split(' ', 1)[0]

    def save(self, filename: P) -> None:
        """See base class."""
        enc = {data_var: get_enc(self.dataset[data_var].values, 0.001, True)
               for data_var in self.data_vars}
        enc.update({
            'crs': {'dtype': 'byte'},
            'product_metadata': {'dtype': 'byte'},
            'x': get_enc(self.dataset.x.values, 0.1),
            'y': get_enc(self.dataset.y.values, 0.1)
        })
        self.dataset.to_netcdf(filename, encoding=enc)


@dataclass
class L3MaskProduct(L3Product):
    """An L3Product embedding data obtained by using a mask algorithm.

    Attributes:
        dataset: A dataset containing processed data.
    """
    __slots__ = ()

    @classmethod
    def from_file(cls, filename):
        return L3MaskProduct(xr.open_dataset(filename))

    @property
    def mask(self):
        """Returns the name of the mask used to get this dataset."""
        return self.title.split(' ', 1)[0]

    def save(self, filename: Union[Path, str]) -> None:
        """See base class."""
        self.dataset.to_netcdf(filename, encoding={
                self.mask: {'dtype': 'bool'},
                'crs': {'dtype': 'byte'},
                'product_metadata': {'dtype': 'byte'},
                'x': {'dtype': 'int32'},
                'y': {'dtype': 'int32'}
            })


def mask_product(l3_algo: L3AlgoProduct,
                 l3_masks: Union[L3MaskProduct, List[L3MaskProduct]],
                 lst_mask_type: Union[str, List[str]],
                 inplace=False) -> Optional[L3AlgoProduct]:
    """Masks an L3AlgoProduct.

    Masks an L3AlgoProduct with one or more L3MaskProducts. It can be used for
    instance to get rid of clouds or to extract only water areas.

    Args:
        l3_algo: The L3AlgoProduct to be masked.
        l3_masks: The mask or list of masks to use.
        lst_mask_type: The type of the input mask (or the list of the types of
            input masks). Can either be 'IN' or 'OUT', indicating if the
            corresponding mask is inclusive or exclusive.
        inplace: If True, do operation inplace and return None.

    Returns:
        A masked L3AlgoProduct.
    """
    if not inplace:
        l3_algo = deepcopy(l3_algo)
    if isinstance(l3_masks, L3MaskProduct):
        l3_masks = [l3_masks]
    if isinstance(lst_mask_type, str):
        lst_mask_type = [lst_mask_type]
    # Get the shared bounding box (i.e. intersection)
    x_min = max([l3_mask.x.values.min() for l3_mask in l3_masks]
                + [l3_algo.x.values.min()])
    x_max = min([l3_mask.x.values.max() for l3_mask in l3_masks]
                + [l3_algo.x.values.max()])
    y_min = max([l3_mask.y.values.min() for l3_mask in l3_masks]
                + [l3_algo.y.values.min()])
    y_max = min([l3_mask.y.values.max() for l3_mask in l3_masks]
                + [l3_algo.y.values.max()])
    # Clip masks with the previous bounding box
    arr_masks = [l3_mask.dataset[l3_mask.mask].sel(
        x=slice(x_min, x_max), y=slice(y_max, y_min)).values
        for l3_mask in l3_masks]
    # Merge 'IN' masks (<=> what to include)
    idx_in = [i for i, mask_type in enumerate(lst_mask_type)
              if mask_type.upper() == 'IN']
    mask_in = np.sum([arr_masks[i] for i in idx_in], axis=0)
    # Merge 'OUT' masks (<=> what to exclude)
    idx_out = [i for i, mask_type in enumerate(lst_mask_type)
               if mask_type.upper() == 'OUT']
    mask_out = np.sum([arr_masks[i] for i in idx_out], axis=0)
    # Create the final mask
    if not idx_in:
        mask = np.where(mask_out == 0, True, False)
    elif not idx_out:
        mask = np.where(mask_in > 0, True, False)
    else:
        mask = np.where((mask_in > 0) & (mask_out == 0), True, False)
    # Apply the previously computed mask to the product
    l3_algo.dataset = l3_algo.dataset.sel(x=slice(x_min, x_max),
                                          y=slice(y_max, y_min))
    for var in l3_algo.data_vars:
        l3_algo.dataset[var].values = np.where(
            mask, l3_algo.dataset[var].values, np.nan
        )
    # Store masks' names
    masks = []
    dico = {'s2cloudless': 'cloudmask', 'waterdetect': 'watermask'}
    for l3_mask, mask_type in zip(l3_masks, lst_mask_type):
        if l3_mask.mask in ('s2cloudless', 'waterdetect'):
            version = l3_mask.dataset[l3_mask.mask].attrs['version']
            l3_algo.dataset.attrs[dico[l3_mask.mask]] = f'{l3_mask.mask} ({version}) [{mask_type}]'
        else:
            masks.append(f'{l3_mask.mask} [{mask_type}]')
    if masks:
        l3_algo.dataset.attrs['masks'] = masks
    if not inplace:
        return l3_algo
    return None
