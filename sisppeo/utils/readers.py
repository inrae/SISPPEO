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
"""Contains various useful functions used by readers."""
from typing import List, Union

import numpy as np
from PIL import Image
from rasterio.windows import Window
from tqdm import tqdm

# pylint: disable=invalid-name
# Ok for a custom type.
N = Union[int, float]


def get_ij_bbox(subdataset, geom) -> List[int]:
    """Clips the subdataset with the geometry.

    Args:
        subdataset: An open rasterio.io DatasetReader.
        geom: A shapley geometry object.

    Returns:
        The corresponding bbox."""
    x_min, y_min, x_max, y_max = geom.bounds
    row_start, col_start = subdataset.index(x_min, y_max)
    row_start, col_start = max(0, row_start), max(0, col_start)
    row_stop, col_stop = subdataset.index(x_max, y_min)
    row_stop = min(subdataset.height - 1, row_stop)
    col_stop = min(subdataset.width - 1, col_stop)
    return [row_start, col_start, row_stop, col_stop]


def get_ij_bbox_from_ds(ds, geom):
    """Clips the subdataset with the geometry.

    Args:
        subdataset: A xarray dataset.
        geom: A shapley geometry object.

    Returns:
        The corresponding bbox."""
    x_min, y_min, x_max, y_max = geom.bounds
    row_start = float(ds.sel(x=x_min, method='nearest').x.values)
    col_start = float(ds.sel(y=y_max, method='nearest').y.values)
    row_stop = float(ds.sel(x=x_max, method='nearest').x.values)
    col_stop = float(ds.sel(y=y_min, method='nearest').y.values)
    return [row_start, row_stop, col_start, col_stop]


def decode_data(arr: np.ndarray,
                scale_factor: N,
                fill_value: N,
                offset: N = 0) -> np.ndarray:
    """Reads and decodes encoded data.

    Args:
        arr: The input encoded array of values.
        scale_factor: coefficient.
        fill_value ([type]): coefficient.
        offset: Optional; coefficient.

    Returns:
        The decoded array.
    """
    nan_arr = np.where(arr == fill_value, np.nan, arr)
    decoded_arr = scale_factor * nan_arr + offset
    return decoded_arr


def resample_band_array(arr: np.ndarray,
                        in_res: int,
                        out_res: int,
                        tqdm_: bool = True) -> np.ndarray:
    """Resamples an array.

    Args:
        arr: An array of (radiometric) values.
        in_res: The input resolution.
        out_res: The output resolution.
        tqdm_: Optional; True if in a tqdm loop.

    Returns:
        The resampled array.
    """
    scale_factor = in_res / out_res
    resampling_filter = Image.LANCZOS if scale_factor < 1 else Image.NEAREST
    msg = (f'\nscale factor: {scale_factor}, '
           f'resampling filter: {resampling_filter}')
    if tqdm_:
        tqdm.write(msg)
    else:
        print(msg)
    im = Image.fromarray(arr)
    im_new = im.resize(
        (int(im.width * scale_factor), int(im.height * scale_factor)),
        resample=resampling_filter
    )
    return np.array(im_new)


def resize_and_resample_band_array(arr: np.ndarray,
                                   ij_bbox: List[int],
                                   in_res: N,
                                   out_res: N,
                                   _tqdm: bool = True):
    """Resamples and resizes an array.

    Args:
        arr: An array of (radiometric) values.
        ij_bbox: The bbox of the ROI.
        in_res: The input resolution.
        out_res: The output resolution.
        _tqdm: Optional; True if in a tqdm loop.

    Returns:
        The resampled ROI.
    """
    row_start, col_start, row_stop, col_stop = ij_bbox
    scale_factor = in_res / out_res
    resampling_filter = Image.LANCZOS if scale_factor < 1 else Image.NEAREST
    msg = (f'\nscale factor: {scale_factor}, '
           f'resampling filter: {resampling_filter}')
    if _tqdm:
        tqdm.write(msg)
    else:
        print(msg)
    im = Image.fromarray(arr)
    im_new = im.resize(
        (int((col_stop - col_start + 1) * scale_factor),
         int((row_stop - row_start + 1) * scale_factor)),
        resample=resampling_filter
    )
    return np.array(im_new)


def _extract_nth_band(subdataset, xy_bbox):
    x0, y0, x1, y1 = xy_bbox
    row_start, col_start = subdataset.index(x0, y0)
    row_stop, col_stop = subdataset.index(x1, y1)
    arr = subdataset.read(1, window=Window.from_slices((row_start, row_stop + 1), (col_start, col_stop + 1)))
    return arr


def _extract_rad_coefs(metadata, band):
    # pylint: disable=invalid-name
    # M_rho is the name of a physical coefficients.
    M_rho = float(metadata['RADIOMETRIC_RESCALING'][f'REFLECTANCE_MULT_BAND_{band[1:]}'])
    # pylint: disable=invalid-name
    # A_rho is the name of a physical coefficients.
    A_rho = float(metadata['RADIOMETRIC_RESCALING'][f'REFLECTANCE_ADD_BAND_{band[1:]}'])
    # pylint: disable=invalid-name
    # theta_SE is the name of a physical coefficients.
    theta_SE = float(metadata['IMAGE_ATTRIBUTES']['SUN_ELEVATION'])
    return M_rho, A_rho, theta_SE


# pylint: disable=invalid-name
# M_rho, A_rho and theta_SE are name of physical coefficients.
def _digital_number_to_reflectance(arr, M_rho, A_rho, theta_SE):
    """Turn DNs into TOA Reflectances (corrected for the sun angle)"""
    nan_arr = np.where(arr == 0, np.nan, arr)
    rho_prime = M_rho * nan_arr + A_rho
    rho = rho_prime / np.sin(theta_SE * np.pi / 180)
    return rho
