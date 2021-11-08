<img title="SISPPEO banner" src="assets/SISPPEO_FondEtoile.png" width="100%">

<div align="center">

# SISPPEO: Satellite Imagery & Signal Processing Package for Earth Observation
</div>

<div align="center">
  <img title="logos" src="assets/logo_merged.png" width="834">
</div>

[![Anaconda-Server Badge](https://anaconda.org/conda-forge/sisppeo/badges/version.svg)](https://anaconda.org/conda-forge/sisppeo)
[![Anaconda-Server Badge](https://anaconda.org/conda-forge/sisppeo/badges/downloads.svg)](https://anaconda.org/conda-forge/sisppeo)
[![Anaconda-Server Badge](https://anaconda.org/conda-forge/sisppeo/badges/license.svg)](https://anaconda.org/conda-forge/sisppeo)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.4639630.svg)](https://doi.org/10.5281/zenodo.4639630)

## Content

1. [What is SISPPEO ?](#what-is-sisppeo)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Dependencies](#dependencies)

### What is SISPPEO ?

`SISPPEO` is an open source project and Python package (with a CLI) allowing one to extract synthetic information
useful for Earth observation (Water and Land) from satellite optical imagery (e.g, Sentinel-2/MSI, Sentinel-3/OLCI,
Landsat 8/OLI…).

- **Documentation:** https://inrae.github.io/SISPPEO
- **Source code:** https://github.com/inrae/SISPPEO

**Author:** Arthur Coqué (arthur.coque@inrae.fr)

**Contributors:** Guillaume Morin (guillaume.p.morin@inrae.fr), Nathalie Reynaud (nathalie.reynaud@inrae.fr), 
Thierry Tormos (thierry.tormos@ofb.gouv.fr), Valentine Aubard (valentine.aubard@inrae.fr)

### Requirements

You will need Python 3.8 to run `SISPPEO`. You can have multiple Python versions (2.x and 3.x) 
installed on the same system without any problems.

### Installation


SISPPEO can be downloaded and installed using conda-forge:

```shell
$ conda install sisppeo -c conda-forge
```

You can also install it from source. To do so, you will first have to clone the GitHub repository:

```shell
$ git clone https://github.com/inrae/SISPPEO.git
$ cd sisppeo
```

Then, you will need to create a virtual environment (optional, but strongly advised) and install SISPPEO.

- using conda (recommended):

```shell
$ conda env create -f conda/environment.yml
$ pip install .
```

- using virtualenv and pip:

```shell
$ python3 -m venv venv
$ source venv/bin/activate

$ pip install -U .
```

Finally, you can use SISPPEO as a Python package (it's kind of like a toolbox) or through its CLI:

```shell
$ sippeo <your_cmd>
```
