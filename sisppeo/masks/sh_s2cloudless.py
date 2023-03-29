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

"""This module contains functions related to the s2cloudless package.

The logic is encapsulated inside the function named 'cloud_detector'.

Example::

    out_array = cloud_detector([input_arrays])
"""

from pathlib import Path
from typing import List, Tuple, Union

import numpy as np
import s2cloudless
from xarray import DataArray

from sisppeo.utils.algos import load_calib, producttype_to_sat
from sisppeo.utils.config import mask_calib, mask_config
from sisppeo.utils.exceptions import InputError

P = Union[str, Path]


def overlay_cloud_mask(image, mask, figsize=(15, 15)):
    """Utility function for plotting RGB images with binary mask overlayed."""
    import matplotlib.pyplot as plt
    plt.figure(figsize=figsize)
    plt.imshow(image)
    plt.imshow(np.where(mask == 1, 1., np.nan), vmin=0., vmax=1.)
    plt.show()


class S2Cloudless:
    """s2cloudless algorithm (Sentinel Hub).

    Algorithm to detect cloud in Sentinel-2 imagery.

    Attributes:
        name: The name of the algorithm used. This is the key used by
          L3AlgoBuilder and that you must provide in config or when using
          the CLI.
        requested_bands: A list of bands further used by the algorithm.
        meta: A dict of metadata (calibration name, model coefficients, etc).
    """
    _default_calibration_file = mask_calib / 's2cloudless.yaml'
    _default_calibration_name = 'sentinel-hub_example'
    name = 's2cloudless'

    def __init__(self, product_type: str, calibration: P = _default_calibration_name, **_ignored) -> None:
        """Inits a 'S2Cloudless' instance with specific settings.

        Args:
            product_type: The type of the input satellite product
                (must be S2_ESA_L1C).
            **_ignored: Unused kwargs sent to trash.
        """
        try:
            self.requested_bands = mask_config[self.name][
                producttype_to_sat(product_type)]
        except KeyError as invalid_product:
            msg = f'{product_type} is not allowed with {self.name}'
            raise InputError(msg) from invalid_product
        calibration_dict, calibration_name = load_calib(
            calibration,
            self._default_calibration_file,
            self._default_calibration_name
        )
        self.__dict__.update(calibration_dict)
        self.meta = {'version': f'v{s2cloudless.__version__}', 'calibration': calibration_name, **calibration_dict}
        # Initialize the cloud detector
        self.cloud_detector = s2cloudless.S2PixelCloudDetector(threshold=self.threshold,
                                                               average_over=self.average_over,
                                                               dilation_size=self.dilation_size,
                                                               all_bands=False)

    def __call__(self, bands: List[DataArray], **_ignored) -> Tuple[np.ndarray]:
        """Compute the s2cloudless cloud mask.

        Args:
            bands: List of extracted bands (from satellite products).
            **_ignored: Unused kwargs sent to trash.

        Returns:
            Two DataArrays (dimension 1 * N * M) of flagged clouds and cloud
            probabilities.
        """
        print('Generating mask...')
        # Run the classification
        img = np.stack([band[0, :, :] for band in bands], axis=-1)
        img.resize((1, *img.shape))
        cloud_masks = self.cloud_detector.get_cloud_masks(img)
        cloud_probs = self.cloud_detector.get_cloud_probability_maps(img)
        print('Done.')
        return cloud_masks.astype(np.uint8), cloud_probs
