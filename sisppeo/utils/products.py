# -*- coding: utf-8 -*-
# Copyright 2020 Arthur Coqué, Pierre Manchon, Pôle OFB-INRAE ECLA, UR RECOVER
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
"""Contains useful stuff for products."""
import bisect
import re
from pathlib import Path
from typing import Optional, Tuple, Union

import fiona
import numpy as np
import pandas as pd
import pyproj
import rasterio.features
import shapely.wkt
import xarray as xr
from pandas import DataFrame, Series
from shapely.geometry import Polygon, shape
from shapely.ops import transform
from skimage.draw import disk
from xarray import Dataset

from sisppeo.utils.exceptions import InputError
from sisppeo.utils.main import zonal_stats

# pylint: disable=invalid-name
# Ok for a custom type.
N = Union[int, float]
S = Union[str, str]


def get_enc(array, scale_factor, compression=False):
    min_ = np.nanmin(array)
    max_ = np.nanmax(array)
    if np.isnan(min_):
        enc = {'dtype': np.uint8, '_FillValue': 0}
    else:
        offset = min_ - 1
        min_, max_ = 1, max_ - offset
        if max_ <= 255 * scale_factor:
            dtype, fill_value = np.uint8, 0
        elif max_ <= 65535 * scale_factor:
            dtype, fill_value = np.uint16, 0
        elif max_ <= 4294967295 * scale_factor:
            dtype, fill_value = np.uint32, 0
        else:
            dtype, fill_value = np.uint64, 0
        enc = {'dtype': dtype, '_FillValue': fill_value,
               'scale_factor': scale_factor, 'add_offset': offset}
    if compression:
        enc.update({'zlib': True, 'complevel': 9})
        if min(_ for _ in array.shape if _ > 1) > 239:
            print(f'output {array.shape=}')
            enc['chunksizes'] = [1, 60, 60]
    return enc


def get_grid(n: int) -> Tuple[int, int]:
    """Gets the number of rows and columns needed according the number of subplots."""
    rows = (n + 2) // 3
    if n <= 3:
        cols = n
    elif n == 4:
        cols = 2
    else:
        cols = 3
    return rows, cols


def normalize_arr(arr, min_, max_, new_max=255):
    """Normalize an array between 0 and new_max.

    Args:
        arr: The input array.
        min_: The value to consider as being the min of the array.
        max_: The value to consider as being the min of the array.
        new_max: The maximum value of the output array.
    """
    return new_max * (arr - min_) / (max_ - min_)


