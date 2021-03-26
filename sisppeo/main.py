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

"""This module gathers a method called generate along with some standard recipes.

The generate method is the user-friendly way of using SISPPEO. You give the
type of products you want, a config dictionary and that's all: you can then
get the products you asked for !
It will automatically call the right recipe, parse parameters (values in the
config dict), and save generated products if asked.

Each recipe is responsible for executing the building steps in a particular
sequence (while the builder provides the implementation for those steps).
Strictly speaking, these recipes are optionals, since the client can control
the builder directly.
"""

import copy
from pathlib import Path
from typing import Dict, List, Optional, Union

import psutil
import ray

from sisppeo.builders import ProductBuilder
from sisppeo.products import (mask_time_series, L3AlgoProduct, L3MaskProduct,
                              TimeSeries)
from sisppeo.utils.main import parse_params, series_to_batch
from sisppeo.utils.naming import (extract_info_from_input_product,
                                  generate_l3_filename, generate_ts_filename)


def create_l3algoproducts(input_product: Path,
                          product_type: str,
                          lst_algo: List[str],
                          lst_l3mask: Optional[List[L3MaskProduct]] = None,
                          lst_l3mask_path: Optional[List[Path]] = None,
                          lst_l3mask_type: Optional[List[str]] = None,
                          geom: Optional[dict] = None,
                          lst_band: Optional[List[str]] = None,
                          lst_calib: Optional[List[Union[str, Path]]] = None,
                          lst_design: Optional[List[str]] = None,
                          save: bool = False,
                          dirname: Optional[Path] = None,
                          filenames: Optional[List[Union[str, Path]]] = None,
                          **kwargs) -> List[L3AlgoProduct]:
    """Returns a list of L3AlgoProducts (one per algo in lst_algo).

    Args:
        input_product: The path of the input product (multispectral spaceborne
            imagery).
        product_type: The type of the input satellite product (e.g.
            "S2_ESA_L2A" or "L8_USGS_L1GT").
        lst_algo: A list of algorithms to use.
        lst_l3mask: A list of masks (L3MaskProduct) to use.
        lst_l3mask_path: A list of paths (of L3MaskProducts) to use.
        lst_l3mask_type: The list of the type of the masks used. Values can
            either be "IN" (area to include) or "OUT" (area to exclude).
        geom: A dict containing geographical information that define the ROI.
            4 keys: geom (a shapely.geom object), shp (a path to an ESRI
            shapefile), wkt (a path to a wkt file) and srid (an EPSG code).
        lst_band: A list of "requested_band" args (a param used by some
            algorithms).
        lst_calib: A list of "calibration" args (a param used by some
            algorithms).
        lst_design: A list of "design" args (a param used by some
            algorithms).
        save: If True, write output products on disk.
        dirname: The path of the directory in which output products will be
            written (using automatically generated names).
        filenames: A list of wanted paths for output products.
        **kwargs: Args specific to the Reader that will be used.
    """
    builder = ProductBuilder()
    builder.set_algos(lst_algo, product_type, lst_band, lst_calib, lst_design)
    builder.extract_data(product_type, input_product, geom, **kwargs)
    builder.compute_algos()
    builder.create_l3products(product_type)
    if lst_l3mask_type is not None:
        if lst_l3mask is not None:
            builder.mask_l3algosproduct(lst_l3mask_type, lst_l3mask)
        elif lst_l3mask_path is not None:
            builder.mask_l3algosproduct(lst_l3mask_type,
                                        masks_paths=lst_l3mask_path)
        else:
            print('You should provide a list of either L3MaskProducts or '
                  'paths to masks (in netCDF format).')
    products = builder.get_products()
    if save:
        if filenames is None:
            code_image, _, source, roi = extract_info_from_input_product(
                input_product, product_type,
                kwargs.get('code_site', None), geom
            )
            for product in products:
                filename = generate_l3_filename(product, code_image, source,
                                                roi)
                if dirname is not None:
                    filename = dirname / filename
                product.save(filename)
        else:
            for product, filename in zip(products, filenames):
                product.save(filename)
    return products


