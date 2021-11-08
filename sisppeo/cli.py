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

"""Defines the CLI of SISPPEO (powered by click)."""

from pathlib import Path

import click
import yaml
from shapely.wkt import loads

from sisppeo.main import generate, sat_products, theia_masks_names
from sisppeo.products.l3 import mask_product
from sisppeo.utils.cli import (PathPath, Mutex, Mutin, read_products_list,
                               read_algos_list, read_masks_list)
from sisppeo.utils.config import dict_workspace, root
from sisppeo.utils.exceptions import InputError
from sisppeo.utils.registration import (check_algoconfig, mask_functions,
                                        land_algo_classes, user_algo_classes,
                                        user_mask_functions, wc_algo_classes)

algo_names = [_[1].name for _ in land_algo_classes + wc_algo_classes
              + user_algo_classes]
mask_names = [_[0] for _ in mask_functions + user_mask_functions]


@click.group()
@click.version_option()
def cli():
    """SISPPEO is a Python package (with a CLI) allowing one to extract
    synthetic information useful for Earth observation (Water and Land) from
    satellite optical imagery (e.g, Sentinel-2/MSI, Sentinel-3/OLCI,
    Landsat 8/OLI...)."""


@cli.command()
def algorithms():
    """Returns the list of algorithms that can be used."""
    click.secho('AVAILABLE ALGORITHMS\n', bold=True, reverse=True)
    str_ = click.style('Land algorithms:', underline=True)
    click.echo(f'{str_} {", ".join([_[1].name for _ in land_algo_classes])}.\n')

    str_ = click.style('Water colour algorithms:', underline=True)
    click.echo(f'{str_} {", ".join([_[1].name for _ in wc_algo_classes])}.\n')
    if user_algo_classes:
        str_ = click.style('Custom algorithms:', underline=True)
        click.echo(f'{str_} {", ".join([_[1].name for _ in user_algo_classes])}.\n')


@cli.command()
def masks():
    """Returns the list of masks that can be created."""
    click.secho('AVAILABLE MASKS\n', bold=True, reverse=True)
    str_ = click.style('Standard masks:', underline=True)
    click.echo(f'{str_} {", ".join([_[0] for _ in mask_functions])}.\n')

    if user_mask_functions:
        str_ = click.style('Custom masks:', underline=True)
        click.echo(f'{str_} {", ".join([_[0] for _ in user_mask_functions])}.\n')


@cli.command()
def check_registration():
    """Checks if all algorithms are properly configured."""
    check_algoconfig()


@cli.command()
@click.option('--path', '-p', type=PathPath(),
              default=dict_workspace['default_path'],
              help='the path of the workspace')
def set_user_workspace(path):
    """Creates a workspace where the user can store his own algorithms."""
    if (path_str := str(path))[:2] == '~/':
        path = Path.home() / path_str.lstrip('~/')
    else:
        path = path.resolve()

    try:
        path.mkdir()
    except FileExistsError:
        io = input(f'This folder ("{str(path)}") already exists. Do you want '
                   'to continue ? (y/n)  [this operation will not erase your '
                   'data]')
        if io.lower() == 'n':
            click.echo('Operation aborted.')
            raise
    (path / 'custom_algorithms').mkdir(exist_ok=True)
    (path / 'custom_algorithms/__init__.py').touch()
    (path / 'custom_masks').mkdir(exist_ok=True)
    (path / 'custom_masks/__init__.py').touch()
    (path / 'resources').mkdir(exist_ok=True)
    (path / 'resources/algo_config.yaml').touch()
    (path / 'resources/mask_config.yaml').touch()
    (path / 'resources/algo_calibration').mkdir(exist_ok=True)

    dict_workspace['active_workspace'] = str(path)
    with open(root / 'workspace.yaml', 'w') as f:
        yaml.dump(dict_workspace, f)
    click.echo(f'new workspace: {str(path)}')


@cli.command()
def show_user_workspace():
    """Shows the path of the user's workspace."""
    click.echo(f'current workspace: {dict_workspace["active_workspace"]}')


@cli.command()
@click.option('--input_product', '-i', type=PathPath(exists=True),
              required=True,
              help='the path of the input product')
@click.option('--product_type', '-t', type=click.Choice(list(sat_products)),
              required=True,
              help='the type of the input product')
@click.option('--input_product_mask', '-im', type=PathPath(exists=True),
              cls=Mutin, required_if=('product_type_mask', 'mask'),
              help='the path of the input product (used to compute the wanted mask)')
@click.option('--product_type_mask', '-tm', type=click.Choice(list(sat_products)),
              cls=Mutin, required_if=('input_product_mask', 'mask'),
              help='the type of the input product (used to compute the wanted mask)')
@click.option('--theia_bands', type=click.Choice(['SRE', 'FRE']),
              default='FRE',
              help=('either use "SRE" or "FRE" bands when product_type is '
                    '"S2_THEIA".'))
@click.option('--theia_masks', multiple=True,
              help=(f'the mask to use ({", ".join(theia_masks_names[:-1])} or '
                    f'{theia_masks_names[-1]} are available) when '
                    'product_type is "S2_THEIA", and which bits to use (if no '
                    'bits are provided, all classes are used); e.g., "CLM '
                    '012467" or "MG2".'))
@click.option('--glint_corrected/--glint', default=True,
              help=('either use "Rrs" or "Rrs_g" bands when product_type is '
                    '"*_GRS"'))
@click.option('--flags', is_flag=True,
              help=('apply the "flags" mask of GRS products to extract water '
                    'surface'))
@click.option('--sensing_date', type=click.DateTime(),
              help='the sensing date (in UTC time) of the C2RCC product. [required]')
