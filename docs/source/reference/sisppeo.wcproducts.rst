.. _wcproducts:

********************
sisppeo.wcproducts
********************

.. currentmodule:: sisppeo.wcproducts

This package is made of modules in which are defined algorithms
for water optics and water color remote sensing.

Each module is dedicated to one specific water quality parameter
(e.g. chlorophyll a) (except for :ref:`sisppeo.wcproducts.algos`).


.. _sisppeo.wcproducts.algos:

sisppeo.wcproducts.algos
========================

:ref:`sisppeo.wcproducts.algos` contains the following algorithms:

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   Ndwi


.. _sisppeo.wcproducts.acdom:

sisppeo.wcproducts.acdom
========================

This module gathers water colour algorithms used for retrieving aCDOM (/[DOC]).


.. _sisppeo.wcproducts.chla:

sisppeo.wcproducts.chla
=======================

The following algorithms are used for estimating Chl-a concentrations:

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   CHLAGons
   CHLAGitelson
   CHLAOC
   CHLALins
   NDCI


.. _sisppeo.wcproducts.spm:

sisppeo.wcproducts.spm
======================

The following algorithms are used for estimating suspended particulate matter
(SPM) concentrations:

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   SPMNechad
   SPMHan
   SPMGet
   TURBIDogliotti


.. _sisppeo.wcproducts.transparency:

sisppeo.wcproducts.transparency
===============================

The following algorithms are used for estimating transparency:

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   KDLee
