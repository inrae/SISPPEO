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

"""This module contains a reader for L8_USGS_L2C1 products with hdf files.

    Typical usage example:

    reader = L8USGSL2C1HDFReader(**config)
    reader.extract_bands()
    reader.create_ds()
    extracted_dataset = reader.dataset
"""

import io
import tarfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio
import xarray as xr
from pyproj import CRS
from rasterio.windows import Window
from tqdm import tqdm

from sisppeo.readers.reader import Reader
from sisppeo.utils.readers import get_ij_bbox, decode_data


def format_zippath(path: Path) -> str:
    return f'tar://{str(path.resolve())}!/'


class L8USGSL2Reader(Reader):
    """A reader dedicated to extract data from L8_USGS_L2C1 products (.hdf).

    Attributes:
        dataset: A dataset containing extracted data.
    """

    def extract_bands(self) -> None:
        """See base class."""
        # Load data
        compressed = False
        if self._inputs['input_product'].suffix == '.gz':   # .tar.gz
            compressed = True
            root_path = format_zippath(self._inputs['input_product'])
            with tarfile.open(self._inputs['input_product']) as archive:
                hdf_path = [_ for _ in archive.getnames()
                            if _.endswith('.hdf')][0]
            with rasterio.Env(RAW_CHECK_FILE_SIZE=False):
                dataset = rasterio.open(root_path + hdf_path)
        else:
            dataset = rasterio.open(
                list(self._inputs['input_product'].glob('*.hdf'))[0]
            )

        # Load metadata
        metadata = {'tags': dataset.tags()}     # useful ?
        metadata.update(self._load_metadata_from_MTL(compressed))

        # Filter subdatasets
        f_subdatasets = [subdataset for subdataset in dataset.subdatasets
                         if subdataset.rsplit(':', 1)[1][:4] == 'sr_b']
        requested_bands = [(subdataset, b) for subdataset in f_subdatasets
                           if (b := subdataset.rsplit('_', 1)[1].replace(
                               'band', 'B'))
                           in self._inputs['requested_bands']]

        # Extract data
        data = {}
        for path, band in tqdm(requested_bands, unit='bands'):
            with rasterio.open(path) as subdataset:
                if self._intermediate_data['x'] is None:
                    # Store the CRS
                    self._intermediate_data['crs'] = CRS.from_epsg(
                        # pylint: disable=no-member
                        # False positive.
                        subdataset.crs.to_epsg()
                    )
                    band_array, xy_bbox = self._extract_first_band(subdataset)
                else:
                    band_array = _extract_nth_band(subdataset, xy_bbox)
                data[band] = band_array.reshape(1, *band_array.shape)
        dataset.close()
        print('')

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
                'time': [datetime.fromisoformat(
                    self._intermediate_data['metadata']['MTL'][
                        'PRODUCT_METADATA']['DATE_ACQUIRED']
                    + 'T'
                    + self._intermediate_data['metadata']['MTL'][
                        'PRODUCT_METADATA']['SCENE_CENTER_TIME'][:-2]
                )]
            }
        )
        crs = self._intermediate_data['crs']
        # Set up coordinate variables
        ds.x.attrs['axis'] = 'X'
        ds.x.attrs['long_name'] = f'x-coordinate ({crs.name})'
        ds.x.attrs['standard_name'] = 'projection_x_coordinate'
        ds.x.attrs['units'] = 'm'
        ds.y.attrs['axis'] = 'Y'
        ds.y.attrs['long_name'] = f'y-coordinate ({crs.name})'
        ds.y.attrs['standard_name'] = 'projection_y_coordinate'
        ds.y.attrs['units'] = 'm'
        ds.time.attrs['axis'] = 'T'
        ds.time.attrs['long_name'] = 'time'

        # Set up the 'grid mapping variable'
        ds['crs'] = xr.DataArray(name='crs', attrs=crs.to_cf())

        # Store metadata
        ds['product_metadata'] = xr.DataArray()
        for key, val in self._intermediate_data['metadata']['tags'].items():
            ds.product_metadata.attrs[key] = val
        for key, val in {
            f'{key1}:{key2}': val for key1
            in self._intermediate_data['metadata']['MTL'] for key2, val
            in self._intermediate_data['metadata']['MTL'][key1].items()
        }.items():
            ds.product_metadata.attrs[key] = val

        ds.attrs['data_type'] = 'rho'
        self.dataset = ds

    # pylint: disable=invalid-name
    # MTL is the name given by the USGS to the file containing metadata.
    def _load_metadata_from_MTL(self, compressed):
        if compressed:
            with tarfile.open(self._inputs['input_product']) as archive:
                path = [_ for _ in archive.getnames()
                        if _.endswith('MTL.txt')][0]
                with io.TextIOWrapper(archive.extractfile(path)) as f:
                    lines = f.readlines()
        else:
            path = list(self._inputs['input_product'].glob('*MTL.txt'))[0]
            with open(path, 'r') as f:
                lines = f.readlines()
        metadata = defaultdict(dict)
        key = None
        for line in lines[1:-2]:
            line = line.lstrip(' ').rstrip('\n').replace('"', '').split(' = ')
            if line[0] == 'GROUP':
                metadata['MTL'][line[1]] = {}
                key = line[1]
            elif line[0] == 'END_GROUP':
                continue
            else:
                metadata['MTL'][key][line[0]] = line[1]
        return metadata

    def _compute_x_coords(self, x0, x1):
        x_start = x0 + 15
        x_stop = x1 - 15
        self._intermediate_data['x'] = np.arange(x_start, x_stop + 1, 30)

    def _compute_y_coords(self, y0, y1):
        y_start = y0 - 15
        y_stop = y1 + 15
        self._intermediate_data['y'] = np.arange(y_start, y_stop - 1, -30)

    def _extract_first_band(self, subdataset):
        if self._inputs['geom'] is not None:
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
        # Get encoding parameters
        scale_factor = float(subdataset.tags()['scale_factor'])
        fill_value = float(subdataset.tags()['_FillValue'])
        # Decode extracted data
        band_array = decode_data(arr, scale_factor, fill_value)
        # Compute projected coordinates
        self._compute_x_coords(x0, x1)
        self._compute_y_coords(y0, y1)
        # Update internal coords
        x1 -= 1
        y1 += 1
        return band_array, [x0, y0, x1, y1]


def _extract_nth_band(subdataset, xy_bbox):
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
    # Get encoding parameters
    scale_factor = float(subdataset.tags()['scale_factor'])
    fill_value = float(subdataset.tags()['_FillValue'])
    # Decode extracted data
    band_array = decode_data(arr, scale_factor, fill_value)
    return band_array