@click.option('--algo', '-a', type=click.Choice(algo_names), multiple=True,
              cls=Mutex, not_required_if=('algos_list',),
              help='the algorithm to use')
@click.option('--algo_band', nargs=2, multiple=True,
              help='the band used by the algorithm, e.g. "spm-nechad B4"')
@click.option('--algo_calib', nargs=2, multiple=True,
              help=('the calibration (set of parameters) used by the '
                    'algorithm, e.g. "spm-nechad Nechad_2010"'))
@click.option('--algo_custom_calib', nargs=2, type=(str, PathPath()),
              multiple=True,
              help=('the custom calibration (set of parameters) used by the '
                    'algorithm, e.g. "spm-nechad path/to/custom/calib"'))
@click.option('--algo_design', nargs=2, multiple=True,
              help=('the design used by the algorithm, e.g. "chla-gitelson '
                    '3_bands"'))
@click.option('--algos_list', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('algo',),
              help=('a text file listing the algorithms to apply along with '
                    'their configuration (optional; the bands, the [custom] '
                    'calibration and/or the design used); see examples in '
                    'doc'))
@click.option('--mask', '-m', type=click.Choice(mask_names),
              cls=Mutin, required_if=('input_product_mask', 'product_type',
              'out_resolution'),multiple=True,
              help='the mask to use')
@click.option('--output_dir', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('out_product',),
              help=('the path of the directory in which output product(s) '
                    'will be written (using automatically generated names)'))
@click.option('--out_product', '-o', type=PathPath(),
              cls=Mutex, not_required_if=('output_dir',), multiple=True,
              help='the path of the output product (one per algo/product)')
@click.option('--shp', type=PathPath(exists=True),
              help='the ESRI Shapefile to use (default: in WGS84)')
@click.option('--wkt',
              help='the polygon wkt to use (default: in WGS84)')
@click.option('--wkt_file', type=PathPath(exists=True),
              help=('the path of the file containing the polygon wkt to use '
                    '(default: in WGS84)'))
@click.option('--srid', type=click.INT, default=4326, show_default=True,
              help='the spatial reference identifier of the given wkt')
@click.option('--code_site',
              help=('the code_site (cf. bd_emil) that corresponds to the '
                    'provided shape; used for automatic naming'))
@click.option('--res', 'out_resolution', type=click.INT,
              help=('the resolution of output product(s); authorized values '
                    'are those of extracted band(s)'))
@click.option('--proc_res', 'processing_resolution', type=click.INT,
              help=('the resolution used when processing mask(s); must be '
                    'coarser than the one of the output product'))
def create_l3(input_product, product_type, input_product_mask,
              product_type_mask, theia_bands, theia_masks, glint_corrected,
              flags, algo, algo_band, algo_calib, algo_custom_calib,
              algo_design, algos_list, mask, output_dir, out_product,
              shp, wkt, wkt_file, srid, code_site, out_resolution,
              processing_resolution, sensing_date):
    """Creates masked (opt.) L3 products (one per algo) from a L1-2 one."""
    if mask:
        config_mask = {
            'input_product': input_product_mask,
            'product_type': product_type_mask,
            'theia_bands': theia_bands,
            'glint_corrected': glint_corrected,
            'flags': flags,
            'lst_mask': list(mask),
            'code_site': code_site,
            'out_resolution': out_resolution,
            'processing_resolution': processing_resolution
        }
        config_mask = {key: val for key, val in config_mask.items() if val is not None}
        if theia_masks:
            dd = {}
            for entry in theia_masks:
                tmp = entry.split(' ')
                if tmp[0] in theia_masks_names:
                    if len(tmp) == 2:
                        dd[tmp[0]] = [int(e) for e in tmp[1]]
                    else:
                        dd[tmp[0]] = None
                else:
                    continue
            if dd:
                config_mask['theia_masks'] = dd
        if not (wkt is None and shp is None and wkt_file is None):
            config_mask['geom'] = {
                'geom': None if wkt is None else loads(wkt),
                'shp': shp,
                'wkt': wkt_file,
                'srid': srid
            }

        lst_l3mask = generate('l3 mask', config_mask)
        dict_l3mask_type = {'s2cloudless': 'OUT', 'waterdetect': 'IN'}
        lst_l3mask_type = [dict_l3mask_type[_] for _ in list(mask)]

    config_algo = {
        'input_product': input_product,
        'product_type': product_type,
        'theia_bands': theia_bands,
        'glint_corrected': glint_corrected,
        'flags': flags,
        'sensing_date': sensing_date,
        'code_site': code_site,
        'out_resolution': out_resolution
    }
    config_algo = {key: val for key, val in config_algo.items() if val is not None}
    if theia_masks:
        dd = {}
        for entry in theia_masks:
            tmp = entry.split(' ')
            if tmp[0] in theia_masks_names:
                if len(tmp) == 2:
                    dd[tmp[0]] = [int(e) for e in tmp[1]]
                else:
                    dd[tmp[0]] = None
            else:
                continue
        if dd:
            config_algo['theia_masks'] = dd
    if algos_list is None:
        config_algo['lst_algo'] = list(algo)
        if lst_algo_band := list(algo_band):
            config_algo['lst_band'] = [dict(lst_algo_band).get(key, None)
                                       for key in list(algo)]
        if lst_algo_calib := list(algo_calib) + list(algo_custom_calib):
            config_algo['lst_calib'] = [dict(lst_algo_calib).get(key, None)
                                        for key in list(algo)]
        if lst_algo_design := list(algo_design):
            config_algo['lst_design'] = [dict(lst_algo_design).get(key, None)
                                         for key in list(algo)]
    else:
        config_algo.update(read_algos_list(algos_list))
    if output_dir is None:
        config_algo['filenames'] = list(out_product)
    else:
        config_algo['dirname'] = output_dir
    if not (wkt is None and shp is None and wkt_file is None):
        config_algo['geom'] = {
            'geom': None if wkt is None else loads(wkt),
            'shp': shp,
            'wkt': wkt_file,
            'srid': srid
        }
    if mask:
        config_algo['lst_l3mask'] = lst_l3mask
        config_algo['lst_l3mask_type'] = lst_l3mask_type

    _ = generate('l3 algo', config_algo, True)


