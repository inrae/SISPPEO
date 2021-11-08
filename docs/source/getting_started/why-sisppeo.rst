.. _why:

*************
Why SISPPEO ?
*************

**SISPPEO** allows scientists to write remote sensing algorithms
without having to worry about which satellite product will be used
- specific steps like reading/extracting data, or formatting output products
are already implemented.

Moreover, this package includes various carefully selected algorithms
from the literature, allowing users to derive for example Chl-a concentrations
or water turbidity in a river, or to detect burnt areas (`NBR`__).

__ https://un-spider.org/advisory-support/recommended-practices/recommended-practice-burn-severity/in-detail/normalized-burn-ratio

How does it work ?
==================

1. Data is extracted using "readers" (one per (satellite / atmospheric correction) couple).
2. The chosen algorithm is applied.
3. An output product (called a "L3 product") is built and saved as a well-formatted NetCDF file (CF-1.8).

How to add an algorithm to SISPPEO ?
====================================

Basically, you just need to write a function that takes *n* bands
(as :code:`xr.DataArray`) as parameters and returns one or more arrays.
Which bands are used (e.g., depending the satellite) is defined in a YAML file:

.. code-block:: yaml

    ndwi:
    long_name: Normalized Difference Water Index
    output: ndwi
    L8:
        - B3
        - B5
    S2:
        - B3
        - B8

For more details, please see the corresponding :doc:`tutorial </development/add_algo>`.

What if there is no reader for my product ?
===========================================

For now, SISPPEO can read:

* S2 products from ESA (both L1C and L2A)
* L8 products from USGS (both L1C1 and L2C1)
* S2 L2A and L8 L2 **GRS** products (`T. Harmel et al., 2018 <https://doi.org/10.1016/j.rse.2017.10.022>`__)
* S2 L2A **C2RCC** products (`Brockmann Consult <https://www.brockmann-consult.de/portfolio/water-quality-from-space/>`__)
* S2 L2A **MAJA** products (`O. Hagolle et al., 2017 <https://doi.org/10.5281/zenodo.1209633>`__)

You can write a new reader and add it to SISPPEO. It is really super easy to do
(cf. :doc:`this tutorial </development/add_reader>`).