@ray.remote
def _mp_l3algoproducts(input_product: Path,
                       product_type: str,
                       lst_algo: List[str],
                       lst_l3mask: Optional[List[L3MaskProduct]] = None,
                       lst_l3mask_path: Optional[List[Path]] = None,
                       lst_l3mask_type: Optional[List[str]] = None,
                       theia_bands: str = None,
                       theia_masks: Optional[Dict[str, Optional[List[int]]]] = None,
                       glint_corrected: Optional[bool] = None,
                       flags: Optional[bool] = None,
                       geom: Optional[dict] = None,
                       out_res: Optional[int] = None,
                       **kwargs) -> List[L3AlgoProduct]:
    suppl_config = {
        'theia_bands': theia_bands,
        'theia_masks': theia_masks,
        'glint_corrected': glint_corrected,
        'flags': flags,
        'geom': geom,
        'out_resolution': out_res,
    }
    config = kwargs.copy()
    config.update({key: val for key, val in suppl_config.items()
                   if val is not None})
    return create_l3algoproducts(input_product, product_type, lst_algo,
                                 lst_l3mask, lst_l3mask_path, lst_l3mask_type,
                                 **config)


def create_l3maskproducts(input_product: Path,
                          product_type: str,
                          lst_mask: List[str],
                          geom: Optional[dict] = None,
                          save: bool = False,
                          dirname: Optional[Path] = None,
                          filenames: Optional[List[Union[str, Path]]] = None,
                          **kwargs) -> List[L3MaskProduct]:
    """Returns a list of L3MaskProducts (one per mask in lst_mask).

    Args:
        input_product: The path of the input product (multispectral spaceborne
            imagery).
        product_type: The type of the input satellite product (e.g.
            "S2_ESA_L1C" or "S2_GRS").
        lst_mask: A list of masks to use.
        geom: A dict containing geographical information that define the ROI.
            4 keys: geom (a shapely.geom object), shp (a path to an ESRI
            shapefile), wkt (a path to a wkt file) and srid (an EPSG code).
        save: If True, write output products on disk.
        dirname: The path of the directory in which output products will be
            written (using automatically generated names).
        filenames: A list of wanted paths for output products.
        **kwargs: Args specific to the Reader that will be used.
    """
    builder = ProductBuilder()
    builder.set_masks(lst_mask, product_type)
    builder.extract_data(product_type, input_product, geom, **kwargs)
    builder.compute_masks()
    builder.create_l3products(product_type)
    products = builder.get_products()
    if save:
        if filenames is None:
            code_image, _, source, roi = extract_info_from_input_product(
                input_product, product_type,
                kwargs.get('code_site', None), geom
            )
            for product in products:
                filename = generate_l3_filename(product, code_image, source,
                                                roi)
                if dirname is not None:
                    filename = dirname / filename
                product.save(filename)
        else:
            for product, filename in zip(products, filenames):
                product.save(filename)
    return products


@ray.remote
def _mp_l3maskproducts(input_product: Path,
                       product_type: str,
                       lst_mask: List[str],
                       theia_bands: str = None,
                       theia_masks: Optional[Dict[str, Optional[List[int]]]] = None,
                       glint_corrected: Optional[bool] = None,
                       flags: Optional[bool] = None,
                       geom: dict = None,
                       out_res: Optional[int] = None,
                       proc_res: Optional[int] = None,
                       **kwargs) -> List[L3MaskProduct]:
    suppl_config = {
        'theia_bands': theia_bands,
        'theia_masks': theia_masks,
        'glint_corrected': glint_corrected,
        'flags': flags,
        'geom': geom,
        'out_resolution': out_res,
        'processing_resolution': proc_res,
    }
    config = kwargs.copy()
    config.update({key: val for key, val in suppl_config.items()
                   if val is not None})
    return create_l3maskproducts(input_product, product_type, lst_mask,
                                 **config)


