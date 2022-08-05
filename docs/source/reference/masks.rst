.. _masks:

*****
Masks
*****

.. currentmodule:: sisppeo.masks

SISPPEO can be used to create mask (e.g. cloud or water mask) from satellite
products.

:ref:`masks` contains the following algorithms:

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   
   s2cloudless
   waterdetect

References:

* s2cloudless: "Cloud Masks at Your Service", `Url <https://medium.com/sentinel-hub/cloud-masks-at-your-service-6e5b2cb2ce8a>`_, Sentinel Hub, Sinergise Ltd.
* waterdetect: Cordeiro, M. C. R.; Martinez, J.-M.; Peña-Luque, S. Automatic Water Detection from Multidimensional Hierarchical Clustering for Sentinel-2 Images and a Comparison with Level 2A Processors. Remote Sensing of Environment 2021, 253, 112209. `doi <https://doi.org/10.1016/j.rse.2020.112209>`_

.. autosummary::
   :toctree: generated
   :template: custom-class-template.rst
   :hidden:
   
   sisppeo.masks.sh_s2cloudless.cloud_detector
   sisppeo.masks.obs2co_s2wm.water_detector
