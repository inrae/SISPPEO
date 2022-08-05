:notoc:

****************************************************************************
SISPPEO: Satellite Imagery & Signal Processing Package for Earth Observation
****************************************************************************

**SISPPEO** is an open source project and Python package (with a CLI) allowing one to extract synthetic information useful for Earth observation (Water and Land) from satellite optical imagery (e.g, Sentinel-2/MSI, Sentinel-3/OLCI, Landsat 8/OLI...).

**SISPPEO** is built on top of xarray_ and uses Ray_ for distributed computing. Outputs are netCDF_ files.

.. _xarray: https://xarray.pydata.org
.. _Ray: https://ray.io/
.. _netCDF: http://www.unidata.ucar.edu/software/netcdf

**SISPPEO** is the successor of an internal processing chain previously used by members of the `"Colours of the continental waters" SEC`_ (Scientific Expertise Centre). This tool is developed by `"Pôle ÉCLA"`_ (OFB_/INRAE_/USMB_) scientists based in Aix-En-Provence.

.. _"Colours of the continental waters" SEC: https://www.theia-land.fr/en/ceslist/colours-of-the-continental-waters-sec/
.. _"Pôle ÉCLA": https://professionnels.ofb.fr/fr/pole-ecla-ecosystemes-lacustres
.. _OFB: https://ofb.gouv.fr/en/french-biodiversity-agency-ofb
.. _INRAE: https://www.inrae.fr/en/about-us
.. _USMB: https://www.univ-smb.fr/en/universite/

.. panels::
    :card: + intro-card text-center
    :column: col-lg-6 col-md-6 col-sm-6 col-xs-12 d-flex

    ---
    :img-top: _static/index-baby-yoda.svg

    Getting started
    ^^^^^^^^^^^^^^^

    New to **SISPPEO**? Check out the getting started guides. They contain an
    introduction to *SISPPEO'* main concepts.

    +++

    .. link-button:: getting_started
            :type: ref
            :text: To the getting started guides
            :classes: btn-block btn-secondary stretched-link

    ---
    :img-top: _static/index-stormtrooper.svg

    User guide
    ^^^^^^^^^^

    The user guide provides in-depth information on the key concepts
    of **SISPPEO** with useful background information and explanation.

    +++

    .. link-button:: user
            :type: ref
            :text: To the user guide
            :classes: btn-block btn-secondary stretched-link

    ---
    :img-top: _static/index_book.svg

    API reference
    ^^^^^^^^^^^^^

    The reference guide contains a detailed description of the **SISPPEO**
    package. The reference describes how the methods work and which parameters
    can be used. It assumes that you have an understanding of the key concepts.

    +++

    .. link-button:: reference
            :type: ref
            :text: To the reference guide
            :classes: btn-block btn-secondary stretched-link

    ---
    :img-top: _static/index-r2-d2.svg

    Developer guide
    ^^^^^^^^^^^^^^^

    Want to add a new reader/algorithm ? This guides will show you
    how to extend SISPPEO.

    +++

    .. link-button:: development
            :type: ref
            :text: To the development guide
            :classes: btn-block btn-secondary stretched-link


.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: For users
   
   Getting Started <getting_started/index>
   User Guide <user_guide/index>
   API Reference <reference/index>
   
.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: For developers/contributors
   
   Extending SISPPEO <development/index>

.. toctree::
   :maxdepth: 2
   :hidden:
   
   Team <team>


Get in touch
------------

- If you have a question or need complementary information, please i) carefuly read the documentation, ii) look at :ref:`the API Reference<reference>` and  then iii) contact me_.
- Report bugs, suggest features or view the source code `on GitHub`_.

.. _me: arthur.coque@inrae.fr
.. _on Github: https://github.com/inrae/SISPPEO


License
-------

**SISPPEO** is available under the open source `Apache License`__.

__ http://www.apache.org/licenses/LICENSE-2.0.html