@cli.command()
@click.option('--input_product', '-i', type=PathPath(exists=True),
              required=True,
              help='the path of the input product')
@click.option('--product_type', '-t', type=click.Choice(list(sat_products)),
              required=True,
              help='the type of the input product')
@click.option('--theia_bands', type=click.Choice(['SRE', 'FRE']),
              default='FRE',
              help=('either use "SRE" or "FRE" bands when product_type is '
                    '"S2_THEIA".'))
@click.option('--theia_masks', multiple=True,
              help=(f'the mask to use ({", ".join(theia_masks_names[:-1])} or '
                    f'{theia_masks_names[-1]} are available) when '
                    'product_type is "S2_THEIA", and which bits to use (if no '
                    'bits are provided, all classes are used); e.g., "CLM '
                    '012467" or "MG2".'))
@click.option('--glint_corrected/--glint', default=True,
              help=('either use "Rrs" or "Rrs_g" bands when product_type is '
                    '"*_GRS"'))
@click.option('--flags', is_flag=True,
              help=('apply the "flags" mask of GRS products to extract water '
                    'surface'))
@click.option('--sensing_date', type=click.DateTime(),
              help='the sensing date (in UTC time) of the C2RCC product. [required]')
@click.option('--algo', '-a', type=click.Choice(algo_names), multiple=True,
              cls=Mutex, not_required_if=('algos_list',),
              help='the algorithm to use')
@click.option('--algo_band', nargs=2, multiple=True,
              help='the band used by the algorithm, e.g. "spm-nechad B4"')
@click.option('--algo_calib', nargs=2, multiple=True,
              help=('the calibration (set of parameters) used by the '
                    'algorithm, e.g. "spm-nechad Nechad_2010"'))
@click.option('--algo_custom_calib', nargs=2, type=(str, PathPath()),
              multiple=True,
              help=('the custom calibration (set of parameters) used by the '
                    'algorithm, e.g. "spm-nechad path/to/custom/calib"'))
@click.option('--algo_design', nargs=2, multiple=True,
              help=('the design used by the algorithm, e.g. "chla-gitelson '
                    '3_bands"'))
@click.option('--algos_list', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('algo',),
              help=('a text file listing the algorithms to apply along with '
                    'their configuration (optional; the bands, the [custom] '
                    'calibration and/or the design used); see examples in '
                    'doc'))
@click.option('--output_dir', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('out_product',),
              help=('the path of the directory in which output product(s) '
                    'will be written (using automatically generated names)'))
@click.option('--out_product', '-o', type=PathPath(),
              cls=Mutex, not_required_if=('output_dir',), multiple=True,
              help='the path of the output product (one per algo/product)')
@click.option('--mask_path', type=PathPath(exists=True), multiple=True,
              help='the path of a mask to use')
@click.option('--mask_type', type=click.Choice(['IN', 'OUT']), multiple=True,
              help=('the type of an input mask; will it be used to include '
                    'or to exclude pixels ?'))
@click.option('--masks_list', type=PathPath(exists=True),
              help=('a text file listing the masks to apply along with '
                    'their type; see examples in doc'))
@click.option('--shp', type=PathPath(exists=True),
              help='the ESRI Shapefile to use (default: in WGS84)')
@click.option('--wkt',
              help='the polygon wkt to use (default: in WGS84)')
@click.option('--wkt_file', type=PathPath(exists=True),
              help=('the path of the file containing the polygon wkt to use '
                    '(default: in WGS84)'))
@click.option('--srid', type=click.INT, default=4326, show_default=True,
              help='the spatial reference identifier of the given wkt')
@click.option('--code_site',
              help=('the code_site (cf. bd_emil) that corresponds to the '
                    'provided shape; used for automatic naming'))
@click.option('--res', 'out_resolution', type=click.INT,
              help=('the resolution of output product(s); authorized values '
                    'are those of extracted band(s)'))
def create_l3algo(input_product, product_type, theia_bands, theia_masks,
                  glint_corrected, flags, algo, algo_band, algo_calib,
                  algo_custom_calib, algo_design, algos_list, output_dir,
                  out_product, mask_path, mask_type, masks_list, shp, wkt,
                  wkt_file, srid, code_site, out_resolution, sensing_date):
    """Creates L3 products (one per algo) from a L1-2 one."""
    config = {
        'input_product': input_product,
        'product_type': product_type,
        'theia_bands': theia_bands,
        'glint_corrected': glint_corrected,
        'flags': flags,
        'sensing_date': sensing_date,
        'code_site': code_site,
        'out_resolution': out_resolution
    }
    config = {key: val for key, val in config.items() if val is not None}
    if theia_masks:
        dd = {}
        for entry in theia_masks:
            tmp = entry.split(' ')
            if tmp[0] in theia_masks_names:
                if len(tmp) == 2:
                    dd[tmp[0]] = [int(e) for e in tmp[1]]
                else:
                    dd[tmp[0]] = None
            else:
                continue
        if dd:
            config['theia_masks'] = dd
    if algos_list is None:
        config['lst_algo'] = list(algo)
        if lst_algo_band := list(algo_band):
            config['lst_band'] = [dict(lst_algo_band).get(key, None)
                                  for key in list(algo)]
        if lst_algo_calib := list(algo_calib) + list(algo_custom_calib):
            config['lst_calib'] = [dict(lst_algo_calib).get(key, None)
                                   for key in list(algo)]
        if lst_algo_design := list(algo_design):
            config['lst_design'] = [dict(lst_algo_design).get(key, None)
                                    for key in list(algo)]
    else:
        config.update(read_algos_list(algos_list))
    if output_dir is None:
        config['filenames'] = list(out_product)
    else:
        config['dirname'] = output_dir
    if masks_list is not None:
        config.update(read_masks_list(masks_list))
    elif list(mask_path) and list(mask_type):
        config['lst_l3mask_path'] = list(mask_path)
        config['lst_l3mask_type'] = list(mask_type)
    if not (wkt is None and shp is None and wkt_file is None):
        config['geom'] = {
            'geom': None if wkt is None else loads(wkt),
            'shp': shp,
            'wkt': wkt_file,
            'srid': srid
        }

    _ = generate('l3 algo', config, True)


