.. _readers:

*************
Reader object
*************

.. automodule:: sisppeo.readers.reader


The abstract class
==================

.. currentmodule:: sisppeo.readers.reader

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   Reader


Custom namedtuples
==================

.. autosummary::
   
   Inputs
   ROI


Available readers
=================

.. currentmodule:: sisppeo.readers

Numerous readers are availables.

For Sentinel-2 products:

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   S2ESAReader
   S2THEIAReader
   GRSReader
   C2RCCReader

For Landsat 8 products:

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   L8USGSL1C1Reader
   L8USGSL2Reader
   GRSReader
   C2RCCReader
