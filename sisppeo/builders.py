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

"""Contains the ProductBuilder class.

The builder pattern organizes object construction into a set of steps
(extract_data, apply_algos, get_products, etc). To create an object,
you execute a series of these steps on a builder object (here,
a ProductBuilder instance). The important part is that you don’t need
to call all of the steps. You can call only the steps that are necessary
for producing a particular configuration of an object.

If the client code needs to assemble a special, fine-tuned L3
or L4 product, it can work with the builder directly.
Otherwise, the user can delegate the assembly to the generate method
(or dictely one of the recipes), which knows how to use a builder
to construct several of the most standard products (e.g., L3AlgoProduct,
L3MaskProduct, TimeSeries, Matchup, etc).
"""

import copy
from collections import namedtuple
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
import xarray as xr
from pyproj import CRS

from sisppeo._version import __version__
from sisppeo.catalogs import algo_catalog, mask_catalog, reader_catalog
from sisppeo.products import mask_product, L3AlgoProduct, L3MaskProduct
from sisppeo.utils.algos import producttype_to_sat
from sisppeo.utils.builders import get_variables
from sisppeo.utils.config import (land_algo_config, mask_config,
                                  user_algo_config, user_mask_config,
                                  wc_algo_config)
from sisppeo.utils.exceptions import InputError
from sisppeo.utils.readers import resample_band_array

algo_config = {**land_algo_config, **wc_algo_config, **user_algo_config}
mask_config = {**mask_config, **user_mask_config}


