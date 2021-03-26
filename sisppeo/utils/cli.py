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

"""This module contains various useful functions and classes used in the CLI."""

from pathlib import Path
from typing import Optional

import click
import pandas as pd
from shapely.wkt import loads


class PathPath(click.Path):
    """A Click path argument that returns a pathlib Path, not a string"""
    def convert(self, value, param, ctx):
        return Path(super().convert(value, param, ctx))


class Mutex(click.Option):
    """Mutually exclusive options (with at least one required)."""

    def __init__(self, *args, **kwargs):
        self.not_required_if = kwargs.pop('not_required_if')  # list
        assert self.not_required_if, '"not_required_if" parameter required'
        kwargs['help'] = (f'{kwargs.get("help", "")}  [required; mutually '
                          f'exclusive with {", ".join(self.not_required_if)}]')
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        current_opt = self.name in opts  # bool
        for mutex_opt in self.not_required_if:
            if mutex_opt in opts:
                if current_opt:
                    msg = (f'Illegal usage: "{self.name}" is mutually '
                           f'exclusive with "{mutex_opt}".')
                    raise click.UsageError(msg)
        return super().handle_parse_result(ctx, opts, args)


def _read_optional_column(df, key):
    if key in df.columns:
        return df[key].to_list()
    return None


def read_products_list(path: Path, is_ts=False) -> dict:
    """Parse a text file and return a config dictionnary."""
    df_products = pd.read_csv(path, ' ')
    if is_ts:
        product_types = _read_optional_column(df_products, 'product_type')
    else:
        product_types = df_products['product_type'].to_list()
    config = {
        'input_products': df_products['input_product'].to_list(),
        'product_types': product_types,
        'lst_tb': _read_optional_column(df_products, 'theia_bands'),
        'lst_gc': _read_optional_column(df_products, 'glint_corrected'),
        'lst_flags': _read_optional_column(df_products, 'flags'),
        'filenames': _read_optional_column(df_products, 'out_product'),
        'lst_masks_list': _read_optional_column(df_products, 'masks_list'),
        'lst_code_site': _read_optional_column(df_products, 'code_site'),
        'lst_res': _read_optional_column(df_products, 'res'),
        'lst_proc_res': _read_optional_column(df_products, 'proc_res')
    }
    theia_masks = _read_optional_column(df_products, 'theia_masks')
    if theia_masks is not None:
        ll = []
        for e in theia_masks:
            if isinstance(e, str):
                dd = {}
                for _ in e.split(','):
                    if len(_) == 3:
                        dd[_] = None
                    else:
                        dd[_[:3]] = [int(__) for __ in _[3:]]
                ll.append(dd)
            else:
                ll.append(None)
        config['lst_tm'] = ll
    lst_shp = _read_optional_column(df_products, 'shp')
    if lst_shp is None:
        lst_shp = [None for _ in range(len(df_products))]
    lst_wkt = _read_optional_column(df_products, 'wkt')
    if lst_wkt is None:
        lst_wkt = [None for _ in range(len(df_products))]
    lst_wf = _read_optional_column(df_products, 'wkt_file')
    if lst_wf is None:
        lst_wf = [None for _ in range(len(df_products))]
    lst_srid = _read_optional_column(df_products, 'srid')
    if lst_srid is None:
        lst_srid = [None for _ in range(len(df_products))]
    geoms = []
    for shp, wkt, wkt_file, srid in zip(lst_shp, lst_wkt, lst_wf, lst_srid):
        if shp is None and wkt is None and wkt_file is None and srid is None:
            geoms.append(None)
        else:
            geoms.append({
                'geom': None if wkt is None else loads(wkt),
                'shp': shp,
                'wkt': wkt_file,
                'srid': srid
            })
    if geoms != [None] * len(geoms):
        config['lst_geom'] = geoms
    return {key: val for key, val in config.items() if val is not None}


def _read_calib(df: pd.DataFrame, key: str) -> list:
    if key in df.columns:
        return df[key].to_list()
    return [None for _ in range(len(df))]


def _get_path(elem: Optional[str]) -> Path:
    if pd.isna(elem):
        return None
    return Path(elem)


def read_algos_list(path: Path) -> dict:
    """Parse a text file and return a config dictionnary."""
    df_algos = pd.read_csv(path, ' ')
    config = {
        'lst_algo': df_algos['algo'].to_list(),
        'lst_band': _read_optional_column(df_algos, 'band'),
        'lst_design': _read_optional_column(df_algos, 'design')
    }
    lst_calib = _read_calib(df_algos, 'calib')
    lst_custom_calib = _read_calib(df_algos, 'custom_calib')
    lst_custom_calib = [_get_path(_) for _ in lst_custom_calib]
    merge_calib = []
    for calib, custom_calib in zip(lst_calib, lst_custom_calib):
        if not pd.isna(calib):
            merge_calib.append(calib)
        else:
            merge_calib.append(custom_calib)
    config['lst_calib'] = merge_calib
    return {key: val for key, val in config.items() if val is not None}


def read_masks_list(path: Path) -> dict:
    """Parse a text file and return a config dictionnary."""
    df_l3masks = pd.read_csv(path, ' ')
    config = {
        'lst_l3mask_path': df_l3masks['path'].to_list(),
        'lst_l3mask_type': df_l3masks['type'].to_list()
    }
    return config
