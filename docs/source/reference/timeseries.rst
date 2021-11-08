.. _time_series:

***********
Time series
***********

.. automodule:: sisppeo.products.timeseries

.. currentmodule:: sisppeo.products


Constructing time series
========================

TimeSeries objects can be constructed using:

* the top-level function :py:func:`sisppeo.generate`;
* the three methods :py:meth:`TimeSeries.from_file`, :py:meth:`TimeSeries.from_files`, and :py:meth:`TimeSeries.from_l3products`;
* the low-level :py:class:`TimeSeries` constructor.

.. note::
    Using the low-level constructor involves that you must generate
    and correctly format the dataset you'll be using.

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   TimeSeries


Masking time series
===================

.. autosummary::
   :toctree: generated
   
   mask_time_series


Querying spatial features
=========================

.. currentmodule:: sisppeo

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   sisppeo.utils.products.CoordinatesMixin