class ProductBuilder:
    """The builder used to create L3 and L4 objects.

    It specifies methods for creating the different parts (or
    building steps) of the product objects, and provides
    their implementations.
    """
    __slots__ = ('_algos', '_masks', '_product_type', '_requested_bands',
                 '_out_resolution', '_extracted_ds', '_results', '_products')

    def __init__(self):
        self._algos = None
        self._masks = None
        self._product_type = None
        self._requested_bands = None
        self._out_resolution = None
        self._extracted_ds = None
        self._results = None
        self._products = None

    def set_algos(self,
                  lst_algo: List[str],
                  product_type: str,
                  lst_band: Optional[List[str]] = None,
                  lst_calib: Optional[List[Union[str, Path]]] = None,
                  lst_design: Optional[List[str]] = None) -> None:
        """Creates and inits algo objects.

        Args:
            lst_algo: A list of algorithms to use.
            product_type: The type of the input satellite product (e.g.
                S2_ESA_L2A or L8_USGS_L1GT).
            lst_band: A list of "requested_band" args (a param used
                by some algorithms).
            lst_calib: A list of "calibration" args (a param used
                by some algorithms).
            lst_design: A list of "design" args (a param used
                by some algorithms).
        """
        algos = []
        requested_bands = set()
        for i, algo_name in enumerate(lst_algo):
            config = {}
            if lst_band is not None and lst_band[i] is not None:
                config['requested_band'] = lst_band[i]
            if lst_calib is not None and lst_calib[i] is not None:
                config['calibration'] = lst_calib[i]
            if lst_design is not None and lst_design[i] is not None:
                config['design'] = lst_design[i]
            algo = algo_catalog[algo_name](product_type=product_type, **config)
            algos.append(algo)
            requested_bands = requested_bands.union(algo.requested_bands)
        self._algos = tuple(algos)
        self._requested_bands = tuple(requested_bands)

    def set_masks(self, lst_masks: List[str], product_type: str) -> None:
        """Creates mask objects.

        Args:
            lst_masks: A list of masks to use.
            product_type: The type of the input satellite product
                (e.g. S2_ESA_L1C).
        """
        masks = []
        requested_bands = set()
        for mask_name in lst_masks:
            mask_func = mask_catalog[mask_name]
            masks.append((mask_name, mask_func))
            requested_bands = requested_bands.union(
                mask_config[mask_name][producttype_to_sat(product_type)])
        self._masks = tuple(masks)
        self._product_type = product_type
        self._requested_bands = tuple(requested_bands)

    @staticmethod
    def _set_resolution(product_type: str,
                        out_resolution: Optional[int] = None,
                        processing_resolution: Optional[int] = None
                        ) -> Tuple[Optional[int], Optional[int]]:
        if 'S2_ESA' in product_type:
            authorized_res = (None, 10, 20, 60)
            if out_resolution not in authorized_res:
                msg = ('"out_resolution" must either be set to None, 10, 20 '
                       'or 60.')
                raise InputError(msg)
            if processing_resolution not in authorized_res:
                msg = ('"processing_resolution" must either be set to None, '
                       '10, 20 or 60.')
                raise InputError(msg)
            if out_resolution is None:
                out_resolution = processing_resolution
            else:
                if (processing_resolution is None or
                        processing_resolution < out_resolution):
                    print(
                        f'"processing_resolution" must be >= {out_resolution}'
                        'm ("out_resolution"); here, "processing_resolution"='
                        f'{processing_resolution}m. Therefore, it will be '
                        f'ignored.'
                    )
                    processing_resolution = out_resolution
        elif product_type == 'S2_THEIA':
            authorized_res = (None, 10, 20)
            if out_resolution not in authorized_res:
                msg = '"out_resolution" must either be set to None, 10 or 20.'
                raise InputError(msg)
            if processing_resolution not in authorized_res:
                msg = ('"processing_resolution" must either be set to None, '
                       '10 or 20.')
                raise InputError(msg)
            if out_resolution is None:
                out_resolution = processing_resolution
            else:
                if (processing_resolution is None or
                        processing_resolution < out_resolution):
                    print(
                        f'"processing_resolution" must be >= {out_resolution}'
                        'm ("out_resolution"); here, "processing_resolution"='
                        f'{processing_resolution}m. Therefore, it will be '
                        f'ignored.'
                    )
                    processing_resolution = out_resolution
        else:
            if out_resolution is not None or processing_resolution is not None:
                print('Both "out_resolution" and "processing_resolution" '
                      'parameters can only be used with S2_ESA and S2_THEIA '
                      'products. Therefore, they will be ignored.')
        return out_resolution, processing_resolution

    def extract_data(self, product_type: str, input_product: Path,
                     geom: Optional[dict] = None, **kwargs) -> None:
        """Extracts (meta)data from the input product.

        Selects the right Reader and use it to extract the needed bands
        and metadata. Then, creates and returns a xr.Dataset containing
        these information.

        Args:
            product_type: The type of the input satellite product
                (e.g. "S2_ESA_L2A" or "L8_USGS_L1").
            input_product: The path of the input product (multispectral
                spaceborne imagery).
            geom: Optional; A dict containing geographical information
                that define the ROI.
                4 keys: geom (a shapely.geom object), shp (a path to
                an ESRI shapefile), wkt (a path to a wkt file) and srid
                (an EPSG code).
            kwargs: Args specific to the selected Reader.
        """
        if self._requested_bands is not None:
            requested_bands = self._requested_bands
        else:
            requested_bands = kwargs.pop('requested_bands')
        o_res, p_res = self._set_resolution(
            product_type, kwargs.pop('out_resolution', None),
            kwargs.pop('processing_resolution', None)
        )
        self._out_resolution = o_res
        reader = reader_catalog[product_type](input_product=input_product,
                                              product_type=product_type,
                                              requested_bands=requested_bands,
                                              geom=geom,
                                              out_resolution=p_res,
                                              **kwargs)
        reader.extract_bands()
        reader.create_ds()
        self._extracted_ds = reader.dataset

    @staticmethod
    def _compute_algo(algo,
                      input_dataarrays: List[xr.DataArray],
                      data_type: str,
                      epsg_code: int) -> xr.Dataset:
        output = algo(*input_dataarrays, data_type=data_type,
                      epsg_code=epsg_code)
        variables, long_names = get_variables(algo_config, algo.name)
        if len(variables) == 1:
            output = [output]
        out_dataarrays = {}
        for out_dataarray, variable, long_name in zip(output, variables,
                                                      long_names):
            np.nan_to_num(out_dataarray, False, np.nan, np.nan, np.nan)
            out_dataarray.attrs.update({
                'grid_mapping': 'crs',
                'long_name': long_name,
                **algo.meta
            })
            out_dataarray.name = variable
            out_dataarrays[variable] = out_dataarray
        return xr.Dataset(out_dataarrays)

    def compute_algos(self) -> None:
        """Runs every algorithms using extracted data and stores the results."""
        out_algos = {}
        data_type = self._extracted_ds.attrs['data_type']
        epsg_code = CRS.from_cf(self._extracted_ds.crs.attrs).to_epsg()
        for algo in self._algos:
            input_dataarrays = [self._extracted_ds[band].copy()
                                for band in algo.requested_bands]
            out_algos[algo.name] = self._compute_algo(algo, input_dataarrays,
                                                      data_type, epsg_code)
        self._results = out_algos

    @staticmethod
    def _compute_mask(mask_func,
                      input_dataarrays: List[xr.DataArray],
                      in_res: Optional[int] = None,
                      out_res: Optional[int] = None
                      ) -> Tuple[np.ndarray, dict]:
        out_ndarray, params = mask_func(input_dataarrays)
        if out_res is not None and out_res != in_res:
            arr = resample_band_array(out_ndarray[0], in_res, out_res, False)
            out_ndarray = arr.reshape((1, *arr.shape))
        return out_ndarray, params

    def compute_masks(self) -> None:
        """Runs every masks using extracted data and stores the results."""
        ds_res = (self._extracted_ds.x.values[1]
                  - self._extracted_ds.x.values[0])
        out_masks = []
        for mask_name, mask_func in self._masks:
            input_dataarrays = [
                copy.deepcopy(self._extracted_ds[band]) for band
                in mask_config[mask_name][producttype_to_sat(self._product_type)]
            ]
            out_masks.append(self._compute_mask(mask_func, input_dataarrays,
                                                ds_res, self._out_resolution))
        datasets = {}
        for (mask_name, _), (out_ndarray, params) in zip(self._masks,
                                                         out_masks):
            if self._out_resolution is None or self._out_resolution == ds_res:
                out_dataarray = self._extracted_ds[self._requested_bands[0]].copy(data=out_ndarray)
            else:
                offset = (self._out_resolution - ds_res) / 2
                x = np.arange(self._extracted_ds.x.values[0] + offset,
                              self._extracted_ds.x.values[-1] - offset + 1,
                              self._out_resolution)
                y = np.arange(self._extracted_ds.y.values[0] - offset,
                              self._extracted_ds.y.values[-1] + offset - 1,
                              -self._out_resolution)
                out_dataarray = xr.DataArray(
                    out_ndarray,
                    coords=[self._extracted_ds.time, y, x],
                    dims=['time', 'y', 'x']
                )
                out_dataarray.x.attrs = copy.copy(self._extracted_ds.x.attrs)
                out_dataarray.y.attrs = copy.copy(self._extracted_ds.y.attrs)
                out_dataarray.time.attrs = copy.copy(self._extracted_ds.time.attrs)
            out_dataarray.attrs.update({
                'grid_mapping': 'crs',
                'long_name': mask_config[mask_name]['long_name']
            })
            out_dataarray.attrs.update(params)
            if self._out_resolution is not None and ds_res != self._out_resolution:
                out_dataarray.attrs['processing_resolution'] = f'{int(ds_res)}m'
            out_dataarray.name = mask_name
            datasets[mask_name] = xr.Dataset({mask_name: out_dataarray})
        self._results = datasets

    def create_l3products(self, product_type: str) -> None:
        """Creates the wanted products and stores them.

        Args:
            product_type: The type of the input satellite product
                (e.g. "S2_ESA_L2A" or "L8_USGS_L1").
        """
        class Products(namedtuple('Products', (key.replace('-', '_')
                                               for key in self._results))):
            __slots__ = ()

            def __repr__(self):
                tmp = (f'{_}=<{str(self[i].__class__.mro()[0])[8:-2]}>'
                       for i, _ in enumerate(self._fields))
                return f'Products({", ".join(tmp)})'
                
        if self._algos is not None:
            product = L3AlgoProduct
        elif self._masks is not None:
            product = L3MaskProduct
        else:
            msg = 'You need to provide at least one algo or mask to use.'
            raise InputError(msg)
        products = []
        for algo in self._results:
            dataset = self._results[algo]
            for key in ('crs', 'product_metadata'):
                dataset[key] = self._extracted_ds[key]
            dataset.attrs = {
                'Convention': 'CF-1.8',
                'title': f'{algo} from {product_type}',
                'history': f'created with SISPPEO (v{__version__}) on '
                           + date.today().isoformat()
            }
            dataset.attrs.update(self._extracted_ds.attrs)
            dataset.attrs.pop('data_type', None)
            products.append(product(dataset))
        self._products = Products(*products)

    def mask_l3algosproduct(self,
                            masks_types: List[str],
                            masks: Optional[List[L3MaskProduct]] = None,
                            masks_paths: Optional[List[Path]] = None) -> None:
        """Masks the previously generated products.

        Args:
            masks_types: The list of the type of the masks to use.
                Values can either be "IN" (area to include) or "OUT"
                (area to exclude).
            masks: Optional; A list of masks to use.
            masks_paths: Optional; A list of paths (of L3MaskProducts)
                to use.
        """
        if masks_paths is not None:
            masks = [L3MaskProduct.from_file(path) for path in masks_paths]
        for l3_algo in self._products:
            mask_product(l3_algo, masks, masks_types, True)

    def get_products(self) -> namedtuple:
        """Returns products and resets itself."""
        products = self._products
        # Reset attributes
        self._algos = None
        self._masks = None
        self._product_type = None
        self._requested_bands = None
        self._out_resolution = None
        self._extracted_ds = None
        self._results = None
        self._products = None
        return products
