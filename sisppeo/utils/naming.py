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

"""Contains various useful functions used for naming products."""

import io
import tarfile
import logging
import fiona
from shapely.geometry import shape

from sisppeo.utils.exceptions import InputError

product_type_to_source = {
    'L8_USGS_L1C1': 'USGS-C1',
    'L8_USGS_L2': 'LaSRC',
    'S2_ESA_L1C': 'ESA',
    'S2_ESA_L2A': 'Sen2Cor',
    'L8_GRS': 'GRS',
    'S2_GRS': 'GRS',
    'S2_THEIA': 'MAIA',
    'S2_C2RCC': 'C2RCC'
}

mask_types = {
    's2cloudless': 'cloudmask',
    'waterdetect': 'watermask'
}

masks_to_args = {
    'watermask': 'wm',
    'cloudmask': 'cm',
    'suppl_masks': 'sm',
    'masks': 'm'
}

algoparams_to_args = {
    'band': 'band',
    'calibration': 'calib',
    'design': 'design'
}


def topleftlatlon_from_wkt(wkt_string):
    """Returns the (lat, lon) of the top-left point of a WKT string."""
    wkt_type = wkt_string.split('(', 1)[0].rstrip(' ')
    coord_string = wkt_string.lstrip(wkt_type + ' (')
    if wkt_type not in ('POINT', 'LINESTRING', 'POLYGON', 'MULTIPOINT',
                        'MULTILINESTRING', 'MULTIPOLYGON'):
        raise InputError('Invalid WKT')
    if wkt_type == 'POINT':
        topleftlatlon = [round(float(_), 5) for _
                         in coord_string.rstrip(')').split(' ')]
    elif wkt_type == 'MULTIPOINT':
        topleftlatlon = [round(float(_.rstrip(')')), 5) for _
                         in coord_string.split(',', 1)[0].split(' ')]
    else:
        topleftlatlon = [round(float(_), 5) for _
                         in coord_string.split(',', 1)[0].split(' ')]
    if len(topleftlatlon) == 3:
        topleftlatlon = topleftlatlon[:2]
    return str(topleftlatlon).replace(' ', '')


def geom_to_str(geom_dict):
    """Returns the (lat, lon) of top-left point of a geometry."""
    if (geom := geom_dict.get('geom')) is not None:
        wkt_str = geom.to_wkt()
    elif (wkt_file := geom_dict.get('wkt')) is not None:
        with open(wkt_file, 'r') as f:
            wkt_str = f.readlines()[0]
    elif (shp_file := geom_dict.get('shp')) is not None:
        with fiona.open(shp_file) as collection:
            geom = shape(collection[0]['geometry'])
        wkt_str = geom.to_wkt()
    else:
        raise InputError('wrong geom')
    return topleftlatlon_from_wkt(wkt_str)


def generate_l3_filename(l3prod, code_image, source, roi, chain_version=None, product_counter=None):
    """Returns a filename for a L3 product based on the provided arguments."""
    algo = l3prod.title.split(' ', 1)[0]
    if algo in mask_types:
        algo = f'{mask_types[algo]}-{algo}'
    var = l3prod.data_vars[0]
    bands = (l3prod.dataset.attrs.get('grs_bands', '')
             + l3prod.dataset.attrs.get('theia_bands', ''))
    if bands:
        bands = f'-bands={bands}'
    algoparams = []
    for algoparam in algoparams_to_args:
        if algoparam in l3prod.dataset[var].attrs:
            algoparams.append(f'{algoparams_to_args[algoparam]}='
                              + l3prod.dataset[var].attrs[algoparam])
    if algoparams:
        algoparams = f'-{"-".join(algoparams)}'
    else:
        algoparams = ''
    maskparams = l3prod.dataset[var].attrs.get('processing_resolution', '')
    if maskparams:
        maskparams = f'-proc_res={maskparams}'
    params = f'_params{bands}-res={l3prod.res}m{algoparams}{maskparams}'
    masks = []
    for mask in masks_to_args:
        if mask in l3prod.dataset.attrs:
            masks.append(f'{masks_to_args[mask]}'
                         + l3prod.dataset.attrs[mask].split(" ")[0])
    if masks:
        masks = f'_masks-{"-".join(masks)}'
    else:
        masks = ''
    if chain_version is None:
        chain_version=''
    if product_counter is None:
        product_counter=''
    filename = f'S2B_MSIL2B_{code_image}_{roi}_{source}_{algo}{params}{masks}_{chain_version}_{product_counter}.nc'
    logging.info(f'{filename} will be saved')
    return filename


