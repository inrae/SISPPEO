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

"""This module contains functions related to the wmOBS2CO package.

The logic is encapsulated inside the function named 'water_detector'.

Example::

    out_array = water_detector([input_arrays])
"""

from typing import List, Tuple

import numpy as np
from xarray import DataArray
import logging
import sisppeo.masks.waterdetect as wd


def overlay_water_mask(image, mask, figsize=(15, 15)):
    """Utility function for plotting RGB images with binary mask overlayed."""
    import matplotlib.pyplot as plt
    plt.figure(figsize=figsize)
    plt.imshow(image)
    plt.imshow(np.where(mask == 1, 1., np.nan), vmin=0., vmax=1.)
    plt.show()


def water_detector(bands: List[DataArray],
                   plot: bool = False) -> Tuple[np.ndarray, dict]:
    """Compute the wmOBS2CO water mask.

    Args:
        bands: List of extracted bands (from S2 or L8_GRS).
        plot: A boolean flag that indicates if a figure should be plotted or
            not.

    Returns:
        An DataArray (dimension 1 * N * M) of flagged water surface.
    """
    logging.info('Generating mask...')

    img = np.stack([band[0] for band in bands], axis=-1)
    mask = np.where(np.isnan(bands[0][0]), True, False)
    bands_ = wd.DWutils.create_bands_dict(img, ['Green', 'Nir', 'Mir', 'Mir2'])
    image = wd.DWImageClustering(bands=bands_, bands_keys=['mndwi', 'ndwi', 'Mir2'],
                                 invalid_mask=mask, config=wd.DWConfig())
    image.run_detect_water()
    water_mask = np.where(image.water_mask == 1, 1, 0)

    if plot:
        b8 = bands[2][0, :, :]
        overlay_water_mask(b8, water_mask)
        logging.info(water_mask)

    logging.info('Done.')
    meta = {'version': f'v{wd.__version__}', 'bands_keys': 'mndwi, ndwi, Mir2'}
    return water_mask.astype(np.uint8).reshape((1, *water_mask.shape)), meta


setattr(water_detector, 'version', f'v{wd.__version__}')
