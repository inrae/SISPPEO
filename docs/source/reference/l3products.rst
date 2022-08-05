.. _l3products:

***********
L3 Products
***********

.. automodule:: sisppeo.products.l3

.. currentmodule:: sisppeo.products


Constructing L3 products
========================

New L3 products can be constructed using:

* the top-level function :py:func:`sisppeo.generate`;
* the method :py:meth:`~L3Product.from_file`;
* the low-level :py:class:`L3AlgoProduct` and :py:class:`L3MaskProduct` constructors.

.. note::
    Using the low-level constructors involves that you must generate
    and correctly format the dataset you'll be using.

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   L3AlgoProduct
   L3MaskProduct


The inherited abstract class
----------------------------

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   L3Product


Masking L3 products
===================

.. autosummary::
   :toctree: generated
   
   mask_product


Querying spatial features
=========================

.. currentmodule:: sisppeo

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   sisppeo.utils.products.CoordinatesMixin