@cli.command()
@click.option('--input_product', '-i', type=PathPath(exists=True),
              required=True,
              help='the path of the input product')
@click.option('--product_type', '-t', type=click.Choice(list(sat_products)),
              required=True,
              help='the type of the input product')
@click.option('--theia_bands', type=click.Choice(['SRE', 'FRE']),
              default='FRE',
              help=('either use "SRE" or "FRE" bands when product_type is '
                    '"S2_THEIA".'))
@click.option('--theia_masks', multiple=True,
              help=(f'the mask to use ({", ".join(theia_masks_names[:-1])} or '
                    f'{theia_masks_names[-1]} are available) when '
                    'product_type is "S2_THEIA", and which bits to use (if no '
                    'bits are provided, all classes are used); e.g., "CLM '
                    '012467" or "MG2".'))
@click.option('--glint_corrected/--glint', default=True,
              help='either use "Rrs" or "Rrs_g" when product_type is "*_GRS"')
@click.option('--flags', is_flag=True,
              help=('apply the "flags" mask of GRS products to extract water '
                    'surface'))
@click.option('--mask', '-m', type=click.Choice(mask_names),
              required=True, multiple=True,
              help='the mask to use')
@click.option('--output_dir', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('out_product',),
              help=('the path of the directory in which output product(s) '
                    'will be written (using automatically generated names)'))
@click.option('--out_product', '-o', type=PathPath(),
              cls=Mutex, not_required_if=('output_dir',), multiple=True,
              help='the path of the output product')
@click.option('--shp', type=PathPath(exists=True),
              help='the ESRI Shapefile to use (default: in WGS84)')
@click.option('--wkt',
              help='the polygon wkt to use (default: in WGS84)')
@click.option('--wkt_file', type=PathPath(exists=True),
              help=('the path of the file containing the polygon wkt to use '
                    '(default: in WGS84)'))
@click.option('--srid', type=click.INT, default=4326, show_default=True,
              help='the spatial reference identifier of the given wkt')
@click.option('--code_site',
              help=('the code_site (cf. bd_emil) that corresponds to the '
                    'provided shape; used for automatic naming'))
@click.option('--res', 'out_resolution', type=click.INT,
              help=('the resolution of output product(s); authorized values '
                    'are those of extracted band(s)'))
@click.option('--proc_res', 'processing_resolution', type=click.INT,
              help=('the resolution used when processing mask(s); must be '
                    'coarser than the one of the output product'))
def create_l3mask(input_product, product_type, theia_bands, theia_masks,
                  glint_corrected, flags, mask, output_dir, out_product, shp,
                  wkt, wkt_file, srid, code_site, out_resolution,
                  processing_resolution):
    """Creates mask(s) from a L1-2 product (depending of the chosen masks)."""
    config = {
        'input_product': input_product,
        'product_type': product_type,
        'theia_bands': theia_bands,
        'glint_corrected': glint_corrected,
        'flags': flags,
        'lst_mask': list(mask),
        'code_site': code_site,
        'out_resolution': out_resolution,
        'processing_resolution': processing_resolution
    }
    config = {key: val for key, val in config.items() if val is not None}
    if theia_masks:
        dd = {}
        for entry in theia_masks:
            tmp = entry.split(' ')
            if tmp[0] in theia_masks_names:
                if len(tmp) == 2:
                    dd[tmp[0]] = [int(e) for e in tmp[1]]
                else:
                    dd[tmp[0]] = None
            else:
                continue
        if dd:
            config['theia_masks'] = dd
    if output_dir is None:
        config['filenames'] = list(out_product)
    else:
        config['dirname'] = output_dir
    if not (wkt is None and shp is None and wkt_file is None):
        config['geom'] = {
            'geom': None if wkt is None else loads(wkt),
            'shp': shp,
            'wkt': wkt_file,
            'srid': srid
        }

    _ = generate('l3 mask', config, True)


@cli.command()
@click.option('--input_product', '-i', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('products_list',), multiple=True,
              help='the path of the input product')
@click.option('--product_type', '-t', type=click.Choice(list(sat_products)),
              cls=Mutex, not_required_if=('products_list',), multiple=True,
              help='the type of the input product')
@click.option('--products_list', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('input_product', 'product_type'),
              help=('a text file listing product paths and their '
                    'corresponding product_types (+ optional: theia_bands, '
                    'lst_theia_mask, lst_theia_mask_bits, glint_corrrected, '
                    'flags, out_product, shp, wkt, wkt_file, srid, code_site, '
                    'res); see examples in doc'))
@click.option('--theia_bands', type=click.Choice(['SRE', 'FRE']),
              default='FRE',
              help=('either use "SRE" or "FRE" bands when product_type is '
                    '"S2_THEIA".'))
