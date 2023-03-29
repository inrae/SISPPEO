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

import sisppeo.masks.waterdetect as wd
from sisppeo.utils.algos import producttype_to_sat
from sisppeo.utils.config import mask_config
from sisppeo.utils.exceptions import InputError


def overlay_water_mask(image, mask, figsize=(15, 15)):
    """Utility function for plotting RGB images with binary mask overlayed."""
    import matplotlib.pyplot as plt
    plt.figure(figsize=figsize)
    plt.imshow(image)
    plt.imshow(np.where(mask == 1, 1., np.nan), vmin=0., vmax=1.)
    plt.show()


class WaterDetect:
    """WaterDetect algorithm (OBS2CO processing chain).

    Algorithm to generate open water cover mask, specially conceived for L2A
    Sentinel-2 imagery from MAJA processor, without any a priori knowledge
    on the scene.
    This algorithm was published in Cordeiro, Martinez and Peña-Luque (2021).

    Attributes:
        name: The name of the algorithm used. This is the key used by
            L3AlgoBuilder and that you must provide in config or when using
            the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: An empty dict, since there is no parametrisation for WaterDetect.
    """
    name = 'waterdetect'

    def __init__(self, product_type: str, **_ignored) -> None:
        """Inits a 'WaterDetect' instance for a given 'product_type'.

        Args:
            product_type: The type of the input satellite product (e.g.
                S2_ESA_L2A or L8_USGS_L1GT).
            **_ignored: Unused kwargs sent to trash.
        """
        try:
            self.requested_bands = mask_config[self.name][
                producttype_to_sat(product_type)]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with {self.name}'
            raise InputError(msg) from invalid_product
        self.meta = {'version': f'v{wd.__version__}', 'bands_keys': 'mndwi, ndwi, Mir2'}

    def __call__(self, bands: List[DataArray], **_ignored) -> Tuple[np.ndarray]:
        """Compute the WaterDetect water mask.

        Args:
            bands: List of extracted bands (from satellite products).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            An DataArray (dimension 1 * N * M) of flagged water surface.
        """
        print('Generating mask...')
        img = np.stack([band[0] for band in bands], axis=-1)
        mask = np.where(np.isnan(bands[0][0]), True, False)
        bands_ = wd.DWutils.create_bands_dict(img, ['Green', 'Nir', 'Mir', 'Mir2'])
        image = wd.DWImageClustering(bands=bands_, bands_keys=['mndwi', 'ndwi', 'Mir2'],
                                     invalid_mask=mask, config=wd.DWConfig())
        image.run_detect_water()
        water_mask = np.where(image.water_mask == 1, 1, 0)
        print('Done.')
        return water_mask.astype(np.uint8).reshape((1, *water_mask.shape))
