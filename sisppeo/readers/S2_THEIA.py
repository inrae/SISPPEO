# Copyright 2020 Arthur Coqué, Valentine Aubard, Pôle OFB-INRAE ECLA, UR RECOVER
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

"""This module contains a reader for S2_THEIA products.

This reader is dedicated to extract data from S2_THEIA_L2A.

Example::

    reader = S2THEIAReader(**config)
    reader.extract_bands()
    reader.create_ds()
    extracted_dataset = reader.dataset
"""

import warnings
from collections import defaultdict, namedtuple
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from zipfile import ZipFile

import numpy as np
import rasterio
import xarray as xr
from lxml import etree
from pyproj import CRS
from rasterio.windows import Window
from tqdm import tqdm

from sisppeo.readers.reader import Reader, Inputs
from sisppeo.utils.exceptions import InputError, ProductError
from sisppeo.utils.readers import (get_ij_bbox, decode_data,
                                   resample_band_array,
                                   resize_and_resample_band_array)

warnings.filterwarnings('ignore', category=rasterio.errors.NotGeoreferencedWarning)

S2THEIAInputs = namedtuple('S2THEIAInputs', Inputs._fields
                           + ('out_resolution', 'theia_bands', 'theia_masks'))


def format_zippath(path: Path) -> str:
    return f'zip://{str(path.resolve())}!/'


