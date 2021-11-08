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

"""This module contains the TimeSeries class.

A TimeSeries object is a new kind of product, made from either L1, L2, or L3
products, and allowing one to build a time series:

* Masks can be used to clip data.
* Basic statistics can be calculated.
* Generic plots can easily be made.

Example::

    paths = [<first S2_ESA_L2A product>, <second S2_ESA_L2A product>, ...,
           <n-th S2_ESA_L2A product>]
    mask_paths = [
        [<first water_mask>, <second water_mask>, ..., <n-th water_mask>],
        [<first mask2>
    config = {
        'paths': paths,
        'product_type': 'S2_ESA_L2A',
        'requested_bands': ['B2', 'B3', 'B4', 'B5', 'B6'],
        'wkt': wkt,
        'srid': 4326,
    }
    S2L2A_ts = factory.create('TS', **config)
    S2L2A_ts.compute_stats(<filename>)
    S2L2A_ts.plot()
"""

import warnings
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import plotly.figure_factory as ff
import plotly.graph_objects as go
import plotly.io as pio
import xarray as xr
from PIL import Image, ImageDraw, ImageFont
from plotly.subplots import make_subplots
from tqdm import tqdm

from sisppeo.utils.config import resources
from sisppeo.utils.lazy_loader import LazyLoader
from sisppeo.utils.products import (get_grid, get_enc, normalize_arr,
                                    CoordinatesMixin)
from sisppeo.utils.readers import resample_band_array

pio.templates.default = 'simple_white'
warnings.filterwarnings('ignore', category=xr.SerializationWarning)
colorcet = LazyLoader('colorcet', globals(), 'colorcet')
ds = LazyLoader('ds', globals(), 'datashader')

# pylint: disable=invalid-name
# P is a custom static type.
N = Union[int, float]
P = Union[Path, str]


