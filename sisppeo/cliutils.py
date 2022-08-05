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

"""
TODO: module docstring
"""

from pathlib import Path

import click
import fiona
from shapely.geometry import shape


class InputError(Exception):
    """Exception raised for errors in the input"""


class PathPath(click.Path):
    """A Click path argument that returns a pathlib Path, not a string"""
    def convert(self, value, param, ctx):
        return Path(super().convert(value, param, ctx))


class Mutex(click.Option):
    """TODO: class docstring"""

    def __init__(self, *args, **kwargs):
        self.not_required_if = kwargs.pop('not_required_if')  # list
        assert self.not_required_if, '"not_required_if" parameter required'
        kwargs['help'] = (f'{kwargs.get("help", "")}  [required; mutually '
                          f'exclusive with {", ".join(self.not_required_if)}')
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


def topleftlatlon_from_wkt(wkt_string):
    """TODO: function docstring"""
    wkt_type = wkt_string.split('(', 1)[0].rstrip(' ')
    coord_string = wkt_string.lstrip(wkt_type + ' (')
    if wkt_type not in ('POINT', 'LINESTRING', 'POLYGON', 'MULTIPOINT',
                        'MULTILINESTRING', 'MULTIPOLYGON'):
        raise InputError('Invalid WKT')
    if wkt_type == 'POINT':
        topleftlatlon = [float(_) for _ in coord_string.rstrip(')').split(' ')]
    elif wkt_type == 'MULTIPOINT':
        topleftlatlon = [float(_.rstrip(')')) for _
                         in coord_string.split(',', 1)[0].split(' ')]
    else:
        topleftlatlon = [float(_) for _
                         in coord_string.split(',', 1)[0].split(' ')]
    return topleftlatlon


def geom_to_str(geom_dict):
    """TODO: function docstring"""
    if geom := geom_dict.get('geom') is not None:
        wkt_str = geom.to_wkt()
    elif wkt_file := geom_dict.get('wkt') is not None:
        with open(wkt_file, 'r') as f:
            wkt_str = f.readlines()[0]
    elif shp_file := geom_dict.get('shp') is not None:
        with fiona.open(shp_file) as collection:
            geom = shape(collection[0]['geometry'])
        wkt_str = geom.to_wkt()
    else:
        return ''
    return f'_{topleftlatlon_from_wkt(wkt_str)}'


def glint_str(glint_cor):
    """TODO: function docstring"""
    if glint_cor is not None:
        return f'{glint_cor}'
    else:
        return ''


def params_str(**kwargs):
    """TODO: function docstring"""
    def _func(lst_):
        str_ = ''
        for elem in lst_:
            str_ += f'-{elem[0]}={elem[1]}'
        return str_

    tmp = _func([(key, val) for key, val in kwargs.items() if val != ''])
    if tmp == '':
        return ''
    else:
        return f'_args{tmp}'