@click.option('--theia_masks', multiple=True,
              help=(f'the mask to use ({", ".join(theia_masks_names[:-1])} or '
                    f'{theia_masks_names[-1]} are available) when '
                    'product_type is "S2_THEIA", and which bits to use (if no '
                    'bits are provided, all classes are used); e.g., "CLM '
                    '012467" or "MG2".'))
@click.option('--glint_corrected/--glint', default=True,
              help='either use "Rrs" or "Rrs_g" when product_type is "*_GRS"')
@click.option('--flags', is_flag=True,
              help=('apply the "flags" mask of GRS products to extract water '
                    'surface'))
@click.option('--algo', '-a', type=click.Choice(algo_names), multiple=True,
              cls=Mutex, not_required_if=('algos_list',),
              help='the algorithm to use')
@click.option('--algo_band', nargs=2, multiple=True,
              help='the band used by the algorithm, e.g. "spm-nechad B4"')
@click.option('--algo_calib', nargs=2, multiple=True,
              help=('the calibration (set of parameters) used by the '
                    'algorithm, e.g. "spm-nechad Nechad_2010"'))
@click.option('--algo_custom_calib', nargs=2, type=(str, PathPath()),
              multiple=True,
              help=('the custom calibration (set of parameters) used by the '
                    'algorithm, e.g. "spm-nechad path/to/custom/calib"'))
@click.option('--algo_design', nargs=2, multiple=True,
              help=('the design used by the algorithm, e.g. "chla-gitelson '
                    '3_bands"'))
@click.option('--algos_list', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('algo',),
              help=('a text file listing the algorithms to apply along with '
                    'their configuration (optional; the bands, the [custom] '
                    'calibration and/or the design used); see examples in '
                    'doc'))
@click.option('--num_cpus', type=click.INT,
              help='the maximum number of central processing units used')
@click.option('--output_dir', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('out_product',),
              help=('the path of the directory in which output products will '
                    'be written (using automatically generated names)'))
@click.option('--out_product', '-o', type=PathPath(),
              cls=Mutex, not_required_if=('products_list', 'output_dir'),
              multiple=True,
              help='the path of the output product')
@click.option('--masks_list', type=PathPath(exists=True), multiple=True,
              help=('a text file listing mask paths and their corresponding '
                    'mask_types; see "create-l3algo" or examples in doc'))
@click.option('--shp', type=PathPath(exists=True),
              help='the ESRI Shapefile to use (default: in WGS84)')
@click.option('--wkt',
              help='the polygon wkt to use (default: in WGS84)')
@click.option('--wkt_file', type=PathPath(exists=True),
              help=('the path of the file containing the polygon wkt to use '
                    '(default: in WGS84)'))
@click.option('--srid', type=click.INT, default=4326, show_default=True,
              help='the spatial reference identifier of the given wkt')
@click.option('--code_site',
              help=('the code_site (cf. bd_emil) that corresponds to the '
                    'provided shape; used for automatic naming'))
@click.option('--res', 'out_resolution', type=click.INT,
              help=('the resolution of output products; authorized values '
                    'are those of extracted band(s)'))
def create_batch_l3algo(input_product, product_type, products_list,
                        theia_bands, theia_masks, glint_corrected, flags, algo,
                        algo_band, algo_calib, algo_custom_calib, algo_design,
                        algos_list, num_cpus, output_dir, out_product,
                        masks_list, shp, wkt, wkt_file, srid, code_site,
                        out_resolution):
    """[MULTIPROCESSING] Creates L3 products from L1-2 ones."""
    if products_list is None:
        config = {
            'input_products': list(input_product),
            'product_types': list(product_type)
        }
    else:
        config = read_products_list(products_list)
    if algos_list is None:
        config['lst_algo'] = list(algo)
        if lst_algo_band := list(algo_band):
            config['lst_band'] = [dict(lst_algo_band).get(key, None)
                                  for key in list(algo)]
        if lst_algo_calib := list(algo_calib) + list(algo_custom_calib):
            config['lst_calib'] = [dict(lst_algo_calib).get(key, None)
                                   for key in list(algo)]
        if lst_algo_design := list(algo_design):
            config['lst_design'] = [dict(lst_algo_design).get(key, None)
                                    for key in list(algo)]
    else:
        config.update(read_algos_list(algos_list))
    if 'lst_tb' not in config:
        config['theia_bands'] = theia_bands
    if 'lst_tm' not in config and theia_masks:
        dd = {}
        for entry in theia_masks:
            tmp = entry.split(' ')
            if tmp[0] in theia_masks_names:
                if len(tmp) == 2:
                    dd[tmp[0]] = [int(e) for e in tmp[1]]
                else:
                    dd[tmp[0]] = None
            else:
                continue
        if dd:
            config['theia_masks'] = dd
    if 'lst_gc' not in config:
        config['glint_corrected'] = glint_corrected
    if 'lst_flags' not in config:
        config['flags'] = flags
    if num_cpus is not None:
        config['num_cpus'] = num_cpus
    if 'filenames' not in config:
        if output_dir is None:
            config['filenames'] = list(out_product)
        else:
            config['dirname'] = output_dir
    if 'lst_masks_list' in config:
        lst_masks_list = config.pop('lst_masks_list')
    else:
        lst_masks_list = list(masks_list)
    if lst_masks_list:
        lst_tmp = [read_masks_list(file) for file in lst_masks_list]
        config['lst_l3masks_paths'] = [_['lst_l3mask_path'] for _ in lst_tmp]
        config['lst_l3masks_types'] = [_['lst_l3mask_type'] for _ in lst_tmp]
        cond1 = (len(config['input_products'])
                 != len(config['lst_l3masks_paths']))
        cond2 = (len(config['lst_l3masks_types'])
                 != len(config['lst_l3masks_types']))
        if cond1 or cond2:
            msg = 'You must provide a masks_list for each input product.'
            raise InputError(msg)
    if 'lst_geom' not in config and not (wkt is None and shp is None
                                         and wkt_file is None):
        config['geom'] = {
            'geom': None if wkt is None else loads(wkt),
            'shp': shp,
            'wkt': wkt_file,
            'srid': srid
        }
    if not ('lst_code_site' in config or code_site is None):
        config['code_site'] = code_site
    if not ('lst_res' in config and out_resolution is None):
        config['out_resolution'] = out_resolution

    _ = generate('batch algo', config, True)


