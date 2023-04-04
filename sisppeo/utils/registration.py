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

"""Contains functions related to algorithm&mask registration."""

import importlib.util
import sys
from inspect import getmembers, isclass

import sisppeo.landproducts as land_algos
import sisppeo.masks as masks
import sisppeo.wcproducts as wc_algos
from sisppeo.utils.config import (land_algo_config, mask_config,
                                  user_algo_config, user_folder,
                                  user_mask_config, wc_algo_config)

land_algo_classes = getmembers(land_algos, isclass)
wc_algo_classes = getmembers(wc_algos, isclass)
mask_classes = getmembers(masks, isclass)


def _import_from_sourcefile(modname, dirname, filename):
    spec = importlib.util.spec_from_file_location(
        modname, dirname / f'{filename}/__init__.py'
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


user_algo_classes = []
user_mask_classes = []
if user_folder is not None:
    try:
        user_algos = _import_from_sourcefile('user_algos', user_folder,
                                             'custom_algorithms')
        user_algo_classes = getmembers(user_algos, isclass)
        vanilla_algo_names = [_[1].name for _ in land_algo_classes
                              + wc_algo_classes]
        for algo in [e for _ in user_algo_classes if (e := _[1].name)
                     in vanilla_algo_names]:
            print(f'An algorithm with a similar name ("{algo}") is already '
                  'provided with SISPPEO. Please, rename your algorithm to be '
                  'able to use it.')
        user_algo_classes = [_ for _ in user_algo_classes if _[1].name
                             not in vanilla_algo_names]
    except FileNotFoundError:
        print('Custom algorithms must be put in the '
              '"<user_folder>/custom_algorithms" package.')
        raise
    try:
        user_masks = _import_from_sourcefile('user_masks', user_folder,
                                             'custom_masks')
        user_mask_classes = getmembers(user_masks, isclass)
        vanilla_mask_names = [_[1].name for _ in mask_classes]
        for mask in [e for _ in user_mask_classes if (e := _[1].name)
                     in vanilla_mask_names]:
            print(f'A mask with a similar name ("{mask}") is already '
                  'provided with SISPPEO. Please, rename your mask to be able '
                  'to use it.')
        user_mask_classes = [_ for _ in user_mask_classes if _[1].name
                             not in vanilla_mask_names]
    except FileNotFoundError:
        print('Custom masks must be put in the "<user_folder>/custom_masks" '
              'package.')
        raise


def check_algoconfig() -> None:
    """Print a warning message if an algorithm lacks its configuration file."""
    unregistered_land_algo = [e for _ in land_algo_classes if (e := _[1].name)
                              not in land_algo_config]
    for algo in unregistered_land_algo:
        print(f'{algo} must be registered in "land_algo_config.yaml"')
    if len(unregistered_land_algo) == 0:
        print('All land algorithms are correctly registered.')
    unregistered_wc_algo = [e for _ in wc_algo_classes if (e := _[1].name)
                            not in wc_algo_config]
    for algo in unregistered_wc_algo:
        print(f'{algo} must be registered in "wc_algo_config.yaml"')
    if len(unregistered_wc_algo) == 0:
        print('All water colour algorithms are correctly registered.')
    unregistered_mask = [e for _ in mask_classes if (e := _[1].name)
                         not in mask_config]
    for mask in unregistered_mask:
        print(f'{mask} must be registered in "mask_config.yaml"')
    if len(unregistered_mask) == 0:
        print('All masks are correctly registered.')
    if user_folder is not None:
        unregistered_user_algo = [e for _ in user_algo_classes
                                  if (e := _[1].name) not in user_algo_config]
        for algo in unregistered_user_algo:
            print(f'{algo} must be registered in "algo_config.yaml"')
        if len(unregistered_user_algo) == 0:
            print('All custom algorithms are correctly registered.')
        unregistered_user_mask = [e for _ in user_mask_classes
                                  if (e := _[1].name) not in user_mask_config]
        for mask in unregistered_user_mask:
            print(f'{mask} must be registered in "mask_config.yaml"')
        if len(unregistered_user_mask) == 0:
            print('All custom masks are correctly registered.')


def register_algos(catalog: dict) -> None:
    """Register each algorithm into a dictionary.

    Args:
        catalog: the dictionary in which will be stored algorithms.
    """
    for algo_name, algo_class in [(e, _[1]) for _ in land_algo_classes
                                  if (e := _[1].name) in land_algo_config]:
        catalog[algo_name] = algo_class
    for algo_name, algo_class in [(e, _[1]) for _ in wc_algo_classes
                                  if (e := _[1].name) in wc_algo_config]:
        catalog[algo_name] = algo_class
    if user_folder is not None and user_algo_config:
        for algo_name, algo_class in [(e, _[1]) for _ in user_algo_classes
                                      if (e := _[1].name) in user_algo_config]:
            catalog[algo_name] = algo_class


def register_masks(catalog: dict) -> None:
    """Register each mask into a dictionary.

    Args:
        catalog: the dictionary in which will be stored masks.
    """
    for mask_name, mask_class in [(e, _[1]) for _ in mask_classes
                                  if (e := _[1].name) in mask_config]:
        catalog[mask_name] = mask_class
    if user_folder is not None and user_mask_config:
        for mask_name, mask_class in [(e, _[1]) for _ in user_mask_classes
                                      if (e := _[1].name) in user_mask_config]:
            catalog[mask_name] = mask_class
