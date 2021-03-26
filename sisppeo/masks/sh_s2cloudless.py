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

    Typical usage example:

    out_array = cloud_detector([input_arrays])
"""

from typing import List, Tuple

import numpy as np
import s2cloudless
from xarray import DataArray


def overlay_cloud_mask(image, mask, figsize=(15, 15)):
    """Utility function for plotting RGB images with binary mask overlayed."""
    import matplotlib.pyplot as plt
    plt.figure(figsize=figsize)
    plt.imshow(image)
    plt.imshow(np.where(mask == 1, 1., np.nan), vmin=0., vmax=1.)
    plt.show()


def cloud_detector(bands: List[DataArray],
                   plot: bool = False) -> Tuple[np.ndarray, dict]:
    """Compute the s2cloudless cloud mask.

    Args:
        bands: List of extracted bands (from S2_GRS or L8_GRS).
        plot: A boolean flag that indicates if a figure should be plotted or
            not.

    Returns:
        A DataArray (dimension 1 * N * M) of flagged clouds.
    """
    print('Generating mask...')
    # Initialize the cloud detector
    cloud_detector_ = s2cloudless.S2PixelCloudDetector(threshold=0.4,
                                                       average_over=4,
                                                       dilation_size=2)

    # Run the classification
    img = np.stack([band[0, :, :] for band in bands], axis=-1)
    img.resize((1, *img.shape))
    cloud_masks = cloud_detector_.get_cloud_masks(img)
    # cloud_probs = cloud_detector.get_cloud_probability_maps(img)

    if plot:
        band8 = bands[4][0, :, :]
        overlay_cloud_mask(band8, cloud_masks[0])
        print(cloud_masks)

    print('Done.')
    meta = {'version': f'v{s2cloudless.__version__}', 'threshold': 0.4,
            'average_over': 4, 'dilation_size': 2}
    return cloud_masks.astype(np.uint8), meta


setattr(cloud_detector, 'version', f'v{s2cloudless.__version__}')