@cli.command()
@click.option('--input_product', '-i', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('products_list',), multiple=True,
              help='the path of the input product')
@click.option('--product_type', '-t', type=click.Choice(list(sat_products)),
              cls=Mutex, not_required_if=('products_list',), multiple=True,
              help='the type of the input product')
@click.option('--products_list', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('input_product', 'product_type'),
              help=('a text file listing product paths and their '
                    'corresponding product_types (+ optional: theia_bands, '
                    'lst_theia_mask, lst_theia_mask_bits, glint_corrected, '
                    'flags, out_product, shp, wkt, wkt_file, srid, code_site, '
                    'res, proc_res); see examples in doc'))
@click.option('--theia_bands', type=click.Choice(['SRE', 'FRE']),
              default='FRE',
              help=('either use "SRE" or "FRE" bands when product_type is '
                    '"S2_THEIA".'))
@click.option('--theia_masks', multiple=True,
              help=(f'the mask to use ({", ".join(theia_masks_names[:-1])} or '
                    f'{theia_masks_names[-1]} are available) when '
                    'product_type is "S2_THEIA", and which bits to use (if no '
                    'bits are provided, all classes are used); e.g., "CLM '
                    '012467" or "MG2".'))
@click.option('--glint_corrected/--glint', default=True,
              help='either use "Rrs" or "Rrs_g" when product_type is "*_GRS"')
@click.option('--flags', is_flag=True,
              help=('apply the "flags" mask of GRS products to extract water '
                    'surface'))
@click.option('--mask', '-m', type=click.Choice(mask_names),
              required=True, multiple=True,
              help='the mask to use')
@click.option('--num_cpus', type=click.INT,
              help='the maximum number of central processing units used')
@click.option('--output_dir', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('out_product',),
              help=('the path of the directory in which output products will '
                    'be written (using automatically generated names)'))
@click.option('--out_product', '-o', type=PathPath(), multiple=True,
              cls=Mutex, not_required_if=('products_list', 'output_dir'),
              help='the path of the output product')
@click.option('--shp', type=PathPath(exists=True),
              help='the ESRI Shapefile to use (default: in WGS84)')
@click.option('--wkt',
              help='the polygon wkt to use (default: in WGS84)')
@click.option('--wkt_file', type=PathPath(exists=True),
              help=('the path of the file containing the polygon wkt to use '
                    '(default: in WGS84)'))
@click.option('--srid', type=click.INT, default=4326, show_default=True,
              help='the spatial reference identifier of the given wkt')
@click.option('--code_site',
              help=('the code_site (cf. bd_emil) that corresponds to the '
                    'provided shape; used for automatic naming'))
@click.option('--res', 'out_resolution', type=click.INT,
              help=('the resolution of output products; authorized values '
                    'are those of extracted band(s)'))
@click.option('--proc_res', 'processing_resolution', type=click.INT,
              help=('the resolution used when processing masks; must be '
                    'coarser than the one of the output product'))
def create_batch_l3mask(input_product, product_type, products_list,
                        theia_bands, theia_masks, glint_corrected, flags, mask,
                        num_cpus, output_dir, out_product, shp, wkt, wkt_file,
                        srid, code_site, out_resolution,
                        processing_resolution):
    """[MULTIPROCESSING] Creates masks from L1-2 products."""
    if products_list is None:
        config = {
            'input_products': list(input_product),
            'product_types': list(product_type)
        }
    else:
        config = read_products_list(products_list)
    config['lst_mask'] = list(mask)
    if 'lst_tb' not in config:
        config['theia_bands'] = theia_bands
    if 'lst_tm' not in config and theia_masks:
        if theia_masks:
            dd = {}
            for entry in theia_masks:
                tmp = entry.split(' ')
                if tmp[0] in theia_masks_names:
                    if len(tmp) == 2:
                        dd[tmp[0]] = [int(e) for e in tmp[1]]
                    else:
                        dd[tmp[0]] = None
                else:
                    continue
            if dd:
                config['theia_masks'] = dd
    if 'lst_gc' not in config:
        config['glint_corrected'] = glint_corrected
    if 'lst_flags' not in config:
        config['flags'] = flags
    if num_cpus is not None:
        config['num_cpus'] = num_cpus
    if 'filenames' not in config:
        if output_dir is None:
            config['filenames'] = list(out_product)
        else:
            config['dirname'] = output_dir
    if 'lst_geom' not in config and not (wkt is None and shp is None
                                         and wkt_file is None):
        config['geom'] = {
            'geom': None if wkt is None else loads(wkt),
            'shp': shp,
            'wkt': wkt_file,
            'srid': srid
        }
    if not('lst_code_site' in config or code_site is None):
        config['code_site'] = code_site
    if not ('lst_res' in config or out_resolution is None):
        config['out_resolution'] = out_resolution
    if not ('lst_proc_res' in config or processing_resolution is None):
        config['processing_resolution'] = processing_resolution

    _ = generate('batch mask', config, True)


@cli.command()
@click.option('--input_product', '-i', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('products_list',), multiple=True,
              help='the path of the input product')