class CoordinatesMixin:
    """A Mixin which adds extra properties and methods related to coordinates."""
    __slots__ = ()

    def _verify_data_vars(self, data_var):
        if data_var not in self.data_vars:
            msg = (f'"{data_var}" is not a variable of this product; please, '
                   f'choose one from the following list: {self.data_vars}.')
            raise InputError(msg)

    @property
    def bounds(self) -> Tuple[N, ...]:
        """Returns the boundaries of this product: (xmin, ymin, xmax, ymax)."""
        return (self.x.values.min() - self.res / 2,
                self.y.values.min() - self.res / 2,
                self.x.values.max() + self.res / 2,
                self.y.values.max() + self.res / 2)

    @property
    def res(self) -> N:
        """Returns the spatial resolution of this product."""
        res = self.dataset.x.values[1] - self.dataset.x.values[0]
        if isinstance(res, float):
            if res.is_integer():
                res = int(res)
        return res

    @property
    def x(self) -> xr.DataArray:
        """Returns x-coords."""
        return self.dataset.x

    @property
    def y(self) -> xr.DataArray:
        """Returns y-coords."""
        return self.dataset.y

    def xy(self, i, j) -> Tuple[int, int]:
        """Gets (x, y) from (i, j)."""
        if 0 <= i < len(self.y) and 0 <= j < len(self.x):
            return self.x.values[j], self.y.values[i]
        else:
            msg = (f'i ({i}) must be in [0, {len(self.y)}] ; '
                   f'j ({j}) must be in [0, {len(self.x)}]')
            raise InputError(msg)

    def index(self, x, y) -> Tuple[N, N]:
        """Gets (i, j) from (x, y)"""
        if self.bounds[0] <= x <= self.bounds[2] and self.bounds[1] <= y <= self.bounds[3]:
            j = bisect.bisect_right((self.x.values - self.res / 2).tolist(), x) - 1
            i = -bisect.bisect_left(sorted((self.y.values + self.res / 2).tolist()), y) + len(self.y) - 1
            return i, j
        else:
            msg = (f'x ({x}) must be in [{self.bounds[0]}, {self.bounds[2]}] ; '
                   f'y ({y}) must be in [{self.bounds[1]}, {self.bounds[3]}]')
            raise InputError(msg)

    def _reproject_to_dataset_crs(self, input_epsg: str, input_geom):
        """Reproject a shapely geom from a given CRS to the dataset's CRS"""
        # https://gis.stackexchange.com/a/328642
        project = pyproj.Transformer.from_crs(pyproj.CRS(input_epsg),
                                              pyproj.CRS.from_wkt(self.dataset.crs.attrs['crs_wkt']).to_string(),
                                              always_xy=True).transform
        return shapely.ops.transform(project, input_geom)

    def extract_point(self,
                      data_var: str,
                      coordinates: Tuple[N, N],
                      buffer: Optional[int] = None,
                      epsg: int = 4326,
                      mode: str = 'xy') -> xr.DataArray:
        """Returns value(s) at the given coordinates.

        Args:
            data_var: The name of the variable/DataArray of interest (e.g., a
                band, aCDOM, etc).
            coordinates: A tuple of geographic or projected coordinates; see
                "mode".
            buffer: Optional; The radius (in pixels) of the circle (centered on
                coordinates) to extract. Defaults to None.
            epsg: Optional; The EPSG code. Defaults to 4326.
            mode: Optional; Either 'xy' or 'latlon'. Defaults to 'xy'.

        Returns:
            An xr.DataArray containing the wanted information.
        """
        self._verify_data_vars(data_var)
        if mode == 'latlon' or epsg != 4326:
            transformer = pyproj.Transformer.from_crs(
                pyproj.CRS.from_epsg(epsg),
                pyproj.CRS.from_wkt(self.dataset.crs.attrs['crs_wkt']))
            coordinates = transformer.transform(*coordinates)
        # convert coordinates in columns and rows numbers
        i, j = self.index(*coordinates)  # = y, x
        if buffer is None:
            res = self.dataset[data_var].isel(y=i, x=j)
        else:
            # from the center coordinate, expand the selection to the size of the buffer (+x in every directions)
            res = self.dataset[data_var].isel(y=slice(i - buffer, i + buffer + 1),
                                              x=slice(j - buffer, j + buffer + 1))
            # create a nan array with the shape of the band array (time=0 useful only to get a proper shape tuple)
            mask = np.full(res.isel(time=0).shape, np.nan)
            # generate x and y (rr and cc) coordinates of pixels within a circle
            rr, cc = disk((buffer, buffer), buffer + 0.5)
            # assign the value 1 to the pixels at those coordinates in the array full of nans
            mask[rr, cc] = 1
            # multiply and reassign the mask to the result to mask out values out of the circle (being nan values)
            res *= mask
        return res

    def _extract_mask(self,
                      data_var: str,
                      data: xr.DataArray,
                      geom: str,
                      epsg: int,
                      buffer: int) -> xr.DataArray:
        """Extract statistics from a xarray masked by WKT or SHP geometry.

        Args:
            data_var: The name of the variable/DataArray of interest (e.g., a
                band, aCDOM, etc).
            geom: The geometry must be Point/MultiPoint/ or Polygon/MultiPolygon
                given as a WKT (well-known-text) or a path to a SHP (shapefile)
                and both having a single entity which could have several parts.
                The CRS for the WKT must be EPSG:4326 but don't need to be
                specified for the SHP.
            buffer: Optional; The distance of the buffer in units of the CRS of the dataset.
                A positive value means the buffer will be inside the polygon while a negative
                value means the buffer will be outside the polygon.

        Returns:
            A list of dictionaries containing:
                - the result of the mask as a xr.DataArray
                - another dictionary of the computed statistics
        """
        geometry = None
        # if the coordinates are recognized as such by the regex xp_coords:
        # ([LEFT BRACKET (round or square)][float number][COMA][SPACE][float number][RIGHT BRACKET (round or square)])
        # reconstruct it as a WKT string using f'strings then read it with shapely, otherwise
        # if the wkt string is recognized as such by matching the regular expression xp_wkt:
        # ([WORD][SPACE][( or (( or (((][floats until ) or )) or )))][))) or )) or )])
        # read it with shapely. Finally, if the string is an existing path to a shapefile,
        # read it with fiona first then with shapely then extract the CRS
        # https://stackoverflow.com/a/7124811
        xp_coords = "(\[|\()([+-]?\d*[.]?\d+)(,)( )([+-]?\d*[.]?\d+)(\]|\))"
        xp_wkt = "([A-Z]\w+)(| [A-Z])( |)(\(|\(\(|\(\(\(|)[+-]?\d*[.]?\d+.+?(?=\)\)\)|\)\)|\))(\)\)\)|\)\)|\))"
        if re.match(xp_coords, str(geom)):
            geometry = shapely.wkt.loads(f'POINT ({geom[0]} {geom[1]})')
            # WKT's CRS is hardocded because it must be WGS84:4326
            input_epsg = epsg
        elif re.match(xp_wkt, geom):
            geometry = shapely.wkt.loads(geom)
            # WKT's CRS is hardocded because it must be WGS84:4326
            input_epsg = epsg
        elif Path(geom).is_file() and Path(geom).suffix == '.shp':
            with fiona.open(geom) as shp:
                input_epsg = shp.crs['init'].upper()
                # If the shapefile has no CRS, default to 4326
                if input_epsg is None:
                    input_epsg = epsg
                    print(f'No CRS found for shapefile {geom}, defaulting to {input_epsg}.')
                for i in shp:
                    geometry = shapely.wkt.loads(str(shape(i['geometry'])))
        else:
            msg = f"{geom} doesn't exist or isn't a valid input file for geometry." \
                  f"The accepted geometries are SHAPEFILES (Given as an absolute file path)" \
                  f" and WELL-KNOWN-TEXT (CRS:WGS84 only)"
            raise InputError(msg)

        # eitherway, once the geom is loaded into a shapely object reproject to the array's crs (retrieved with self)
        geometry = self._reproject_to_dataset_crs(input_epsg=input_epsg, input_geom=geometry)

        # Check if the geometry overlap with the data
        xmin, ymin, xmax, ymax = self.bounds
        data_geom = Polygon([[xmin, ymin], [xmin, ymax], [xmax, ymax], [xmax, ymin]])
        if data_geom.intersects(geometry) is not True:
            msg = f"\nGeometry with bounds {geometry.bounds}\n" \
                  f" doesn't overlap with data of bounds {data_geom.bounds}"
            raise InputError(msg)

        # single sided = positif value => exterior, negative value => interior
        if buffer is not None:
            geometry_buffered = geometry.buffer(buffer, single_sided=True)
        else:
            geometry_buffered = geometry
        # if the area is equal to 0.0 it could means two things:
        #   - the geometry is a point to which no buffer (or one of 0m) has been applied
        #   - the geometry is a point or a polygon to which a negative buffer has been applied to the extent that it
        #      exceeded
        # In the second case, the geometry keeps its type even though its area is 0. That's why i retrieve the X and Y
        # coordinates using the centroid (the centroid of the point is still the same point )
        if geometry_buffered.area == 0.0:
            return self.extract_point(data_var=data_var, coordinates=(geometry.centroid.x, geometry.centroid.y),
                                      buffer=buffer, epsg=epsg, mode='latlon')
        else:
            # then rasterize the geometry filling the values with 1s (polygon) and 0s (not polygons)
            # https://rasterio.readthedocs.io/en/latest/api/rasterio.features.html#rasterio.features.geometry_mask
            _, y, x = data.shape
            # bounds: bottom left/top right coords: x/y: width:height
            affine = rasterio.transform.from_bounds(*self.bounds, x, y)
            mask = rasterio.features.geometry_mask(geometries=[geometry_buffered],
                                                   out_shape=(y, x),
                                                   transform=affine,
                                                   all_touched=True,
                                                   invert=True)
        return mask

    def _apply_mask(self, data, mask):
        # keep data where mask is true
        resd = xr.where(mask == True, data, np.nan)
        # Get the index of the mask cells
        resi = np.where(mask == True)
        # Fit to the bounding box of the values
        x1, x2, y1, y2 = np.min(resi[0]), np.max(resi[0]) + 1, np.min(resi[1]), np.max(resi[1]) + 1
        return resd.isel(y=slice(x1, x2), x=slice(y1, y2))

    def _extract_by_geoms(self,
                          data_var: str,
                          list_geom: list,
                          epsg: int,
                          buffer: int,
                          ):
        """Extract statistics from a xarray masked by WKT or SHP geom.

        Args:
            data_var: The name of the variable/DataArray of interest (e.g., a
                band, aCDOM, etc).
            list_geom: A list of geometries that must be Point/MultiPoint/ or Polygon/MultiPolygon
                given as a WKT (well-known-text) or a path to a SHP (shapefile)
                and both having a single entity which could have several parts.
                The CRS for the WKT must be EPSG:4326 but don't need to be
                specified for the SHP.
            epsg: The CRS used when the geom given as an input can't be found.
            buffer: Optional; The distance of the buffer in units of the CRS of the dataset.
                A positive value means the buffer will be inside the polygon while a negative
                value means the buffer will be outside the polygon.
        Returns:
            A list of dictionaries containing:
                - the result of the mask as a xr.DataArray
                - another dictionary of the computed statistics
        """
        # ensure inputs integrity
        if data_var is None:
            print('No data_vars arguments given, defaulting to every data_vars')
            datavars = self.data_vars
        else:
            if isinstance(list_geom, (list, tuple)) is not True:
                msg = (f'"list_geom" is not of a supported type. "list_geom" is of type <{type(list_geom).__name__}>'
                       f' whereas it should be of type (<list> or <tuple>).')
                raise InputError(msg)
            else:
                datavars = data_var

        result = []
        for geom in list_geom:
            datavar = datavars[0]
            self._verify_data_vars(datavar)
            mask = self._extract_mask(data_var=datavar, data=self.dataset[datavar].sel(time=self.dataset[datavar].time.values),
                                      geom=geom, epsg=epsg, buffer=buffer)
            for datavar in datavars:
                result.append(self._apply_mask(self.dataset[datavar], mask))
        return xr.merge(result)

    def stats(self, method=None, printres: bool = False) -> Union[DataFrame, Series, Dataset]:
        """
        """
        if method is None:
            method = ['x', 'y']
        methods = ['alldims', list(self.dataset.dims)[:2], list(self.dataset.dims)[-1:]]
        if method not in methods:
            msg = (f'"{method}" is not a known parameter of argument method. Valid parameters are: '
                   f' {methods}')
            raise InputError(msg)
        if method == 'alldims':
            # As a pandas DataFrame:
            d = []
            s = []
            for date in self.dataset.time.values:
                d.append(date)
                s.append(zonal_stats(self.dataset.sel(time=date).to_array()))
            result = pd.DataFrame({'date': d, 'stats': s})
            result = pd.concat([result, result['stats'].apply(pd.Series)], axis=1)
            result.drop('stats', axis=1, inplace=True)
            result.set_index('date')
            if printres:
                print(result)
            return result
        else:
            result = self.dataset.copy()
            result = result.assign(min=result.min(method, skipna=True).to_array(),
                                   mean=result.mean(method, skipna=True).to_array(),
                                   med=result.median(method, skipna=True).to_array(),
                                   max=result.max(method, skipna=True).to_array(),
                                   std=result.std(method, skipna=True).to_array(),
                                   sum=result.sum(method, skipna=True).to_array(),
                                   var=result.var(method, skipna=True).to_array())
            if printres:
                print(result)
            return result