@dataclass
class TimeSeries(CoordinatesMixin):
    """A 'L4' product, made from either L1, L2, or L3 products.

    This product contain one or more DataArrays (e.g., one for ndwi, one for
    each band extracted...). Each DataArrays is a data cube (i.e. 3D: x, y,
    time). It allows one to study time series of data, and compute and plot
    statistics over time and/or space.

    Attributes:
        dataset: A dataset containing one or more 3D-dataarrays.
    """
    __slots__ = 'dataset',
    dataset: xr.Dataset

    def __post_init__(self):
        self.dataset = self.dataset.sortby('time')

    @classmethod
    def from_file(cls, filename: Path):
        """Load a TimeSeries object from disk.

        Args:
            filename: The path of the netCDF file.

        Returns:
            A TimeSeries object (i.e. a 3D dataset : time, x, y).
        """
        return TimeSeries(xr.open_dataset(filename))

    @classmethod
    def from_files(cls, paths: List[Path]):
        """Load and merge a list of L3 products from disk.

        Args:
            paths: A list of paths (to L3 products saved as netCDF files).

        Returns:
            A TimeSeries object (i.e. a 3D dataset : time, x, y).
        """
        ts = xr.open_mfdataset(paths, concat_dim='time', combine='nested',
                               join='inner', data_vars='minimal',
                               coords='minimal', compat='override')
        return TimeSeries(ts)

    @classmethod
    def from_l3products(cls, lst: Iterable):
        """Load and merge a list of L3 products.

        Args:
            lst: A list of L3 products (loaded in memory).

        Returns:
            A TimeSeries object (i.e. a 3D dataset : time, x, y).
        """
        ts = xr.concat([product.dataset for product in lst], dim='time',
                       data_vars='minimal', coords='minimal',
                       compat='override', join='inner',
                       combine_attrs='override')
        return TimeSeries(ts)

    @property
    def title(self) -> str:
        """Returns the title of the underlying dataset."""
        return self.dataset.attrs.get('title')

    @property
    def data_vars(self):
        """Returns a list of DataArrays corresponding to variables."""
        return [data_var for data_var in self.dataset.data_vars
                if data_var not in ('crs', 'product_metadata')]

    @property
    def start_date(self) -> pd.Timestamp:
        """Return the start date."""
        return self.dataset.get_index('time').min()

    @property
    def end_date(self) -> pd.Timestamp:
        """Return the end date."""
        return self.dataset.get_index('time').max()

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

    def compute_stats(self, filename: P, plot: bool = True) -> None:
        """Computes (and save on disk) statistics about embedded data at each date.

        Args:
            filename: The path of the output product (a CSV file).
            plot: A boolean flag that indicates if computed statistics should
                be plotted or not.
        """
        lst_df = []
        for var in tqdm(self.data_vars, unit='vars'):
            lst_series = []
            for date in tqdm(self.dataset.time.values, leave=False,
                             unit='dates'):
                mean = float(self.dataset[var].sel(time=str(date)).mean())
                std = float(self.dataset[var].sel(time=str(date)).std())
                min_ = float(self.dataset[var].sel(time=str(date)).min())
                q1 = float(
                    self.dataset[var].sel(time=str(date)).quantile(0.25)
                )
                median = np.nanmedian(self.dataset[var].sel(time=str(date)).values)
                q3 = float(
                    self.dataset[var].sel(time=str(date)).quantile(0.75)
                )
                max_ = float(self.dataset[var].sel(time=str(date)).max())
                series = pd.Series(
                    data=[mean, std, min_, q1, median, q3, max_],
                    index=['mean', 'std', 'min', 'q1', 'median', 'q3', 'max'],
                    name=str(date)
                )
                lst_series.append(series)
            df = pd.concat(lst_series, axis=1).transpose()
            if plot:
                lst_df.append(df)
            df.to_csv(f'{filename}_{var}.csv', index_label='date')
        if plot:
            for df in lst_df:
                print(df)

    def _grayscale_timelapse(self, data_var: str, filename: P,
                             out_res: Optional[int] = None, write_time: bool = True):
        min_ = np.nanmin(self.dataset[data_var].values)
        max_ = np.nanmax(self.dataset[data_var].values)
        lst_img = [Image.fromarray(normalize_arr(
            cond_resample(self.dataset[data_var].isel(time=i).values, self.res,
                          out_res), min_, max_
        ).astype(np.uint8)) for i in range(len(self.dataset.time))]
        if write_time:
            font = ImageFont.truetype(str(resources / 'fonts/Ubuntu-R.ttf'),
                                      32)
            for i, img in enumerate(lst_img):
                draw = ImageDraw.Draw(img)
                draw.text((10, img.height-10),
                          self.dataset.get_index('time')[i].isoformat(),
                          255, font, 'lb', stroke_width=2, stroke_fill=127)
        lst_img[0].save(filename, save_all=True, append_images=lst_img[1:],
                        duration=1500, optimize=True)

    def _rgb_timelapse(self, data_vars: List[str], filename: P,
                       out_res: Optional[int] = None, write_time: bool = True):
        min_ = {data_var: np.nanmin(self.dataset[data_var].values)
                for data_var in data_vars}
        max_ = {data_var: np.nanmax(self.dataset[data_var].values)
                for data_var in data_vars}
        lst_img = [Image.fromarray(np.stack([normalize_arr(
            cond_resample(self.dataset.isel(time=i)[data_var].values, self.res,
                          out_res), min_[data_var], max_[data_var]
        ).astype(np.uint8) for data_var in data_vars], axis=-1), mode='RGB')
                   for i in range(len(self.dataset.time))]
        if write_time:
            font = ImageFont.truetype(str(resources / 'fonts/Ubuntu-R.ttf'),
                                      32)
            for i, img in enumerate(lst_img):
                draw = ImageDraw.Draw(img)
                draw.text(
                    (10, img.height-10),
                    self.dataset.get_index('time')[i].isoformat(),
                    'yellow', font, 'lb', stroke_width=2, stroke_fill='red'
                )
        lst_img[0].save(filename, save_all=True, append_images=lst_img[1:],
                        duration=1500, optimize=True)

    def timelapse(self, data_vars: Union[str, List[str]], filename: P,
                  out_res: Optional[int] = None, write_time: bool = True):
        """Creates a timelapse and save it on disk (as a GIF file).

        Args:
            data_vars: The data_var(s) to plot; 1 for a grayscale image, and a
                list of 3 for a RGB one.
            filename: The path of the output gif.
            out_res: The resolution of the timelapse; must be coarser than the
                one of the time series.
            write_time: If True, the corresponding date will be written on each
                frame.
        """
        if isinstance(data_vars, str):
            self._grayscale_timelapse(data_vars, filename, out_res, write_time)
        else:
            self._rgb_timelapse(data_vars, filename, out_res, write_time)

    def _plot_1d_1var(self, data_var, lst_coordinates, buffer=None, epsg=4326,
                      mode='xy'):
        fig = go.Figure()
        lst_data = self.extract_points(data_var, lst_coordinates, buffer, epsg,
                                       mode)
        for i, (data, coordinates) in enumerate(zip(lst_data, lst_coordinates)):
            if buffer is not None:
                data = np.nanmean(data)
            fig.add_trace(go.Scatter(
                x=self.dataset.time.values,
                y=data,
                name=f'Point {i + 1} ({coordinates[0]}, {coordinates[1]})'
            ))
        fig.update_xaxes(title_text='date')
        fig.update_yaxes(title_text=self.dataset[data_var].long_name)
        return fig

    def _plot_1d_nvars(self, data_vars, lst_coordinates, buffer=None,
                       epsg=4326, mode='xy'):
        rows, cols = get_grid(len(data_vars))
        fig = make_subplots(rows=rows, cols=cols, shared_xaxes=True,
                            vertical_spacing=0.05, horizontal_spacing=0.05)
        for i, data_var in enumerate(data_vars):
            row = i // cols + 1
            col = i % cols + 1
            lst_data = self.extract_points(data_var, lst_coordinates, buffer,
                                           epsg, mode)
            for j, (data, coordinates) in enumerate(zip(lst_data,
                                                        lst_coordinates)):
                if buffer is not None:
                    data = np.nanmean(data)
                fig.add_trace(go.Scatter(
                    x=self.dataset.time.values,
                    y=data,
                    name=f'Point {j + 1} ({coordinates[0]}, {coordinates[1]})'
                ), row=row, col=col)
            fig.update_xaxes(title_text='date')
            fig.update_yaxes(title_text=self.dataset[data_var].long_name)
        width = 450 * cols
        height = 450 * rows
        fig.update_layout(width=width, height=height,
                          margin={'b': 0, 'l': 0, 'r': 0, 't': 0})
        return fig

    # pylint: disable=too-many-locals
    # 17 local variables is acceptable here (plotting stuff).
    def plot_1d(self,
                lst_coordinates: Union[Tuple[int, int], List[Tuple[int, int]]],
                data_var: Union[str, List[str]] = 'all',
                buffer=None,
                epsg=4326,
                mode='xy',
                filename: Optional[P] = None,
                fmt: str = 'jpeg') -> None:
        """Plots time series of data_var(s) for one or more given points.

        Args:
            lst_coordinates: A tuple of coordinates (x, y) that locates the
                point to extract (/a list of tuples of coordinates, locating
                points of interest).
            data_var: Optional; A variable (e.g. "aCDOM") or a list of
                variables to plot.
            buffer:
            epsg:
            mode:
            filename: Optional; If a filename is provided, the figure will be
                saved using this path.
            fmt: The format of the exported figure. Can be either "png",
                "jpeg", "webp", "svg" or "pdf".
        """
        if isinstance(lst_coordinates, tuple):
            lst_coordinates = [lst_coordinates]
        if data_var == 'all':
            data_var = self.data_vars
        if isinstance(data_var, list):
            fig = self._plot_1d_nvars(data_var, lst_coordinates, buffer, epsg,
                                      mode)
        else:
            fig = self._plot_1d_1var(data_var, lst_coordinates, buffer, epsg,
                                     mode)
        fig.show()
        if filename is not None:
            fig.write_image(f'{filename}.{fmt}')

    # pylint: disable=too-many-locals
    # 17 local variables is acceptable here (plotting stuff).
    def plot_2d(self,
                data_vars: Union[str, List[str]] = 'all',
                filename: Optional[P] = None,
                fmt: str = 'jpeg') -> None:
        """Plots timelapse as a mosaic (one per data_var).

        For each data_var, create a figure composed of multiples subplots, each
        one of them being a image of the given data_var at a given date.

        Args:
            data_vars: A variable (e.g. "aCDOM") or a list for variables to
                plot. If 'all', creates a figure for each variable (i.e.
                DataArray) embedded into this dataset.
            filename: Optional; If a filename is provided, the figure will be
                saved using this path.
            fmt: The format of the exported figure. Can be either "png",
                "jpeg", "webp", "svg" or "pdf".
        """
        if data_vars == 'all':
            data_vars = self.data_vars
        elif isinstance(data_vars, str):
            data_vars = [data_vars]
        x = self.dataset.x.values
        y = self.dataset.y.values
        for data_var in data_vars:
            rows, cols = get_grid(len(self.dataset.time))
            fig = make_subplots(rows=rows, cols=cols,
                                shared_yaxes=True, shared_xaxes=True,
                                subplot_titles=[str(time) for time
                                                in self.dataset.time.values],
                                vertical_spacing=0.05, horizontal_spacing=0.05)
            for i, row in enumerate(range(1, rows + 1)):
                for j, col in enumerate(range(1, cols + 1)):
                    data = self.dataset[data_var].isel(time=i + j).values
                    if len(x) + len(y) >= 9000:
                        z = ds.Canvas(
                            plot_width=np.round(len(x) / 10).astype(np.int16),
                            plot_height=np.round(len(y) / 10).astype(np.int16)
                        ).raster(data)
                    else:
                        z = data
                    fig.add_trace(go.Heatmap(z=z, x=x, y=y, hoverongaps=False,
                                             coloraxis='coloraxis'), row, col)
                    if row == rows:
                        fig.update_xaxes(title_text=self.dataset.x.long_name,
                                         row=row, col=col)
                    if col == 1:
                        fig.update_yaxes(title_text=self.dataset.y.long_name,
                                         row=row, col=col)
            fig.update_xaxes(showline=False)
            fig.update_yaxes(showline=False)
            width = 450 * cols
            height = 450 * rows
            fig.update_layout(coloraxis={'colorscale': colorcet.rainbow,
                                         'colorbar': {'title': data_var}},
                              width=width, height=height,
                              margin={'b': 0, 'l': 0, 'r': 0, 't': 50})
            fig.show()
            if filename is not None:
                fig.write_image(f'{filename}.{fmt}')

    def get_mean_map(self,
                     var: str,
                     plot: bool = True,
                     filename: Optional[P] = None,
                     save: bool = False,
                     savefig: bool = False,
                     fmt: str = 'jpeg') -> xr.DataArray:
        """Gets the map of (temporal) mean values for a given data_var.

        Compute a map (a DataArray of dimension N * M) from a DataArray of
        dimension t * N * M. Each pixel of this map is the mean value of the
        N * M t-vectors.

        Args:
            var: The name of the DataArray to use.
            plot: A boolean flag that indicates if the figure should be
                plotted or not.
            filename: Optional; The path of the output product (a figure and/or
                a netCDF file).
            save: Optional; A boolean flag that indicates if the mean map
                should be saved on disk or not.
            savefig: Optional; A boolean flag that indicates if the figure
                should be saved or not.
            fmt: The format of the static image that is saved on disk. Can be
                either "png", "jpeg", "webp", "svg" or "pdf".

        Returns:
            A map (a dataarray of dimension N * M) of mean values for a given
            data_var.
        """
        res = self.dataset[var].mean(dim='time')
        if plot:
            if len(res.x) + len(res.y) >= 9000:
                z = ds.Canvas(
                    plot_width=np.round(len(res.x) / 10).astype(np.int16),
                    plot_height=np.round(len(res.y) / 10).astype(np.int16)
                ).raster(res)
            else:
                z = res
            fig = go.Figure(go.Heatmap(
                z=z, x=res.x.values, y=res.y.values,
                hoverongaps=False,
                colorscale=colorcet.rainbow, colorbar={'title': var}
            ))
            fig.update_xaxes(title_text=self.dataset.x.long_name,
                             showline=False)
            fig.update_yaxes(title_text=self.dataset.y.long_name,
                             showline=False, )
            fig.update_layout(width=900, height=900,
                              margin={'b': 0, 'l': 0, 'r': 0, 't': 0})
            fig.show()
            if savefig and filename is not None:
                fig.write_image(f'{filename}.{fmt}')
        if save and filename is not None:
            np.save(filename, res, False)
        return res

    def get_min_map(self,
                    var: str,
                    plot: bool = True,
                    filename: Optional[P] = None,
                    save: bool = False,
                    savefig: bool = False,
                    fmt: str = 'jpeg') -> xr.DataArray:
        """Gets the map of (temporal) min values for a given data_var.

        Compute a map (a dataarray of dimension N * M) from a dataarray of
        dimension t * N * M. Each pixel of this map is the min value of the
        N * M t-vectors.

        Args:
            var: The name of the dataarray to use.
            plot: A boolean flag that indicates if the figure should be
                plotted or not.
            filename: Optional; The path of the output product (a figure and/or
                a netCDF file).
            save: Optional; A boolean flag that indicates if the mean map
                should be saved on disk or not.
            savefig: Optional; A boolean flag that indicates if the figure
                should be saved or not.
            fmt: The format of the static image that is saved on disk. Can be
                either "png", "jpeg", "webp", "svg" or "pdf".

        Returns:
            A map (a dataarray of dimension N * M) of min values for a given
            data_var.
        """
        res = self.dataset[var].min(dim='time')
        if plot:
            if len(res.x) + len(res.y) >= 9000:
                z = ds.Canvas(
                    plot_width=np.round(len(res.x) / 10).astype(np.int16),
                    plot_height=np.round(len(res.y) / 10).astype(np.int16)
                ).raster(res)
            else:
                z = res
            fig = go.Figure(go.Heatmap(
                z=z, x=res.x.values, y=res.y.values,
                hoverongaps=False,
                colorscale=colorcet.rainbow, colorbar={'title': var}
            ))
            fig.update_xaxes(title_text=self.dataset.x.long_name,
                             showline=False)
            fig.update_yaxes(title_text=self.dataset.y.long_name,
                             showline=False)
            fig.update_layout(width=900, height=900,
                              margin={'b': 0, 'l': 0, 'r': 0, 't': 0})
            fig.show()
            if savefig and filename is not None:
                fig.write_image(f'{filename}.{fmt}')
        if save and filename is not None:
            np.save(filename, res, False)
        return res

    def get_max_map(self,
                    var: str,
                    plot: bool = True,
                    filename: Optional[P] = None,
                    save: bool = False,
                    savefig: bool = False,
                    fmt: str = 'jpeg') -> xr.DataArray:
        """Gets the map of (temporal) max values for a given data_var.

        Compute a map (a dataarray of dimension N * M) from a dataarray of
        dimension t * N * M. Each pixel of this map is the max value of the
        N * M t-vectors.

        Args:
            var: The name of the dataarray to use.
            plot: A boolean flag that indicates if the figure should be
                plotted or not.
            filename: Optional; The path of the output product (a figure and/or
                a netCDF file).
            save: Optional; A boolean flag that indicates if the mean map
                should be saved on disk or not.
            savefig: Optional; A boolean flag that indicates if the figure
                should be saved or not.
            fmt: The format of the static image that is saved on disk. Can be
                either "png", "jpeg", "webp", "svg" or "pdf".

        Returns:
            A map (a dataarray of dimension N * M) of max values for a given
            data_var.
        """
        res = self.dataset[var].max(dim='time')
        if plot:
            if len(res.x) + len(res.y) >= 9000:
                z = ds.Canvas(
                    plot_width=np.round(len(res.x) / 10).astype(np.int16),
                    plot_height=np.round(len(res.y) / 10).astype(np.int16)
                ).raster(res)
            else:
                z = res
            fig = go.Figure(go.Heatmap(
                z=z, x=res.x.values, y=res.y.values,
                hoverongaps=False,
                colorscale=colorcet.rainbow, colorbar={'title': var}
            ))
            fig.update_xaxes(title_text=self.dataset.x.long_name,
                             showline=False)
            fig.update_yaxes(title_text=self.dataset.y.long_name,
                             showline=False)
            fig.update_layout(width=900, height=900,
                              margin={'b': 0, 'l': 0, 'r': 0, 't': 0})
            fig.show()
            if savefig and filename is not None:
                fig.write_image(f'{filename}.{fmt}')
        if save and filename is not None:
            np.save(filename, res, False)
        return res

    def plot_stats_maps(self,
                        data_vars: Union[str, List[str]] = 'all',
                        filename: P = None,
                        savefig: bool = False,
                        fmt: str = 'jpeg') -> None:
        """Plots a figure of stats (temporal mean/min/max) map (one per data_var).

        For each data_var, create a figure composed of 3 subplots : a mean-,
        min-, and max-map.
        See 'get_mean_map', 'get_min_map', and 'get_max_map' for more
        information about what the so-called maps are.

        Args:
            data_vars: The name of the dataarray to plot. If 'all', create a
                figure for each dataarray (i.e. for each data_var in
                data_vars).
            filename: Optional; The path of the output figure.
            savefig: Optional; A boolean flag that indicates if the figure
                should be saved or not.
            fmt: The format of the static image that is saved on disk. Can be
                either "png", "jpeg", "webp", "svg" or "pdf".
        """
        if data_vars == 'all':
            data_vars = self.data_vars
        else:
            data_vars = [data_vars]
        for var in data_vars:
            mean_map = self.get_mean_map(var, False)
            min_map = self.get_min_map(var, False)
            max_map = self.get_max_map(var, False)
            if len(self.dataset.x) + len(self.dataset.y) >= 9000:
                mean_map = ds.Canvas(
                    plot_width=np.round(len(self.dataset.x)
                                        / 10).astype(np.int16),
                    plot_height=np.round(len(self.dataset.y)
                                         / 10).astype(np.int16)
                ).raster(mean_map)
                min_map = ds.Canvas(
                    plot_width=np.round(len(self.dataset.x)
                                        / 10).astype(np.int16),
                    plot_height=np.round(len(self.dataset.y)
                                         / 10).astype(np.int16)
                ).raster(min_map)
                max_map = ds.Canvas(
                    plot_width=np.round(len(self.dataset.x)
                                        / 10).astype(np.int16),
                    plot_height=np.round(len(self.dataset.y)
                                         / 10).astype(np.int16)
                ).raster(max_map)
            fig = make_subplots(rows=1, cols=3, shared_yaxes=True,
                                subplot_titles=['mean', 'min', 'max'],
                                horizontal_spacing=0.05)
            fig.add_trace(go.Heatmap(z=mean_map,
                                     x=self.dataset.x.values,
                                     y=self.dataset.y.values,
                                     hoverongaps=False,
                                     coloraxis='coloraxis'),
                          row=1, col=1)
            fig.add_trace(go.Heatmap(z=min_map,
                                     x=self.dataset.x.values,
                                     y=self.dataset.y.values,
                                     hoverongaps=False,
                                     coloraxis='coloraxis'),
                          row=1, col=2)
            fig.add_trace(go.Heatmap(z=max_map,
                                     x=self.dataset.x.values,
                                     y=self.dataset.y.values,
                                     hoverongaps=False,
                                     coloraxis='coloraxis'),
                          row=1, col=3)
            fig.update_xaxes(title_text=self.dataset.x.long_name,
                             showline=False)
            fig.update_yaxes(title_text=self.dataset.y.long_name,
                             showline=False)
            fig.update_layout(coloraxis={'colorscale': colorcet.rainbow,
                                         'colorbar': {'title': var}},
                              width=1350, height=450,
                              margin={'b': 0, 'l': 0, 'r': 0, 't': 50})
            fig.show()
            if savefig and filename is not None:
                fig.write_image(f'{filename}.{fmt}')

    def plot_hists(self,
                   data_vars: Union[str, List[str]] = 'all',
                   dates: Union[str, List[str]] = 'all',
                   plot: bool = True,
                   filename: Optional[P] = None,
                   fmt: str = 'jpeg') -> None:
        """Plots an histogram (per data_var, per date).

        For each data_var, at each date, plots an histogram using the right
        array of values.

        Args:
            data_vars: The name of the dataarray to plot. If 'all', create a
                figure for each dataarray (i.e. for each data_var in
                data_vars).
            dates: The wanted date. If 'all', create a histogram for each date.
            plot: A boolean flag that indicates if the figure should be
                plotted or not.
            filename: Optional; The path of the output figure.
            fmt: The format of the static image that is saved on disk. Can be
                either "png", "jpeg", "webp", "svg" or "pdf".
        """
        if data_vars == 'all':
            data_vars = self.data_vars
        else:
            data_vars = [data_vars]
        if dates == 'all':
            dates = self.dataset.time.values
        else:
            dates = [dates]
        for var in data_vars:
            hist_data, group_labels = [], []
            for date in dates:
                data = self.dataset[var].sel(time=str(date)).values.flatten()
                hist_data.append(data[~np.isnan(data)])
                group_labels.append(f'{var}_{str(date)}')
            fig = ff.create_distplot(hist_data, group_labels)
            if plot:
                fig.show()
            if filename is not None:
                fig.write_image(f'{filename}_{var}.{fmt}')


