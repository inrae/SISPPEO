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