@click.option('--product_type', '-t', type=click.Choice(list(sat_products)),
              required=True,
              help='the type of the input product')
@click.option('--products_list', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('input_product',),
              help='a text file listing product paths (+ optional: masks_list)')
@click.option('--theia_bands', type=click.Choice(['SRE', 'FRE']),
              default='FRE',
              help=('either use "SRE" or "FRE" bands when product_type is '
                    '"S2_THEIA".'))
@click.option('--theia_masks', multiple=True,
              help=(f'the mask to use ({", ".join(theia_masks_names[:-1])} or '
                    f'{theia_masks_names[-1]} are available) when '
                    'product_type is "S2_THEIA", and which bits to use (if no '
                    'bits are provided, all classes are used); e.g., "CLM '
                    '012467" or "MG2".'))
@click.option('--glint_corrected/--glint', default=True,
              help='either use "Rrs" or "Rrs_g" when product_type is "*_GRS"')
@click.option('--flags', is_flag=True,
              help=('apply the "flags" mask of GRS products to extract water '
                    'surface'))
@click.option('--algo', '-a', type=click.Choice(algo_names), multiple=True,
              cls=Mutex, not_required_if=('algos_list',),
              help='the algorithm to use')
@click.option('--algo_band', nargs=2, multiple=True,
              help='the band used by the algorithm, e.g. "spm-nechad B4"')
@click.option('--algo_calib', nargs=2, multiple=True,
              help=('the calibration (set of parameters) used by the '
                    'algorithm, e.g. "spm-nechad Nechad_2010"'))
@click.option('--algo_custom_calib', nargs=2, type=(str, PathPath()),
              multiple=True,
              help=('the custom calibration (set of parameters) used by the '
                    'algorithm, e.g. "spm-nechad path/to/custom/calib"'))
@click.option('--algo_design', nargs=2, multiple=True,
              help=('the design used by the algorithm, e.g. "chla-gitelson '
                    '3_bands"'))
@click.option('--algos_list', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('algo',),
              help=('a text file listing the algorithms to apply along with '
                    'their configuration (optional; the bands, the [custom] '
                    'calibration and/or the design used); see examples in '
                    'doc'))
@click.option('--num_cpus', type=click.INT,
              help='the maximum number of central processing units used')
@click.option('--output_dir', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('out_product',),
              help=('the path of the directory in which output products '
                    'will be written (using automatically generated names)'))
@click.option('--out_product', '-o', type=PathPath(), multiple=True,
              cls=Mutex, not_required_if=('output_dir',),
              help='the path of the output product')
@click.option('--masks_list', type=PathPath(exists=True), multiple=True,
              help=('a text file listing mask paths and their corresponding '
                    'mask_types; see "create-l3algo" or examples in doc'))
@click.option('--tsmask_path', type=PathPath(exists=True), multiple=True,
              help='the path of time series of masks to use')
@click.option('--tsmask_type', type=click.Choice(['IN', 'OUT']), multiple=True,
              help=('the type of an input time series of mask; will it be '
                    'used to include or to exclude pixels ?'))
@click.option('--shp', type=PathPath(exists=True),
              help='the ESRI Shapefile to use (default: in WGS84)')
@click.option('--wkt',
              help='the polygon wkt to use (default: in WGS84)')
@click.option('--wkt_file', type=PathPath(exists=True),
              help=('the path of the file containing the polygon wkt to use '
                    '(default: in WGS84)'))
@click.option('--srid', type=click.INT, default=4326, show_default=True,
              help='the spatial reference identifier of the given wkt')
@click.option('--code_site',
              help=('the code_site (cf. bd_emil) that corresponds to the '
                    'provided shape; used for automatic naming'))
@click.option('--res', 'out_resolution', type=click.INT,
              help=('the resolution of output product(s); authorized values '
                    'are those of extracted band(s)'))
def create_timeseries(input_product, product_type, products_list,
                      theia_bands, theia_masks, glint_corrected, flags, algo,
                      algo_band, algo_calib, algo_custom_calib, algo_design,
                      algos_list, num_cpus, output_dir, out_product,
                      tsmask_path, tsmask_type, masks_list, shp, wkt, wkt_file,
                      srid, code_site, out_resolution):
    """Creates time series (one per algo) of L3 products from L1-2 products.
    [MULTIPROCESSING]"""
    config = {
        'product_type': product_type,
        'theia_bands': theia_bands,
        'glint_corrected': glint_corrected,
        'flags': flags,
        'num_cpus': num_cpus,
        'code_site': code_site,
        'out_resolution': out_resolution
    }
    config = {key: val for key, val in config.items() if val is not None}
    if products_list is None:
        config['input_products'] = list(input_product)
    else:
        tmp = read_products_list(products_list, True)
        config['input_products'] = tmp['input_products']
        if 'lst_masks_list' in tmp:
            config['lst_masks_list'] = tmp['lst_masks_list']
    if theia_masks:
        dd = {}
        for entry in theia_masks:
            tmp = entry.split(' ')
            if tmp[0] in theia_masks_names:
                if len(tmp) == 2:
                    dd[tmp[0]] = [int(e) for e in tmp[1]]
                else:
                    dd[tmp[0]] = None
            else:
                continue
        if dd:
            config['theia_masks'] = dd
    if algos_list is None:
        config['lst_algo'] = list(algo)
        if lst_algo_band := list(algo_band):
            config['lst_band'] = [dict(lst_algo_band).get(key, None)
                                  for key in list(algo)]
        if lst_algo_calib := list(algo_calib) + list(algo_custom_calib):
            config['lst_calib'] = [dict(lst_algo_calib).get(key, None)
                                   for key in list(algo)]
        if lst_algo_design := list(algo_design):
            config['lst_design'] = [dict(lst_algo_design).get(key, None)
                                    for key in list(algo)]
    else:
        config.update(read_algos_list(algos_list))
    if output_dir is None:
        config['filenames'] = list(out_product)
    else:
        config['dirname'] = output_dir
    if tsmask_path:
        config['tsmask_path'] = list(tsmask_path)
    if tsmask_type:
        config['tsmask_type'] = list(tsmask_type)
    if 'lst_masks_list' in config:
        lst_masks_list = config.pop('lst_masks_list')
    elif masks_list:
        lst_masks_list = list(masks_list)
    else:
        lst_masks_list = []
    if lst_masks_list:
        lst_tmp = [read_masks_list(file) for file in lst_masks_list]
        config['lst_l3masks_paths'] = [_['lst_l3mask_path'] for _ in lst_tmp]
        config['lst_l3masks_types'] = [_['lst_masks_type'] for _ in lst_tmp]
        cond1 = (len(config['input_products'])
                 != len(config['lst_l3masks_paths']))
        cond2 = (len(config['lst_l3masks_types'])
                 != len(config['lst_l3masks_types']))
        if cond1 or cond2:
            msg = 'You must provide a masks_list for each input product.'
            raise InputError(msg)
    if not (wkt is None and shp is None and wkt_file is None):
        config['geom'] = {
            'geom': None if wkt is None else loads(wkt),
            'shp': shp,
            'wkt': wkt_file,
            'srid': srid
        }

    _ = generate('time series', config, True)


