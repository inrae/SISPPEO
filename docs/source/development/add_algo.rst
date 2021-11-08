****************************************
Write and add a new algorithm to SISPPEO
****************************************

Introduction
============

Dans SISPPEO, les algorithmes de télédétection se présentent sous la forme d'une classe. Cette dernière comporte deux méthodes à implémenter :

* ``__init__``\ , pour initialiser un algorithme pour un type de produit satellitaire donné (e.g., "S2_GRS") et optionnellement pour une calibration (i.e. un ensemble de paramètres) et une bande données ;
* ``__call__``\ , qui permet d'appeler directement l'instance de classe (à la manière d'une fonction). Cette méthode renvoie le tableau de résultats (ainsi que les paramètres/coefficients utilisés lors des calculs).

Chaque algorithme contient par ailleurs 3 attributs publics :

* ``name``\ , qui est le "label" (i.e. court nom en camel_case, ~id de l'algo utilisé pour le sélectionner lors de la création d'un produit L3) de l'algorithme ;
* ``requested_bands``\ , qui est la liste des bandes utilisées par l'algorithme.
* ``meta``\ , qui est un dictionnaire dans lequel sont stockées différentes métadonnées (nom de la calibration utilisée, coefficients, etc).

De plus, chaque algorithme implémenté se doit d'avoir une entrée dans l'un des fichiers YAML de configuration (\ *"resources/land_algo_config.yaml"*\ , *"resources/wc_algo_config.yaml"* ou le fichier *"resources/algo_config.yaml"* du user workspace).

Structure minimale
==================

Logique métier (python)
-----------------------

.. code-block:: python

   class Dummy:
       name = 'dummy'

       def __init__(self, product_type, **_ignored) -> None:
           try:
               self.requested_bands = algo_config[self.name][producttype_to_sat(product_type)]
           except KeyError as invalid_product:
               msg = f'{product_type} is not allowed with {self.name}'
               raise InputError(msg) from invalid_product
           self.meta = {}

       def __call__(self, band: xr.DataArray, **_ignored) -> xr.DataArray:
           # traitement spécifique à l'algo -> result
           return result

Configuration (yaml)
--------------------

.. code-block:: yaml

   dummy:
     long_name: Dummy variable from Dummy et al., 2021
     output: ymmub
     L8:
       - B5
     S2:
       - B8

Ici, l'on définit l'algorithme "dummy", qui peut être appliquer à des images Landsat 8 (L8) et Sentinel-2 (S2), desquelles seront resp. extraites les bandes B5 et B8. Le nom de la variable dans le dataset (/netCDF) en sortie sera "ymmub", et cette variable aura un attribut "long_name: Dummy variable from Dummy et al., 2021" qui sert à correctement référencer l'algorithme employé.

Exemples
========

1. Cas "trivial" (i.e. pas de bande ni de calibration à spécifier) : NDWI
-------------------------------------------------------------------------

.. code-block:: python

   class Ndwi:
       """Normalized Difference Water Index.

       Algorithm computing the NDWI from green and nir bands, using either surface
       reflectances (rh   o, unitless) or remote sensing reflectances (Rrs,
       in sr-1).
       This index was presented by McFeeters (1996).

       Attributes:
           name: The name of the algorithm used. This is the key used by
             L3AlgoBuilder and that you must provide in config or when using
             the CLI.
           requested_bands: A list of bands further used by the algorithm.
       """
       name = 'ndwi'

       def __init__(self, product_type, **_ignored) -> None:
           """Inits an 'Ndwi' instance for a given 'product_type'.

           Args:
               product_type: The type of the input satellite product (e.g.
                 S2_ESA_L2A or L8_USGS_L1GT)
               **_ignored: Unused kwargs send to trash.
           """
           try:
               self.requested_bands = algo_config[self.name][
                   producttype_to_sat(product_type)]
           except KeyError as invalid_product:
               msg = f'{product_type} is not allowed with {self.name}'
               raise InputError(msg) from invalid_product
           self.meta = {}

       def __call__(self,
                    green: xr.DataArray,
                    nir: xr.DataArray,
                    **_ignored) -> xr.DataArray:
           """Runs the algorithm on input arrays (green and nir).

           Args:
               green: An array (dimension 1 * N * M) of reflectances in the green
                 part of the spectrum (B3 @ 560 nm for S2 & @ 563 nm for L8).
               nir: An array (dimension 1 * N * M) of reflectances in the NIR part
                 of the spectrum (B8 @ 833 nm for S2, B5 @ 865 nm for L8).

           Returns:
               A tuple of:
                 - an array (dimension 1 * N * M) of NDVI values.
           """
           ndwi = (green - nir) / (green + nir)
           return ndwi

.. _aa ini:

1. Initialisation : *__init__*
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

L'initialisation de cet algorithme requiert un paramètre nommé ``product_type``\ , qui permet de renseigner le type de produit que l'algorithme va être amené à traiter. Cela permet d'aller automatiquement chercher dans le fichier de configuration (ici *"resources/wc_algo_config.yaml"*\ ) dudit algorithme les bandes nécessaires (i.e. à extraire).

Dans le cas où cet algorithme n'est pas fait pour ce produit satellitaire, un message d'erreur est renvoyé.

2. Méthode *__call__*
^^^^^^^^^^^^^^^^^^^^^

Cette méthode prend en entrée les tableaux (:code:`xarray.DataArray`) des bandes précédemment extraites (par le reader) et renvoie le tableau (:code:`xarray.DataArray`) de résultats (ici, du NDWI).

3. Configuration
^^^^^^^^^^^^^^^^

L'entrée dans *resources/wc_algo_config.yaml* est la suivante :

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

2. Cas où plusieurs calibrations et bandes utilisables possibles : SPMNechad
----------------------------------------------------------------------------

.. code-block:: python

   class SPMNechad:
       """Semi-analytical algorithm to retrieve SPM concentration (in mg/l) from reflectance.

       Semi-analytical algorithm to retrieve SPM concentrations (in mg/L) from
       surface reflectances (rho, unitless) or remote sensing reflectances (Rrs,
       in sr-1).
       This algorithm was presented in Nechad et al., 2010 and 2016.

       Attributes:
           name: The name of the algorithm used. This is the key used by
             L3AlgoBuilder and that you must provide in config or when using
             the CLI.
           requested_bands: A list of bands further used by the algorithm.
       """
       _default_band = 'B4'
       _default_calibration_file = wc_calib / 'spm_nechad.yaml'
       _default_calibration_name = 'Nechad_2016'
       name = 'spm-nechad'

       def __init__(self,
                    product_type: str,
                    requested_band: str = _default_band,
                    calibration: Optional[P] = None,
                    **_ignored) -> None:
           """Inits an 'SPMNechad' instance with specific settings.

           Args:
               product_type: The type of the input satellite product (e.g.
                 S2_ESA_L2A or L8_USGS_L1GT).
               requested_band: Optional; The band used by the algorithm (
                 default=_default_band).
               calibration: Optional; The calibration (set of parameters) used
                 by the algorithm (default=_default_calibration_name).
               **_ignored: Unused kwargs send to trash.
           """
           self.requested_bands = [requested_band]
           calibration_dict, calibration_name = load_calib(
               calibration,
               self._default_calibration_file,
               self._default_calibration_name
           )
           self._valid_limit = calibration_dict['validity_limit']
           try:
               params = calibration_dict[producttype_to_sat(product_type)][
                   requested_band]
           except KeyError as invalid_input:
               msg = (f'{product_type} or {requested_band} is not allowed with '
                      f'{self.name}/this calibration')
               raise InputError(msg) from invalid_input
           self.__dict__.update(params)
           self.meta = {'band': requested_band,
                        'calibration': calibration_name,
                        'validity_limit': self._valid_limit,
                        **params}

1. Initialisation : *__init__*
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Cf. :ref:`le cas simple <aa ini>`.

Ici, en plus de précédemment, il faut spécifier une bande à utiliser (parmi celles autorisées dans :ref:`le fichier de configuration de l'algorithme <aa config>`, ici : de "B4" à "B8A"). Si aucune bande n'est précisée par l'utilisateur, ``_default_band`` (ici, "B4") est utilisée.

En plus de cela, différentes calibrations sont disponibles. Elles peuvent être :

* fournies par l'utilisateur sous la forme d'un chemin d'accès à un fichier de configuration correctement formaté (pour cela, se référer à ceux déjà fournis avec SISPPEO) ;
* choisies parmis celles disponible "de base" et à retrouver dans le fichier de calibration de l'algorithme (ici *"resources/wc_algo_calibration/spm_nechad.yaml"*\ ). Pour spm-nechad par exemple, les calibrations disponibles sont :ref:`"Nechad_2010" <aa calib>` et "Nechad_2016".

2. Méthode *__call__*
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

       def __call__(self,
                    rho: xr.DataArray,
                    data_type: str,
                    **_ignored) -> xr.DataArray:
           """Runs the algorithm on the input array ('rho').

           Args:
               rho: An array (dimension 1 * N * M) of 'data_type'.
               data_type: Either 'rho' or 'rrs' (respectively surface reflectance
                   and remote sensing reflectance).
               **_ignored: Unused kwargs sent to trash.

           Returns:
               An array (dimension 1 * N * M) of SPM concentration (in mg/L).
           """

           if data_type == 'rrs':
               rho = np.pi * rho

           np.warnings.filterwarnings('ignore')
           # pylint: disable=no-member
           # Loaded in __init__ with "__dict__.update".
           spm = _nechad(rho, self.a, self.c)
           spm = spm.where((rho >= 0) & (spm >= 0) & (spm < self._valid_limit))
           return spm

.. _aa config:

3. Configuration
^^^^^^^^^^^^^^^^

.. code-block:: yaml

   spm-nechad:
     long_name: Suspended particulate matter (mg/l) from Nechad et al., 2010, 2016
     output: spm
     L8:
       - B2
       - B3
       - B4
       - B5
     S2:
       - B3
       - B4
       - B5
       - B6
       - B7
       - B8
       - B8A

.. _aa calib:

4. Calibration
^^^^^^^^^^^^^^

Ceci est un exemple de calibration (stockée dans *resources/wc_algo_calibration/spm-nechad.yaml*\ ) :

.. code-block:: yaml

   Nechad_2010:
     validity_limit: 100
     L8:
       B4:
         a: 346.32
         c: 0.19905
       B5:
         a: 2929.49
         c: 0.21135
     S2:
       B4:
         a: 342.1
         c: 0.19563
       B5:
         a: 444.36
         c: 0.18753
       B6:
         a: 1517.0
         c: 0.19736
       B7:
         a: 1510.12
         c: 0.20535
       B8:
         a: 1801.52
         c: 0.1913
       B8A:
         a: 2932.21
         c: 0.21151

3. Algorithmes mutli-sorties
----------------------------

Un algorithme peut permettre d'estimer plusieurs paramètres (=> plusieurs variables dans le dataset de sortie). Par exemple, QAA (Lee et al., 2002) et ses variantes permettent de calculer "a" et "bbp".

Pour cela, il suffit :

#. de renvoyer une liste de tableau (au lieu d'un unique tableau) avec la méthode ``__call__`` ;
#. de spécifier plusieurs "long_name" (afin de décrire les variables) et sorties (/"output") dans le fichier de configuration (cf. ci-après).

.. code-block:: yaml

   qaa:
     long_name:
       - Absorption coefficient (m-1) from Lee et al., 2009 (Quasi-Analytical Algorithm QAA_v5)
       - Backscattering coefficient (m-1) from Lee et al., 2009 (Quasi-Analytical Algorithm QAA_v5)
     output:
       - a
       - bbp
     L8:
       - B1
       - B2
       - B4
       - B3
     S2:
       - B1
       - B2
       - B4
       - B3

"Intégration" de l'algorithme
=============================

Il faut ensuite importer la classe (i.e. l'algorithme) nouvellement créée dans le fichier *__init__.py* du package auquel il appartient (e.g. :py:mod:`~sisppeo.wcproducts`). Ex :

.. code-block:: python

   from sisppeo.wcproducts.spm import SPMGet, SPMHan, SPMNechad, TURBIDogliotti

----

Remarque
========

Si vous avez une question ou si vous avez besoin d'informations complémentaires, i) référez-vous aux différents algorithmes fournis avec le package :py:mod:`sisppeo.wcproducts` puis si besoin ii) contactez `moi <mailto:arthur.coque@inrae.fr>`_\.