def create_batch_l3algoproducts(input_products: List[Path],
                                product_types: List[str],
                                lst_algo: List[str],
                                lst_l3masks: Optional[List[List[L3MaskProduct]]] = None,
                                lst_l3masks_paths: Optional[List[List[Path]]] = None,
                                lst_l3masks_types: Optional[List[str]] = None,
                                num_cpus: Optional[int] = None,
                                lst_tb: Optional[List[Optional[str]]] = None,
                                lst_tm: Optional[List[Optional[dict]]] = None,
                                lst_gc: Optional[List[Optional[bool]]] = None,
                                lst_flags: Optional[List[Optional[bool]]] = None,
                                lst_geom: Optional[List[Optional[dict]]] = None,
                                lst_res: Optional[List[Optional[int]]] = None,
                                save: bool = False,
                                dirname: Optional[Path] = None,
                                filenames: Optional[List[Union[str, Path]]] = None,
                                **kwargs) -> List[List[L3AlgoProduct]]:
    """Returns a list of lists of L3AlgoProducts.

    Args:
        input_products: The list of paths of input products (multispectral
            spaceborne imagery).
        product_types: The list of types of input producs (e.g., ["S2_ESA_L2A",
            "L8_USGS_L1GT"]).
        lst_algo: A list of algorithms to use.
        lst_l3masks: A list of lists of masks (L3MaskProduct) to use.
        lst_l3masks_paths: A list of lists of paths (of
            L3MaskProducts) to use.
        lst_l3masks_types: The list of lists of the type of the masks
            to use. Values can either be "IN" (area to include) or "OUT" (area
            to exclude).
        num_cpus: The number of central processing units to use.
        lst_tb: A list of "theia_bands" args (one per input product). See
            S2THEIAReader.
        lst_tm: A list of "theia_masks" args (one per input product). See
            S2THEIAReader.
        lst_gc: A list of "glint_corrected" args (one per input product). See
            GRSReader.
        lst_flags: A list of "flags" args (one per input product). See
            GRSReader.
        lst_geom: A list of "geom" args (one per input product). See Reader.
        lst_res: A list of "out_resolution" args (one per input product). See
            either S2ESAREader or S2THEIAReader.
        save: If True, write output products on disk.
        dirname: The path of the directory in which output products will be
            written (using automatically generated names).
        filenames: A list of wanted paths for output products.
        **kwargs: Args specific to Readers that will be used.

    Returns:
        A list of lists of L3AlgoProducts. Each list corresponds to one input
        product.

        input_products = [<path1>, <path2>]
        lst_algo = [<algo1>, <algo2>, <algo3>]
        -> [[res_p1_a1, ..., res_p1_a3], [res_p2_a1, ..., res_p2_a3]]
    """
    cpus = [psutil.cpu_count(logical=False), len(input_products), num_cpus]
    num_cpus = min(val for val in cpus if val is not None)
    if ray.is_initialized():
        ray.shutdown()
    ray.init(num_cpus=num_cpus)
    futures = []
    if lst_tb is None:
        lst_tb = [None for _ in input_products]
    if lst_tm is None:
        lst_tm = [None for _ in input_products]
    if lst_gc is None:
        lst_gc = [None for _ in input_products]
    if lst_flags is None:
        lst_flags = [None for _ in input_products]
    if lst_geom is None:
        lst_geom = [None for _ in input_products]
    if lst_res is None:
        lst_res = [None for _ in input_products]
    for product_type, input_product, tb, tm, gc, flags, geom, res \
        in zip(product_types, input_products, lst_tb, lst_tm, lst_gc, lst_flags,
               lst_geom, lst_res):
        futures.append(_mp_l3algoproducts.remote(
            input_product, product_type, copy.copy(lst_algo),
            copy.deepcopy(lst_l3masks), copy.copy(lst_l3masks_paths),
            copy.copy(lst_l3masks_types), tb, tm, gc, flags, geom, res,
            **copy.copy(kwargs)
        ))
    res = ray.get(futures)
    ray.shutdown()
    if save:
        if filenames is None:
            lst_code_site = kwargs.get('lst_code_site')
            if lst_code_site is None:
                lst_code_site = [None for _ in input_products]
            for products, input_product, product_type, code_site, geom in zip(
                    res, input_products, product_types, lst_code_site,
                    lst_geom):
                code_image, _, source, roi = extract_info_from_input_product(
                    input_product, product_type, code_site, geom
                )
                for product in products:
                    filename = generate_l3_filename(product, code_image,
                                                    source, roi)
                    if dirname is not None:
                        filename = dirname / filename
                    product.save(filename)
        else:
            i = 0
            for products in res:
                for product in products:
                    product.save(filenames[i])
                    i += 1
    return res


