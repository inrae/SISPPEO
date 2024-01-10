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

from setuptools import setup, find_packages


def readme():
    with open('README.md', 'r') as f:
        return f.read()


setup(
    name='SISPPEO',
    version='1.1.2',
    description='Satellite Imagery & Signal Processing Packages for Earth Observation',
    long_description=readme(),
    url='https://github.com/inrae/SISPPEO',
    author='A. Coqué',
    author_email='arthur.coque@inrae.fr',
    license='Apache 2.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'affine',
        'click',
        'colorcet',
        'datashader',
        'fiona',
        'lxml',
        'matplotlib',
        'netcdf4',
        'numpy',
        'pandas',
        'pillow',
        'plotly',
        'psutil',
        'pvlib',
        'pyproj',
        'pyyaml',
        'rasterio',
        'ray',
        's2cloudless',
        'scikit-image',
        'scikit-learn',
        'scipy',
        'shapely',
        'tqdm',
        'xarray',
    ],
    python_requires='>=3.8',
    entry_points='''
        [console_scripts]
        sisppeo=sisppeo.cli:cli
    ''',
    zip_safe=False
)