def generate_ts_filename(ts, sat, source, roi):
    """Returns a filename for time series based on the provided arguments."""
    var = ts.data_vars[0]
    n = len(ts.dataset.time)
    start_date = ts.start_date.date().isoformat().replace('-', '')
    end_date = ts.end_date.date().isoformat().replace('-', '')
    algo = ts.title.split(' ', 1)[0]
    algoparams = []
    for algoparam in algoparams_to_args:
        if algoparam in ts.dataset[var].attrs:
            algoparams.append(f'{algoparams_to_args[algoparam]}='
                              + ts.dataset[var].attrs[algoparam])
    if algoparams:
        algoparams = f'-{"-".join(algoparams)}'
    else:
        algoparams = ''
    maskparams = ts.dataset[var].attrs.get('processing_resolution', '')
    if maskparams:
        maskparams = f'-proc_res={maskparams}'
    params = f'_params-res={ts.res}m{algoparams}{maskparams}'
    masks = []
    for mask in masks_to_args:
        if mask in ts.dataset.attrs:
            masks.append(f'{masks_to_args[mask]}={ts.dataset.attrs[mask]}')
    if masks:
        masks = f'_masks-{"-".join(masks)}'
    else:
        masks = ''
    if roi == "":
        filename = f'{sat}_{source}_{roi}_{algo}_{n}_{start_date}_{end_date}{params}{masks}.nc'
    else:
        filename = f'{sat}_{source}_{algo}_{n}_{start_date}_{end_date}{params}{masks}.nc'
    return filename


def extract_info_from_input_product(input_product, product_type,
                                    code_site=None, geom=None):
    """Extracts some information from the given input product."""
    if 'GRS' in product_type:
        code_image = "_".join(input_product.name.split('_')[2:7])
        if product_type == 'S2_GRS':
            sat = 'S2'
        else:   # product_type == 'L8_GRS'
            sat = 'LC8'
        tile = input_product.name.split('_')[5]
    elif product_type == 'L8_USGS_L1C1':
        if input_product.suffix in ('.tgz', '.gz'):
            with tarfile.open(input_product) as archive:
                tmp = str([_ for _ in archive.getnames()
                           if _.endswith('MTL.txt')][0]).split('_')
        else:
            tmp = str(list(input_product.glob('*MTL.txt'))[0]).split('_')
        code_image = f'LC8{tmp[2]}{tmp[3]}'
        sat = 'LC8'
        tile = tmp[2]
    elif product_type == 'L8_USGS_L2':
        if input_product.suffix == '.gz':
            with tarfile.open(input_product) as archive:
                path = [_ for _ in archive.getnames()
                        if _.endswith('MTL.txt')][0]
                with io.TextIOWrapper(archive.extractfile(path)) as f:
                    lines = f.readlines()
        else:
            path = list(input_product.glob('*MTL.txt'))[0]
            with open(path, 'r') as f:
                lines = f.readlines()
        landsat_scene_id = lines[4].lstrip(' ').rstrip('\n').replace(
            '"', '').split(' = ')[1]
        date_acquired = lines[20].lstrip(' ').rstrip('\n').replace(
            '"', '').split(' = ')[1].replace("-", "")
        code_image = f'LC8{landsat_scene_id[3:9]}{date_acquired}'
        sat = 'LC8'
        tile = landsat_scene_id[3:9]
    elif 'S2_ESA' in product_type or product_type == 'S2_C2RCC':
        tmp = input_product.name.split('_')
        code_image = f'{tmp[0]}{tmp[5][1:]}{tmp[2][:8]}'
        sat = 'S2'
        tile = tmp[5][1:]
    elif product_type == 'S2_THEIA':
        tmp = input_product.name.split('_')
        code_image = f'S{tmp[0][-2:]}{tmp[3][1:]}{tmp[1][:8]}'
        sat = 'S2'
        tile = tmp[3][1:]
    else:
        raise NameError('unknown product_type')
    source = product_type_to_source[product_type]
    if code_site is None and geom is None:
        roi = tile
    elif code_site is not None:
        roi = code_site
    else:
        roi = geom_to_str(geom)
    if product_type == 'S2_GRS':
        roi = ""
    return code_image, sat, source, roi