def create_batch_l3maskproducts(input_products: List[Path],
                                product_types: List[str],
                                lst_mask: List[str],
                                num_cpus: Optional[int] = None,
                                lst_tb: Optional[List[Optional[str]]] = None,
                                lst_tm: Optional[List[Optional[dict]]] = None,
                                lst_gc: Optional[List[Optional[bool]]] = None,
                                lst_flags: Optional[List[Optional[bool]]] = None,
                                lst_geom: Optional[List[Optional[dict]]] = None,
                                lst_res: Optional[List[Optional[int]]] = None,
                                lst_proc_res: Optional[List[Optional[int]]] = None,
                                save: bool = False,
                                dirname: Optional[Path] = None,
                                filenames: Optional[List[Union[str, Path]]] = None,
                                **kwargs) -> List[List[L3MaskProduct]]:
    """Returns a list of lists of L3MaskProducts.

    Args:
        input_products: The list of paths of input products (multispectral
            spaceborne imagery).
        product_types: The list of types of input producs (e.g., ["S2_ESA_L1C",
            "S2_GRS"]).
        lst_mask: A list of masks to use.
        num_cpus: The number of central processing units to use.
        lst_tb: A list of "theia_bands" args (one per input product). See
            S2THEIAReader.
        lst_tm: A list of "theia_masks" args (one per input product). See
            S2THEIAReader.
        lst_gc: A list of "glint_corrected" args (one per input product). See
            GRSReader.
        lst_flags: A list of "flags" args (one per input product). See
            GRSReader.
        lst_geom: A list of "geom" args (one per input product). See Reader.
        lst_res: A list of "out_resolution" args (one per input product). See
            either S2ESAREader or S2THEIAReader.
        lst_proc_res: A list of "proc_res" args (one per input product). See
            ProductBuilder.compute_masks.
        save: If True, write output products on disk.
        dirname: The path of the directory in which output products will be
            written (using automatically generated names).
        filenames: A list of wanted paths for output products.
        **kwargs: Args specific to Readers that will be used.

    Returns:
        A list of lists of L3AlgoMasks. Each list corresponds to one input
        product.

        input_products = [<path1>, <path2>]
        lst_mask = [<mask1>, <mask2>, <mask3>]
        -> [[res_p1_m1, ..., res_p1_m3], [res_p2_m1, ..., res_p2_m3]]
    """
    cpus = [psutil.cpu_count(logical=False), len(input_products), num_cpus]
    num_cpus = min(val for val in cpus if val is not None)
    if ray.is_initialized():
        ray.shutdown()
    ray.init(num_cpus=num_cpus)
    futures = []
    if lst_tb is None:
        lst_tb = [None for _ in input_products]
    if lst_tm is None:
        lst_tm = [None for _ in input_products]
    if lst_gc is None:
        lst_gc = [None for _ in input_products]
    if lst_flags is None:
        lst_flags = [None for _ in input_products]
    if lst_geom is None:
        lst_geom = [None for _ in input_products]
    if lst_res is None:
        lst_res = [None for _ in input_products]
    if lst_proc_res is None:
        lst_proc_res = [None for _ in input_products]
    for product_type, input_product, tb, tm, gc, flags, geom, out_res, \
        proc_res in zip(product_types, input_products, lst_tb, lst_tm, lst_gc,
                        lst_flags, lst_geom, lst_res, lst_proc_res):
        futures.append(_mp_l3maskproducts.remote(
            input_product, product_type, copy.copy(lst_mask), tb, tm, gc,
            flags, geom, out_res, proc_res, **copy.copy(kwargs)
        ))
    res = ray.get(futures)
    ray.shutdown()
    if save:
        if filenames is None:
            lst_code_site = kwargs.get('lst_code_site')
            if lst_code_site is None:
                lst_code_site = [None for _ in input_products]
            for products, input_product, product_type, code_site, geom in zip(
                    res, input_products, product_types, lst_code_site,
                    lst_geom):
                code_image, _, source, roi = extract_info_from_input_product(
                    input_product, product_type, code_site, geom
                )
                for product in products:
                    filename = generate_l3_filename(product, code_image,
                                                    source, roi)
                    if dirname is not None:
                        filename = dirname / filename
                    product.save(filename)
        else:
            i = 0
            for products in res:
                for product in products:
                    product.save(filenames[i])
                    i += 1
    return res


