.. _installing:

************
Installation
************

Instructions
============

SISPPEO itself is a pure Python package, but its dependencies are not.
The easiest way to get everything installed properly is to use conda_.

.. _conda: http://conda.io/

You will first have to clone the GitLab repository:

.. code-block:: shell

    $ git clone https://gitlab.irstea.fr/telquel-obs2co/satellite/sisppeo.git
    $ cd sisppeo

Then, you will need to create a virtual environment (optional,
but strongly advised) and install SISPPEO.

* using conda (recommended):

.. code-block:: shell

    $ conda env create -f conda/environment.yml
    $ pip install .

* using virtualenv and pip:

.. code-block:: shell

    $ python3 -m venv venv
    $ source venv/bin/activate

   $ pip install -U .

If you don't use conda, be sure you have the required dependencies. Indeed,
some packages (like rasterio/GDAL) require extra installation steps
and though are excluded.

Required dependencies
=====================

- Python (3.8 or later)
- setuptools
- `numpy <http://www.numpy.org/>`__
- `pandas <http://pandas.pydata.org/>`__
- `xarray <https://xarray.pydata.org>`__

For netCDF and IO
-----------------
- `netCDF4 <https://github.com/Unidata/netcdf4-python>`__: for reading or writing netCDF files.
- `rasterio <https://github.com/mapbox/rasterio>`__: for reading GeoTiffs and other gridded raster datasets.


For parallel and distributed computing
--------------------------------------
- `ray <https://ray.io/>`__

For plotting
------------
- `matplotlib <http://matplotlib.org/>`__: required for plotting (using xarray.Dataset internal functions)
- `plotly <https://plotly.com/python/>`__: required for custom plots from L3 products.

Others
------
- affine
- click
- colorcet
- datashader
- fiona
- lxml
- pillow
- psutils
- pvlib
- pyproj
- pyyaml
- s2cloudless
- scikit-image
- scikit-learn
- scipy
- shapely
- tqdm
