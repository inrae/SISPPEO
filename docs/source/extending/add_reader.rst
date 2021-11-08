*************************************
Write and add a new reader to SISPPEO
*************************************

Introduction
============

Un reader est une classe permettant de lire et d'extraire des informations (radiométriques + métadonnées) d'un produit satellitaire donné.

Pour cela, un reader doit tout d'abord hériter de la classe abstraite :py:class:`~sisppeo.readers.reader.Reader``. Cette dernière précise l'interface minimale à implémenter (quels arguments sont nécessaires lors d'une instanciation, quelles fonctions doivent obligatoirement être implémentées, etc).

Exemple de notre nouveau reader (pour les produits Sentinel-2 fournis par l'ESA) :

.. code-block:: python

   class S2ESAReader(Reader):
       """A reader dedicated to extract data from both S2_ESA_L1C and S2_ESA_L2A products.

       Attributes:
           dataset: A dataset containing extracted data.
       """

1. Initialisation : *__init__*
==============================

Par défaut, les arguments nécessaire dans l'\ ``__init__`` sont les suivants :


* ``input_product`` : le chemin d'accès au produit satellitaire ;
* ``requested_bands`` : la liste des bandes à extraire (e.g., ``['B3', 'B4', 'B5']``\ ).

Un argument optionnel peut aussi être demandé : :ref:`geom`. Il sera utilisé si l'utilisateur s'intéresse seulement à une zone restreinte (à extraire) et non pas à l'image entière.

Si notre reader ne nécessite pas de paramètres supplémentaires, l'on peut passer à l'implémentation de la méthode :py:meth:`~sisppeo.readers.reader.Reader.extract_bands` (cf. :ref:`extract bands`). Sinon, il faut redéfinir la fonction ``__init__``.

Ici, notre reader nécessite 1 argument supplémentaire : ``out_resolution``. Ce dernier sera utilisé pour forcer la résolution de sortie (parmi les résolutions des différentes bandes extraites).

.. code-block:: python

   def __init__(self,
               input_product: Path,
               requested_bands: List[str],
               geom: Optional['dict'] = None,
               out_resolution: Optional[int] = None,
               **_ignored) -> None:
       """See base class.

       Args:
           out_resolution: The wanted resolution of the output product. Used
               when performing resampling operations.
       """
       super().__init__(input_product, requested_bands, geom)  # Appel de l'__init__ de la classe parente "Reader"
       if out_resolution not in (None, 10, 20, 60):    # Filtrage des valeurs autorisées pour le nouveau paramètre "out_resolution"
           raise InputError('"out_resolution" must be in (10, 20, 60)')
       self._inputs['out_resolution'] = out_resolution     # Stockage de la valeur donnée par l'utilisateur

.. _extract bands:

2. Méthode *extract_bands*
==========================

.. code-block:: python

   @abstractmethod
   def extract_bands(self) -> None:
       """Opens the input product and extracts bands and metadata."""

Cette méthode ouvre un produit satellitaire et extrait les bandes demandées (paramètre ``requested_bands``\ ) ainsi que diverses metadonnées (utilisées par exemple pour convertir les comptes numériques en réflectances, ou bien tout simplement pour renseigner le produit L3 final).

Habituellement, cette méthode peut être structurée de la manière suivante :

#. charger les données (i.e. le dataset) ;
#. extraire/lire les métadonnées ;
#. filtrer les bandes à extraire ;
#. extraire les données (i.e. boucle sur les bandes à extraire, calcul du ROI si besoin...) ;
#. stocker les données et métadonnées.

En fonction du produits, cette structure est amenée à évoluer légèrement. Par ex :


#. :py:class:`~sisppeo.readers.GRS.GRSReader` n'a pas besoin de l'étape 3 (contrairement à un produit où l'on devrait aller lire le chemin de chaque bande à extraire dans les métadonnées) ;
#. un reader pour les produits Landsat 8 fournis par l'USGS n'aurait pas d'étape 1 (pas de dataset à charger, uniquement un fichier de métadonnées à lire dans lequel on va récuper les chemins des bandes qui nous intéressent dans l'étape 3).

Il y a priori 3 types de cas :

#. produit sous la forme d'un dataset (par ex un fichier .netCDF, comme pour GRS), à charger directement en utilisant la bibliothèque ``xarray``.
#. produit dans un format bénéficiant d'un reader ``GDAL`` (par exemple les produits Sentinel-2 fournis par l'ESA en .SAFE) : i) chargement du produit satellitaire en utilisant la bibliothèque ``rasterio`` (interface Python pour l'API C GDAL) puis ii) chargement des différentes bandes d'intérêt, toujours avec la même blibliothèque (fonction *open* et *read*\ ).
#. autres (par exemple les produit Landsat 8 fournis par l'USGS) : i) chargement et lecture des métadonnées puis ii) lecture des différentes bandes en utilisant la bibliothèque ``rasterio``.

3. Méthode *extract_ds*
=======================

.. code-block:: python

   @abstractmethod
   def create_ds(self) -> None:
       """Creates a xr.DataSet out of Reader params and extracted information."""

Cette méthode crée et stocke un objet :code:`xarray.Dataset` à partir des données et métadonnées précédemment extraites.

Cette méthode peut être structurée de la manière suivante :

#. :ref:`création du dataset <31>` ;
#. :ref:`renseigner les variables de coordonnées <32>` ;
#. :ref:`correctement paramétrer la variable "crs" <33>` ;
#. :ref:`renseigner les métadonnées <34>` ;
#. :ref:`préciser le type de données radiométriques <35>`.

.. _31:

3.1 Création du dataset
-----------------------

.. code-block:: python

   ds = xr.Dataset(
       {key: (['time', 'y', 'x'], val) for key, val
           in self._intermediate_data['data'].items()},
       coords={
           'x': ('x', self._intermediate_data['x']),
           'y': ('y', self._intermediate_data['y']),
           'time': [datetime.fromisoformat(self._intermediate_data[
               'metadata']['tags']['PRODUCT_START_TIME'][:-1])]
       }
   )

Le 1er dictionnaire ``{key: ... ['data'].itesms()}`` contient les différentes bandes extraites sous forme de *numpy.ndarray* 3D (image 2D + axe temporel ; shape=(1, M, N)).

Les coordonnées sont :


* un :code:`numpy.ndarray` (N,) **x** de coordonnées projetées sur une grille UTM ;
* un :code:`numpy.ndarray` (M,) **y** de coordonnées projetées sur une grille UTM ;
* une liste de longueur 1 **time** contenant la date d'acquisition du produit satellitaire sous la forme d'une objet datetime (du module datetime contenu dans la bibliothèque standard).

.. _32:

3.2 Renseigner les variables de coordonnées
-------------------------------------------

Pendant cette étape, l'on renseigne les axes, *long_name*\ , *standard_name* (si existe, cf. `netCDF CF-1.8 <https://cfconventions.org/Data/cf-conventions/cf-conventions-1.8/cf-conventions.html>`_\ ) ainsi que l'unité des ces 3 variables.

.. code-block:: python

   crs = self._intermediate_data['crs']
   # Set up coordinate variables
   ds.x.attrs['axis'] = 'X'
   ds.x.attrs['long_name'] = f'x-coordinate ({crs.name})'
   ds.x.attrs['standard_name'] = "projection_x_coordinate"
   ds.x.attrs['units'] = 'm'
   ds.y.attrs['axis'] = 'Y'
   ds.y.attrs['long_name'] = f'y-coordinate ({crs.name})'
   ds.y.attrs['standard_name'] = "projection_y_coordinate"
   ds.y.attrs['units'] = 'm'
   ds.time.attrs['axis'] = 'T'
   ds.time.attrs['long_name'] = 'time'

.. _33:

3.3 Paramétrisation de la variable "crs"
----------------------------------------

Cette variable sert à correctement géo-référencer le produit final (par exemple lors de l'utilisation dudit produit dans QGIS).

.. code-block:: python

   # Set up the 'grid mapping variable'
   ds['crs'] = xr.DataArray(name='crs', attrs=crs.to_cf())

.. _34:

3.4 conserver les métadonnées du produit satellitaire.
------------------------------------------------------

Il faut les enregistrer dans une nouvelle variable "product_metadata".

.. code-block:: python

   # Store metadata
   ds['product_metadata'] = xr.DataArray()
   for key, val in self._intermediate_data['metadata']['tags'].items():
       ds.product_metadata.attrs[key] = val

.. _35:

3.5 Préciser le type de données radiométriques.
-----------------------------------------------

L'on précise ici si ce sont des réflectances de télédétection (Rrs) ou bien des réflectances BOA ('rho') au sein du métadonnées temporaire (elle sera supprimée lors de la création du produit final et n'est utilisée que par les algos en ayant besoin).

.. code-block:: python

   ds.attrs['data_type'] = 'rrs'   # ou 'rho'

"Intégration" du reader
=======================

Il faut ensuite importer la classe (i.e. le reader) nouvellement créée dans le fichier *__init__.py* du module *readers*. Ex :

.. code-block:: python

   from .GRS import GRSReader

----

Remarque
========

Si vous avez une question ou si vous avez besoin d'informations complémentaires, i) référez-vous aux différents readers contenus dans le package :py:mod:`sisppeo.readers` puis si besoin ii) contactez `moi <mailto:arthur.coque@inrae.fr>`_\.

----

Annexe
======

.. _geom:

geom
----

Le paramètre *geom* peut être :

* "None", si l'utilisateur veut traiter l'image dans son entier ;
* un dictionnaire, comprenant un code EPSG (associé à la clé "srid" ; optionnel) et au choix :

  * une géométrie shapely (a priori un polygone) ;
  * un chemin d'accès vers i) un fichier .txt contenant une représentation géographique en wkt (le chemin est associé à la clé "wkt") ou ii) vers un .shp (le chemin est associé à la clé "shp").

Exemple (les champs ayant pour valeur "None" peuvent ne pas être inclus) :

.. code-block:: python

   geom = {
       'geom': None,
       'wkt': 'data/wkt.txt',
       'shp': None,
       'srid': 4326
   }

Gestion des fichiers compressés
-------------------------------

Tous les readers actuellement implémentés dans SISPPEO peuvent lire et extraire des informations depuis des archives (.tar.gz, .tgz ou .zip). Uniquement les bandes et les métadonnées nécessaires sont extraites (en mémoire). Se référer au code pour plus de détails.