def create_algotimeseries(input_products: List[Path],
                          product_type: str,
                          lst_algo: List[str],
                          lst_l3masks: Optional[List[List[L3MaskProduct]]] = None,
                          lst_l3masks_paths: Optional[List[List[Path]]] = None,
                          lst_l3masks_types: Optional[List[str]] = None,
                          lst_tsmask: Optional[List[TimeSeries]] = None,
                          lst_tsmask_path: Optional[List[Path]] = None,
                          lst_tsmask_type=None,
                          geom: Optional[dict] = None,
                          save: bool = False,
                          dirname: Optional[Path] = None,
                          filenames: Optional[List[Union[str, Path]]] = None,
                          **kwargs) -> List[TimeSeries]:
    """Returns a list of TimeSeries (one per algo in lst_algo).

    Args:
        input_products: The list of paths of input products (multispectral
            spaceborne imagery).
        product_type: The type of input products (e.g. "S2_ESA_L2A" or
            "L8_USGS_L1GT").
        lst_algo: A list of algorithms to use.
        lst_l3masks: A list of lists of masks (L3MaskProduct) to use.
        lst_l3masks_paths: A list of lists of paths (of L3MaskProducts) to use.
        lst_l3masks_types: The list of lists of the type of the masks to use.
            Values can either be "IN" (area to include) or "OUT" (area to
            exclude).
        lst_tsmask: A list of time series of masks to use.
        lst_tsmask_path: A list of paths (of TimeSeries) to use.
        lst_tsmask_type: The list of the type of the time series of masks used.
            Values can either be "IN" (area to include) or "OUT" (area to
            exclude).
        geom: A dict containing geographical information that define the ROI.
            4 keys: geom (a shapely.geom object), shp (a path to an ESRI
            shapefile), wkt (a path to a wkt file) and srid (an EPSG code).
        save: If True, write output products on disk.
        dirname: The path of the directory in which output products will be
            written (using automatically generated names).
        filenames: A list of wanted paths for output products.
        **kwargs: Args specific to the Reader that will be used.
    """
    batch_params = series_to_batch({'product_type': product_type,
                                    'geom': geom}, len(input_products))
    res = create_batch_l3algoproducts(input_products,
                                      batch_params.pop('product_types'),
                                      lst_algo, lst_l3masks, lst_l3masks_paths,
                                      lst_l3masks_types, **batch_params,
                                      **kwargs)
    lst_ts = [TimeSeries.from_l3products(time_series)
              for time_series in zip(*res)]
    if lst_tsmask_type is not None:
        if lst_tsmask is None and lst_tsmask_path is not None:
            lst_tsmask = [TimeSeries.from_file(ts_mask_path)
                          for ts_mask_path in lst_tsmask_path]
        if lst_tsmask is not None:
            for ts_algo in lst_ts:
                mask_time_series(ts_algo, lst_tsmask, lst_tsmask_type, True)
    if save:
        if filenames is None:
            code_site = kwargs.get('code_site', None)
            _, sat, source, roi = extract_info_from_input_product(
                input_products[0], product_type, code_site, geom
            )
            for ts in lst_ts:
                filename = generate_ts_filename(ts, sat, source, roi)
                if dirname is not None:
                    filename = dirname / filename
                ts.save(filename)
        else:
            for ts, filename in zip(lst_ts, filenames):
                ts.save(filename)
    return lst_ts