def mask_time_series(ts_algo: TimeSeries,
                     ts_masks: Union[TimeSeries, List[TimeSeries]],
                     lst_mask_type: Union[str, List[str]],
                     inplace=False) -> Optional[TimeSeries]:
    """Masks time series of L3AlgoProducts.

    Masks a TimeSeries made of L3AlgoProducts with one (or multiple ones)
    made of L3MaskProducts. It can be used for instance to get rid of clouds
    or to extract only water areas.

    Args:
        ts_algo: The TimeSeries to be masked.
        ts_masks: The TimeSeries or list of TimeSeries to use as mask (/list of
            masks).
        lst_mask_type: The type of the input mask (or the list of the types of
            input masks). Can either be 'IN' or 'OUT', indicating if the
            corresponding mask is inclusive or exclusive.
        inplace: If True, do operation inplace and return None.

    Returns:
        A masked TimeSeries.
    """
    if not inplace:
        ts_algo = deepcopy(ts_algo)
    if isinstance(ts_masks, TimeSeries):
        ts_masks = [ts_masks]
    if isinstance(lst_mask_type, str):
        lst_mask_type = [lst_mask_type]
    # Get the shared bounding box (i.e. intersection)
    x_min = max([ts_mask.x.values.min() for ts_mask in ts_masks]
                + [ts_algo.x.values.min()])
    x_max = min([ts_mask.x.values.max() for ts_mask in ts_masks]
                + [ts_algo.x.values.max()])
    y_min = max([ts_mask.y.values.min() for ts_mask in ts_masks]
                + [ts_algo.y.values.min()])
    y_max = min([ts_mask.y.values.max() for ts_mask in ts_masks]
                + [ts_algo.y.values.max()])
    # Clip masks with the previous bounding box
    arr_masks = [ts_mask.dataset[ts_mask.title.split(' ', 1)[0]].sel(
                 x=slice(x_min, x_max), y=slice(y_max, y_min)).values
                 for ts_mask in ts_masks]
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
    for var in ts_algo.data_vars:
        ts_algo.dataset = ts_algo.dataset.sel(x=slice(x_min, x_max),
                                              y=slice(y_max, y_min))
        ts_algo.dataset[var].values = np.where(mask,
                                               ts_algo.dataset[var].values,
                                               np.nan)
    # Store masks' names
    masks = []
    dico = {'s2cloudless': 'cloudmask', 'waterdetect': 'watermask'}
    for ts_mask, mask_type in zip(ts_masks, lst_mask_type):
        mask = ts_mask.title.split(' ', 1)[0]
        if mask in ('s2cloudless', 'waterdetect'):
            version = ts_mask.dataset[mask].attrs['version']
            ts_algo.dataset.attrs[dico[mask]] = f'{mask} ({version}) [{mask_type}]'
        else:
            masks.append(f'{mask} [{mask_type}]')
    if masks:
        ts_algo.dataset.attrs['masks'] = masks
    if not inplace:
        return ts_algo
    return None


def cond_resample(arr, in_res, out_res):
    """See resample_band_array(...)."""
    if out_res is None or in_res == out_res:
        return arr
    else:
        return resample_band_array(arr, in_res, out_res, False)