@cli.command()
@click.option('--input_product', '-i', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('products_list',), multiple=True,
              help='the path of the input product')
@click.option('--product_type', '-t', type=click.Choice(list(sat_products)),
              required=True,
              help='the type of the input product')
@click.option('--products_list', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('input_product',),
              help='a text file listing product paths')
@click.option('--theia_bands', type=click.Choice(['SRE', 'FRE']),
              default='FRE',
              help=('either use "SRE" or "FRE" bands when product_type is '
                    '"S2_THEIA".'))
@click.option('--theia_masks', multiple=True,
              help=(f'the mask to use ({", ".join(theia_masks_names[:-1])} or '
                    f'{theia_masks_names[-1]} are available) when '
                    'product_type is "S2_THEIA", and which bits to use (if no '
                    'bits are provided, all classes are used); e.g., "CLM '
                    '012467" or "MG2".'))
@click.option('--glint_corrected/--glint', default=True,
              help='either use "Rrs" or "Rrs_g" when product_type is "*_GRS"')
@click.option('--flags', is_flag=True,
              help=('apply the "flags" mask of GRS products to extract water '
                    'surface'))
@click.option('--mask', '-m', type=click.Choice(mask_names),
              required=True, multiple=True,
              help='the mask to use')
@click.option('--num_cpus', type=click.INT,
              help='the maximum number of central processing units used')
@click.option('--output_dir', type=PathPath(exists=True),
              cls=Mutex, not_required_if=('out_product',),
              help=('the path of the directory in which output products '
                    'will be written (using automatically generated names)'))
@click.option('--out_product', '-o', type=PathPath(),
              cls=Mutex, not_required_if=('output_dir',), multiple=True,
              help='the path of the output product')
@click.option('--shp', type=PathPath(exists=True),
              help='the ESRI Shapefile to use (default: in WGS84)')
@click.option('--wkt',
              help='the polygon wkt to use (default: in WGS84)')
@click.option('--wkt_file', type=PathPath(exists=True),
              help=('the path of the file containing the polygon wkt to use '
                    '(default: in WGS84)'))
@click.option('--srid', type=click.INT, default=4326, show_default=True,
              help='the spatial reference identifier of the given wkt')
@click.option('--code_site',
              help=('the code_site (cf. bd_emil) that corresponds to the '
                    'provided shape; used for automatic naming'))
@click.option('--res', 'out_resolution', type=click.INT,
              help=('the resolution of output product(s); authorized values '
                    'are those of extracted band(s)'))
@click.option('--proc_res', 'processing_resolution', type=click.INT,
              help=('the resolution used when processing masks; must be '
                    'coarser than the one of the output product'))
def create_timeseries_mask(input_product, product_type, products_list,
                           theia_bands, theia_masks, glint_corrected, flags,
                           mask, num_cpus, output_dir, out_product, shp, wkt,
                           wkt_file, srid, code_site, out_resolution,
                           processing_resolution):
    """Creates time series of masks from L1-2 products.
    [MULTIPROCESSING]"""
    config = {
        'product_type': product_type,
        'theia_bands': theia_bands,
        'glint_corrected': glint_corrected,
        'flags': flags,
        'lst_mask': list(mask),
        'num_cpus': num_cpus,
        'code_site': code_site,
        'out_resolution': out_resolution,
        'processing_resolution': processing_resolution,
    }
    config = {key: val for key, val in config.items() if val is not None}
    if products_list is None:
        config['input_products'] = list(input_product)
    else:
        config['input_products'] = read_products_list(products_list, True)['input_products']
    if theia_masks:
        dd = {}
        for entry in theia_masks:
            tmp = entry.split(' ')
            if tmp[0] in theia_masks_names:
                if len(tmp) == 2:
                    dd[tmp[0]] = [int(e) for e in tmp[1]]
                else:
                    dd[tmp[0]] = None
            else:
                continue
        if dd:
            config['theia_masks'] = dd
    if output_dir is None:
        config['filenames'] = list(out_product)
    else:
        config['dirname'] = output_dir
    if wkt is not None or shp is not None or wkt_file is not None:
        config['geom'] = {
            'geom': None if wkt is None else loads(wkt),
            'shp': shp,
            'wkt': wkt_file,
            'srid': srid
        }

    _ = generate('time series (mask)', config, True)