def create_masktimeseries(input_products: List[Path],
                          product_type: List[str],
                          lst_mask: List[str],
                          geom: Optional[dict] = None,
                          save: bool = False,
                          dirname: Optional[Path] = None,
                          filenames: Optional[List[Union[str, Path]]] = None,
                          **kwargs) -> List[TimeSeries]:
    """Returns a list of TimeSeries (one per mask in lst_mask).

    Args:
        input_products: The list of paths of input products (multispectral
            spaceborne imagery).
        product_type: The type of input products (e.g. "S2_ESA_L2A" or
            "L8_USGS_L1GT").
        lst_mask: A list of masks to use.
        geom: A dict containing geographical information that define the ROI.
            4 keys: geom (a shapely.geom object), shp (a path to an ESRI
            shapefile), wkt (a path to a wkt file) and srid (an EPSG code).
        save: If True, write output products on disk.
        dirname: The path of the directory in which output products will be
            written (using automatically generated names).
        filenames: A list of wanted paths for output products.
        **kwargs: Args specific to Readers that will be used.
    """
    batch_params = series_to_batch({'product_type': product_type,
                                    'geom': geom}, len(input_products))
    res = create_batch_l3maskproducts(input_products,
                                      batch_params.pop('product_types'),
                                      lst_mask, **batch_params, **kwargs)
    lst_ts = [TimeSeries.from_l3products(time_series)
              for time_series in zip(*res)]
    if save:
        if filenames is None:
            code_site = kwargs.get('code_site', None)
            _, sat, source, roi = extract_info_from_input_product(
                input_products[0], product_type, code_site, geom
            )
            for ts in lst_ts:
                filename = generate_ts_filename(ts, sat, source, roi)
                if dirname is not None:
                    filename = dirname / filename
                ts.save(filename)
        else:
            for ts, filename in zip(lst_ts, filenames):
                ts.save(filename)
    return lst_ts


# TODO: create a function to automatize the update of this tuple.
sat_products = ('S2_ESA_L1C', 'S2_ESA_L2A', 'S2_THEIA', 'L8_GRS', 'S2_GRS',
                'L8_USGS_L1C1', 'L8_USGS_L2')
theia_masks_names = ('CLM', 'MG2', 'SAT')


def generate(key: str, params: dict, save=False, parse_params_=True):
    """Returns the wanted (L3/L4) products. Can also save them.

    Args:
        key: What product to generate.
        params: A dict of params.
        save: If True, write them on disk.
        naming_function: Optional; The custom naming function to use.
        parse_params_: If True, the params dict is checked (using the
            parse_params function).
    """
    func = {
        'l3 algo': create_l3algoproducts,
        'l3 mask': create_l3maskproducts,
        'batch algo': create_batch_l3algoproducts,
        'batch mask': create_batch_l3maskproducts,
        'time series': create_algotimeseries,
        'time series (mask)': create_masktimeseries
    }
    if parse_params_:
        params = parse_params(key, params)
    params['save'] = save
    print('\nparams: ', params, '\n')
    products = func[key](**params)
    return products
