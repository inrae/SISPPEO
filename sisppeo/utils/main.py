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

"""Contains various useful functions used in main.py."""

from pathlib import Path

from sisppeo.utils.exceptions import InputError


def str_to_path(path_str, exists=True):
    """Converts a path string to a pathlib.Path object.

    Args:
        path_str: a path string.
        exists: a boolean whether to check if this path exists or not.
    """
    if isinstance(path_str, str):
        path = Path(path_str)
    else:
        path = path_str
    if exists and not path.exists():
        raise InputError(f'"{str(path)}" does not exist')
    return path


def parse_params(key, params):
    """Parse and verify params given to the function generate (main.py)."""
    # module
    if 'product_type' in params and 'batch' in key:
        product_type = params.pop('product_type')
        params['product_types'] = [product_type for _
                                   in range(len(params['input_products']))]
    if 'dirname' in params:
        params['dirname'] = str_to_path(params['dirname'])
    if 'filename' in params:
        params['filenames'] = [str_to_path(params.pop('filename'), False)]
    elif 'filenames' in params:
        params['filenames'] = [str_to_path(p, False)
                               for p in params['filenames']]
    if 'algo' in params:
        params['lst_algo'] = [params.pop('algo')]
    if 'algo_band' in params:
        params['lst_band'] = [params.pop('algo_band')]
    if 'algo_calib' in params:
        params['lst_calib'] = [params.pop('algo_calib')]
    if 'mask' in params:
        params['lst_mask'] = [params.pop('mask')]
    if 'l3mask' in params:
        lst_l3mask = params.pop('l3mask')
        if not isinstance(lst_l3mask, list):
            lst_l3mask = [lst_l3mask]
        params['lst_l3mask'] = lst_l3mask
    if 'l3mask_path' in params:
        lst_l3mask_path = params.pop('l3mask_path')
        if not isinstance(lst_l3mask_path, list):
            lst_l3mask_path = [lst_l3mask_path]
        params['lst_l3mask_path'] = lst_l3mask_path
    if 'l3mask_type' in params:
        lst_l3mask_type = params.pop('l3mask_type')
        if not isinstance(lst_l3mask_type, list):
            lst_l3mask_type = [lst_l3mask_type]
        params['lst_l3mask_type'] = lst_l3mask_type
    if 'tsmask' in params:
        lst_tsmask = params.pop('tsmask')
        if not isinstance(lst_tsmask, list):
            lst_tsmask = [lst_tsmask]
        params['lst_tsmask'] = lst_tsmask
    if 'tsmask_path' in params:
        lst_tsmask_path = params.pop('tsmask_path')
        if not isinstance(lst_tsmask_path, list):
            lst_tsmask_path = [lst_tsmask_path]
        params['lst_tsmask_path'] = lst_tsmask_path
    if 'tsmask_type' in params:
        lst_tsmask_type = params.pop('tsmask_type')
        if not isinstance(lst_tsmask_type, list):
            lst_tsmask_type = [lst_tsmask_type]
        params['lst_tsmask_type'] = lst_tsmask_type

    # module + CLI
    if 'input_product' in params:
        params['input_product'] = str_to_path(params.pop('input_product'))
    elif 'input_products' in params:
        params['input_products'] = [str_to_path(product) for product
                                    in params.pop('input_products')]
    else:
        msg = 'You must provide at least one input product.'
        raise InputError(msg)
    if 'lst_l3mask_path' in params:   # l3algo / match up
        params['lst_l3mask_path'] = [str_to_path(l3mask_path) for l3mask_path
                                     in params['lst_l3mask_path']]
    if 'lst_l3masks_paths' in params:     # time series / batch
        params['lst_l3masks_paths'] = [
            [str_to_path(l3mask_path) for l3mask_path in lst_l3mask_path]
            for lst_l3mask_path in params['lst_l3masks_paths']
        ]
    if 'lst_tsmask_path' in params:
        params['lst_tsmask_path'] = [str_to_path(tsmask_path) for tsmask_path
                                     in params['lst_tsmask_path']]

    if 'theia_bands' in params and ('time series' in key
                                    or 'batch' in key):
        theia_bands = params.pop('theia_bands')
        params['lst_tb'] = [theia_bands for _
                            in range(len(params['input_products']))]
    if 'theia_masks' in params and ('time series' in key or 'batch' in key):
        theia_masks = params.pop('theia_masks')
        params['lst_tm'] = [theia_masks for _
                            in range(len(params['input_products']))]
    if 'glint_corrected' in params and ('time series' in key
                                        or 'batch' in key):
        glint_corrected = params.pop('glint_corrected')
        params['lst_gc'] = [glint_corrected for _
                            in range(len(params['input_products']))]
    if 'flags' in params and ('time series' in key or 'batch' in key):
        flags = params.pop('flags')
        params['lst_flags'] = [flags for _
                               in range(len(params['input_products']))]
    if 'geom' in params and 'batch' in key:
        geom = params.pop('geom')
        params['lst_geom'] = [geom for _
                              in range(len(params['input_products']))]
    if 'code_site' in params and 'batch' in key:
        code_site = params.pop('code_site')
        params['lst_code_site'] = [code_site for _
                                   in range(len(params['input_products']))]
    if 'out_resolution' in params and ('time series' in key or 'batch' in key):
        out_resolution = params.pop('out_resolution')
        params['lst_res'] = [out_resolution
                             for _ in range(len(params['input_products']))]
    if 'processing_resolution' in params and ('time series' in key
                                              or 'batch' in key):
        processing_resolution = params.pop('processing_resolution')
        params['lst_proc_res'] = [processing_resolution for _
                                  in range(len(params['input_products']))]

    return params


def series_to_batch(args, n):
    product_type = args.pop('product_type')
    args['product_types'] = [product_type for _ in range(n)]
    geom = args.pop('geom')
    if geom is not None:
        args['lst_geom'] = [geom for _ in range(n)]
    return args
