.. _overview:

**************
Quick overview
**************

Here are some quick examples of what you can do with
:py:class:`~sisppeo.products.l3.L3AlgoProduct` objects. Everything is explained
in much more detail in the rest of the documentation.

SISPPEO as a Python package
===========================

To begin, import SISPPEO:

.. code-block:: python

    import sisppeo
    from sisppeo.products import L3AlgoProduct

Then, you can:

* generate a L3 product (algo/mask) or a time series of L3 products
* load an existing L3 product
* plot stuff.

Generate a L3 product (L3AlgoProduct)
-------------------------------------

.. code-block:: python

    config = {
        'input_product': filepath,  # the filepath of your image
        'product_type': 'S2_GRS',   # which type of product it is ({sat}_{atm_corr})
        'algo': 'spm-get'           # which algorithm to use; this one derives SPM
    }
    l3product = sisppeo.generate('l3 algo', config)

See :doc:`this </user_guide/create_l3algo>`.

Read & write SISPPEO products (netCDF files)
--------------------------------------------

SISPPEO objects (L3AlgoProduct, L3MaskProduct, TimeSeries) are stored
as netCDF files (widely used in geosciences, very handy, and the xarray.Dataset
data model was inspired by it).

You can directly read and write SISPPEO objects from/to disk using the two
:py:meth:`~sisppeo.products.l3.L3AlgoProduct.from_file()` and
:py:meth:`~sisppeo.products.l3.L3AlgoProduct.save()` methods:

.. code-block:: python

    l3product = L3AlgoProduct.from_file('example.nc')
    l3product.save('example_bis.nc')

It is common for TimeSeries not to be saved as such but to be distributed
across multiple L3AlgoProduct files (=> one per date). You can compile them
by using :py:meth:`~sisppeo.products.timeseries.TimeSeries.from_files()`.

.. code-block:: python

    from sisppeo.products import TimeSeries

    timeseries = TimeSeries.from_files(['date1.nc', 'date2.nc'])

The Command Line Interface (or CLI)
===================================

(Almost) everything that you can do with SISPPEO as a package can be done
using the CLI.

The CLI can also be used to:

* print available algorithms and masks (using the :command:`algorithms` and :command:`masks` commands)
* set up :doc:`your own workspace </user_guide/user_workspace>`, where to store custom algorithms and configuration files without having to add it to SISPPEO and reinstall it
* check if each algorithm (included custom ones) is correctly registered (i.e., no missing parts) (using the `check_registration` command).