class S2THEIAReader(Reader):
    """A reader dedicated to extract data from S2_THEIA_L2A products.

    For more information about THEIA S2 L2A products, please see:
    https://labo.obs-mip.fr/multitemp/sentinel-2/theias-sentinel-2-l2a-product-format/

    Attributes:
        dataset: A dataset containing extracted data.
    """

    def __init__(self,
                 input_product: Path,
                 requested_bands: List[str],
                 geom: Optional[dict] = None,
                 out_resolution: Optional[int] = None,
                 theia_bands: str = 'FRE',
                 theia_masks: Optional[Dict[str, Optional[List[int]]]] = None,
                 **_ignored) -> None:
        """See base class.

        Args:
            out_resolution: The wanted resolution of the output product. Used
                when performing resampling operations.
            theia_bands: The bands to be extracted. Must be either "SRE"
                (for Surface REflectance) or "FRE" (for Flat REflectance).
            theia_masks: A dict whose keys are the names of THEIA's masks to
                extract ("CLM", "MG2" or "SAT") and vals are lists of bits to
                use (e.g., [0, 1, 2] ; if None, all bits will be used for the
                corresponding mask).
        """
        super().__init__(input_product, requested_bands, geom)
        if out_resolution not in (None, 10, 20):
            raise InputError('"out_resolution" must be in (10, 20)')
        if theia_bands not in ('FRE', 'SRE'):
            raise InputError('"theia_bands" must be either "SRE" or "FRE"')
        self._inputs = S2THEIAInputs(*self._inputs, out_resolution,
                                     theia_bands, theia_masks)

    def extract_bands(self) -> None:
        """See base class."""
        # Check if data are compressed
        compressed = False
        if self._inputs.input_product.suffix == '.zip':
            compressed = True

        # Load metadata
        metadata = self._load_metadata_from_MTD(compressed)
        quantification_value, nodata = _get_product_coefs(metadata)

        # Filter bands
        if compressed:
            with ZipFile(self._inputs.input_product) as archive:
                root_path = format_zippath(self._inputs.input_product)
                try:
                    requested_bands = [
                        (root_path + [_ for _ in archive.namelist() if _.endswith(
                            f'_{self._inputs.theia_bands}_{band}.tif'
                        )][0], band) for band in self._inputs.requested_bands
                    ]
                except IndexError as no_band:
                    msg = ('One of the requested bands is not found in the '
                           'given product.')
                    raise ProductError(msg) from no_band
        else:
            try:
                requested_bands = [
                    (list(self._inputs.input_product.glob(
                        f'*_{self._inputs.theia_bands}_{band}.tif'
                    ))[0], band) for band in self._inputs.requested_bands
                ]
            except IndexError as no_band:
                msg = ('One of the requested bands is not found in the given '
                       'product.')
                raise ProductError(msg) from no_band

        tmp = ['R1' if band in ('B2', 'B3', 'B4', 'B8') else 'R2'
               for band in self._inputs.requested_bands]
        if 'R1' in tmp and 'R2' in tmp:
            requested_bands = [rband for _, rband
                               in sorted(zip(tmp, requested_bands),
                                         reverse=True)]
        if 'R1' in tmp:
            min_res = 10
        else:
            min_res = 20
        # Set the default resolution
        if self._inputs.out_resolution is None:
            self._inputs = self._inputs._replace(out_resolution=min_res)

        # Extract data
        data = {}
        for path, band in tqdm(requested_bands, unit='bands'):
            with rasterio.open(path) as subdataset:
                if self._intermediate_data['x'] is None:    # 1st extracted_band
                    if ((out_res := self._inputs.out_resolution)
                            > (in_res := subdataset.res[0])):
                        msg = (f'"out_resolution" must be <= {in_res} ; '
                               f'here, out_resolution={out_res}')
                        raise InputError(msg)
                    # Store the CRS
                    self._intermediate_data['crs'] = CRS.from_epsg(
                        subdataset.crs.to_epsg()
                    )
                    band_array, xy_bbox = self._extract_first_band(
                        subdataset, quantification_value, nodata
                    )
                else:
                    band_array = self._extract_nth_band(
                        subdataset, xy_bbox, quantification_value, nodata
                    )
                data[band] = band_array.reshape(1, *band_array.shape)
        print('')

        # Mask data
        if self._inputs.theia_masks is not None:
            for mask_name in self._inputs.theia_masks:
                if self._inputs.out_resolution == 10:
                    suffix = '_R1'
                else:
                    suffix = '_R2'
                if compressed:
                    with ZipFile(self._inputs.input_product) as archive:
                        mask_path = (root_path + [
                            _ for _ in archive.namelist()
                            if _.endswith(f'_{mask_name}{suffix}.tif')
                        ][0])
                else:
                    mask_path = list((self._inputs.input_product / 'MASKS'
                                      ).glob(f'*_{mask_name}{suffix}.tif'))[0]
                with rasterio.open(mask_path) as mask:
                    mask_array = self._extract_nth_band(mask, xy_bbox, 1, 1,
                                                        mask=True)
                if self._inputs.theia_masks[mask_name] is None:
                    self._inputs.theia_masks[mask_name] = range(8)
                bitmasks = [mask_array & (1 << b)
                            for b in self._inputs.theia_masks[mask_name]]
                mask_array *= np.any(bitmasks, axis=0)
                for band in data:
                    data[band] = np.where(mask_array, np.nan, data[band])

        # Store outputs
        self._intermediate_data['data'] = data
        self._intermediate_data['metadata'] = metadata

    def create_ds(self) -> None:
        """See base class."""
        # Create the dataset
        ds = xr.Dataset(
            {key: (['time', 'y', 'x'], val) for key, val
             in self._intermediate_data['data'].items()},
            coords={
                'x': ('x', self._intermediate_data['x']),
                'y': ('y', self._intermediate_data['y']),
                'time': [datetime.fromisoformat(self._intermediate_data[
                    'metadata']['ACQUISITION_DATE'].split('.')[0])]
            }
        )
        crs = self._intermediate_data['crs']
        # Set up coordinate variables
        ds.x.attrs['axis'] = 'X'
        ds.x.attrs['long_name'] = f'x-coordinate ({crs.name})'
        ds.x.attrs['standard_name'] = "projection_x_coordinate"
        ds.x.attrs['units'] = 'm'
        ds.y.attrs['axis'] = 'Y'
        ds.y.attrs['long_name'] = f'y-coordinate ({crs.name})'
        ds.y.attrs['standard_name'] = "projection_y_coordinate"
        ds.y.attrs['units'] = 'm'
        ds.time.attrs['axis'] = 'T'
        ds.time.attrs['long_name'] = 'time'

        # Set up the 'grid mapping variable'
        ds['crs'] = xr.DataArray(name='crs', attrs=crs.to_cf())

        # Store metadata
        ds['product_metadata'] = xr.DataArray()
        for key, val in self._intermediate_data['metadata'].items():
            ds.product_metadata.attrs[key] = val

        ds.attrs['data_type'] = 'rho'
        ds.attrs['theia_bands'] = self._inputs.theia_bands
        if self._inputs.theia_masks is not None:
            ds.attrs['suppl_masks'] = ', '.join(
                f'THEIA_{key} ({"".join([str(b) for b in val])})'
                for key, val in self._inputs.theia_masks.items()
            )
        self.dataset = ds

    def _load_metadata_from_MTD(self, compressed):
        if compressed:
            with ZipFile(self._inputs.input_product) as archive:
                path = [_ for _ in archive.namelist() if _.endswith('MTD_ALL.xml')][0]
                with archive.open(path) as f:
                    tree = etree.parse(f)
        else:
            path = list(self._inputs.input_product.glob('*MTD_ALL.xml'))[0]
            with open(path) as f:
                tree = etree.parse(f)
        root = tree.getroot()
        metadata = defaultdict(dict)
        for elem in root:
            for subelem in elem:
                try:
                    if subelem.text.strip():
                        metadata[subelem.tag] = subelem.text
                except AttributeError:
                    pass # Done in the next two lines
                for att in subelem.attrib:
                    metadata[':'.join([subelem.tag, att])] = subelem.attrib.get(att)
        for elem in root.iter('Horizontal_Coordinate_System'):
            for subelem in elem:
                metadata[subelem.tag] = subelem.text
        for elem in root.iter('SPECIAL_VALUE'):
            metadata[elem.get('name')] = elem.text
        for elem in root.iter('QUALITY_INDEX'):
            metadata[elem.get('name')] = elem.text
        for elem in root.iter('Processing_Information'):
            metadata[elem.find('NAME').text] = elem.find('VALUE').text
        return metadata

    def _compute_x_coords(self, x0, x1):
        out_res = self._inputs.out_resolution
        x_start = x0 + out_res / 2
        x_stop = x1 - out_res / 2
        self._intermediate_data['x'] = np.arange(x_start, x_stop + 1, out_res)

    def _compute_y_coords(self, y0, y1):
        out_res = self._inputs.out_resolution
        y_start = y0 - out_res / 2
        y_stop = y1 + out_res / 2
        self._intermediate_data['y'] = np.arange(y_start, y_stop - 1, -out_res)

    # pylint: disable=too-many-locals
    # False positive.
    def _extract_first_band(self, subdataset, quantification_value, nodata):
        if self._inputs.ROI is not None:
            self._reproject_geom()
            row_start, col_start, row_stop, col_stop = get_ij_bbox(
                subdataset,
                self._intermediate_data['geom']
            )
            arr = subdataset.read(
                1,
                window=Window.from_slices((row_start, row_stop + 1),
                                          (col_start, col_stop + 1))
            )
            # Update internal coords
            x0, y0 = subdataset.transform * (col_start, row_start)
            x1, y1 = subdataset.transform * (col_stop + 1, row_stop + 1)
        else:
            arr = subdataset.read(1)
            # Update internal coords
            x0, y0 = subdataset.transform * (0, 0)
            x1, y1 = subdataset.transform * (subdataset.width,
                                             subdataset.height)
        # Decode extracted data
        band_array = decode_data(arr, 1 / quantification_value, nodata)
        if (out_res := self._inputs.out_resolution) != subdataset.res[0]:
            band_array = resample_band_array(band_array, subdataset.res[0],
                                             out_res)
        # Compute projected coordinates
        self._compute_x_coords(x0, x1)
        self._compute_y_coords(y0, y1)
        # Update internal coords
        x1 -= 1
        y1 += 1
        return band_array, [x0, y0, x1, y1]

    # pylint: disable=too-many-locals
    # More readable if coordonates are explicitely extracted from the bbox.
    def _extract_nth_band(self, subdataset, xy_bbox, quantification_value,
                          nodata, mask=False):
        x0, y0, x1, y1 = xy_bbox
        row_start, col_start = subdataset.index(x0, y0)
        row_stop, col_stop = subdataset.index(x1, y1)
        arr = subdataset.read(
            1,
            window=Window.from_slices(
                (row_start, row_stop + 1),
                (col_start, col_stop + 1)
            )
        )
        if mask:
            band_array = arr
        else:
            # Decode extracted data
            band_array = decode_data(arr, 1 / quantification_value, nodata)
            ij_bbox = [row_start, col_start, row_stop, col_stop]
            if (out_res := self._inputs.out_resolution) != subdataset.res[0]:
                band_array = resize_and_resample_band_array(band_array, ij_bbox,
                                                            subdataset.res[0],
                                                            out_res)
        return band_array


def _get_product_coefs(metadata):
    """Gets both quantification and nodata values (to compute correct reflectances)"""
    quantification_value = float(metadata['REFLECTANCE_QUANTIFICATION_VALUE'])
    nodata = float(metadata['nodata'])
    return quantification_value, nodata
