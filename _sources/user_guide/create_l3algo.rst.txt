***********************************
Create a L3 product (L3AlgoProduct)
***********************************

.. note::
   This tutorial will soon be available in English.

Il existe différents moyens de créer un produit L3 (indice coloré, élément biogéochimique, etc) avec SISPPEO.

Via la CLI
==========

.. note::
   La commande ``create-l3`` permet de créer des produits masqués en générant les masques à la volée (contrairement à ``create-l3algo``, cf. après). Ce tutoriel sera bientôt mis à jour pour en parler.

En utilisant la CLI, il est possible de créer un produit L3 (masqué ou non) à partir de produits L1 ou L2.

Pour cela, il suffit de faire :

.. code-block:: shell

   sisppeo create-l3algo --input_product path1 --product_type S2_GRS [--glint] --algo spm-nechad [--algo_band spm-nechad B5] [--algo_calib spm-nechad Nechad_2010] --out_product path2

Ici, un objet L3AlgoProduct contenant une variable "spm-nechad" sera calculé à partir de l'image S2_GRS "path1" et enregistré sous le nom "path2".

Les arguments entre crochets ("[...]") sont optionnels. D'autres arguments, ainsi que des raccourcis sont disponibles. Pour plus d'information, se référer à la suite de ce tutoriel, au reste de la documentation ou bien taper :command:`sisppeo --help` / :command:`sisppeo create-l3algo --help`.

.. _argu readers 1:

Arguments spécifiques à certains readers
----------------------------------------

GRS
^^^

Le flag ``--glint_corrected``\ /\ ``--glint`` est utilisé pour choisir si le reader des produits GRS va extraire les Rrs corrigées du glint ("Rrs", par défaut) ou non corrigées de ce phénomène ("Rrs_g").

S2_THEIA
^^^^^^^^

theia_bands
"""""""""""

L'argument ``--theia_bands`` permet de choisir si le reader des produits THEIA va extraire les bandes "SRE" (pour Surface REflectance) ou "FRE" (pour Flat REflectance ; corrigées des `effets des pentes <https://labo.obs-mip.fr/multitemp/la-correction-des-variations-declairement-dues-au-relief/>`_\ ).

theia_mask
""""""""""

L'argument ``--theia_mask`` permet d'utiliser les masques THEIA (CLM, MG2 et SAT) et le cas échéant de préciser quels bits prendre en compte (cf. `cette description <https://labo.obs-mip.fr/multitemp/sentinel-2/theias-sentinel-2-l2a-product-format/>`_\ ).

Par exemple :

.. code-block:: shell

   --theia_mask "CLM 012467"

ou encore :

.. code-block:: shell

   --theia_mask "MG2"

Si aucun bit n'est précisé, ils sont par défaut tous utilisés (masque le plus restrictif).

C2RCC
^^^^^

L'argument ``--sensing_date`` permet d'indiquer la date d'acquisition du produit L1C dont est issu le produit C2RCC. C'est un argument temporaire, qui est là pour palier l'absence de métadonnées des produits C2RCC générés avec Snap. Le format attendu est "YYYY-MM-DD".

.. _argu algos 1:

Arguments relatifs aux algorithmes utilisés
-------------------------------------------

Pour spécifier un algorithme, on utilise l'argument ``--algo`` suivi du nom dudit algorithme (e.g. ``--algo ndwi``\ ).

Certains algorithmes peuvent utiliser plusieurs bandes au choix et peuvent avoir plusieurs jeux de calibration. Par exemple, "spm-nechad" peut utiliser les bandes B2, B3, B4 et B5 (pour L8 ; pour S2, se référer au fichier "resources/wc_algo_config.yaml") et a 2 jeux de calibration disponibles : "Nechad_2010" et "Nechad_2016". Les valeurs par défaut sont respectivement "B4" et "Nechad_2016". Cependant, il est possible d'en choisir d'autres en utilisant les arguments ``--algo_band`` et ``--algo_calib``

Par exemple :

.. code-block:: shell

   --algo spm-nechad --algo_band spm-nechad B5 --algo_calib spm-nechad Nechad_2010

*Rq: il est nécessaire de préciser le nom de l'algorithme concerné pour ces deux arguments, afin de pouvoir rendre possible l'utilisation simultanée de plusieurs algorithmes (cf.* :ref:`ci-après <mutualisation1>`\ *).*

Par ailleurs, il est possible d'utiliser son propre jeu de calibration en utilisant l'argument ``--algo_custom_calib`` suivi du nom de l'algorithme employé et du chemin d'accès du fichier YAML de calibration (pour la structure à respecter, se référer aux calibrations fournies avec SISPPEO et situées dans le dossier "sisppeo/resources/wc_algocalibration").

Génération de produits masqués
------------------------------

Il est possible de générer des produits L3 masqués. Pour cela, il faut utiliser les arguments ``--mask_path`` et ``--mask_type``\ , resp. le path du masque et s'il est utilisé pour inclure ou exclure les zones masquées. L'utilisation de plusieurs masques de manière combinée est possible.

Exemple (pour conserver les zones d'eau sans nuages):

.. code-block:: shell

   --mask_path path/to/watermask --mask_type IN --mask_path path/to/cloudmask --mask_type OUT

Les masques utilisées doivent être au format netCDF (avec une variable binaire ; dans l'idéal générés via SISPPEO pour des raisons évidentes de compatibilités). Plusieurs masques sont disponibles :

* masque eau : `WaterDetect <https://github.com/cordmaur/WaterDetect>`_ ;

* masque nuage : `s2cloudless <https://github.com/sentinel-hub/sentinel2-cloud-detector>`_.

.. _ROI 1:

Traitement sur une zone d'intérêt
---------------------------------

Il est possible d'extraire et de traiter une zone limitée en lieu et place de toute l'image (pour des questions de performances/temps, d'intérêt, etc). Pour cela, il suffit de fournir au choix :

un shapefile (.shp)
^^^^^^^^^^^^^^^^^^^

.. code-block:: shell

   --shp path/to/shapefile.shp

un wkt (pour well-known text)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Directement sous forme de chaîne de caractères...

.. code-block:: shell

   --wkt 'POLYGON ((lon1 lat1, lon2 lat2, ..., lonN latN))'

... ou bien de fichier texte :

.. code-block:: shell

   --wkt_file path/to/wkt/file.txt

Par défaut, il est considéré que le SRID du WKT fourni est "4326" (code EPSG pour le système géodésique WGS84 associé à des coordonnées géographiques) mais il est possible d'en spécifier un autre en utilisant l'argument ``--srid`` (e.g., ``--srid 32622`` pour le système de coordonnées projetées WGS84 / UTM zone 22N).

.. _resampling 1:

Rééchantillonnage
-----------------

Dans le cas où des bandes de résolutions différentes sont extraites (readers "S2_ESA" et "S2_THEIA") et utilisées au sein du même algorithme, il est possible de spécifier la résolution voulue en sortie en utilisant l'argument ``--res`` (e.g., ``--res 20``\ ). Seules les valeurs appartenant à l'union des résolutions des bandes utilisées sont autorisées. Par défaut, la résolution la plus grossière est utilisée.

.. _mutualisation1:

Optimisation : mutualisation de l'extraction des bandes
-------------------------------------------------------

Si plusieurs traitements sont envisagés pour la même zone/image, il est possible de mutualiser l'étape d'extraction en spécifiant plusieurs algorithmes.

Par exemple :

.. code-block:: shell

   sisppeo create-l3algo --input_product path1 --product_type S2_GRS --algo ndwi --algo spm-nechad --out_product path_out_ndwi --out_product path_out_spm

L'argument "algo" peut être appelé plusieurs fois (auquel cas, ``--out_product`` devra lui aussi-être appelé plusieurs fois [à moins d'utiliser ``--output_dir``\ , cf. :ref:`ci-après <sortie1>`\ ] et dans le même ordre).

.. _sortie1:

Fichiers de sortie
------------------

Il est possible de fournir au choix un nom de fichier (un par algo/produit) ou le chemin d'un dossier (auquel cas les noms des produits L3 sont générés automatiquement [en fonction des différents paramètres/arguments] dans ce dossier). Les arguments à utiliser sont respectivement ``--out_product`` et ``--output_dir``.

Raccourcis : fichiers d'inputs
------------------------------

.. _algoslist:

"algos_list"
^^^^^^^^^^^^

Dans le cas où l'on souhaite appliquer de nombreux algorithmes, avec ou sans calibrations particulières, il peut être intéressant et plus rapide (génération automatique par ex) d'utiliser un fichier texte regroupant les différentes entrées et qui sera appelé par l'argument ``--algos_list`` (e.g., ``--algos_list path/to/text/file.txt``\ ). Il devra contenir un en-tête (cf. exemples ci-après) ainsi que les valeurs de ces différents arguments pour chaque produit attendu (une ligne par produit), en laissant vide les arguments non pertinents.

Par exemple :\ ::

   algo band calib custom_calib design
   ndwi
   spm-nechad B4  path/to/custom/calib.yaml
   chla-gons  Gernez_2017
   chla-gitelson    2_bands

... ou encore :\ ::

   algo calib
   ndwi
   chla-gons Gernez_2017

Toute les colonnes (excepté "algo") sont optionnelles (cf. les exemples précédents).

Si utilisé, l'argument ``--algos_list`` remplace les arguments ``--algo``\ , ``--algo_band``\ , ``--algo_calib`` et ``--algo_custom_calib``.

.. _maskslist:

"masks_list"
^^^^^^^^^^^^

De la même manière, il est possible d'utiliser l'argument ``--masks_list`` (suivi d'un path) pour remplacer les arguments ``--mask_path`` et ``--mask_type``.

Exemple :\ ::

   path type
   path/to/watermask IN
   path/to/cloudmask OUT

Via le module
=============

SISPPEO peut aussi être importé au sein d'un script Python afin de créer des produits L3 à partir de produits L1 ou L2.

Pour cela, il suffit de procéder de la manière suivante :

.. code-block:: python

   import sisppeo

   params = {
   'input_product': path1,
   'product_type': 'S2_GRS',
   'glint_corrected': True,
   'algo': 'spm-nechad'
   }  
   l3algo_product = sisppeo.generate('l3 algo', params)[0]

Ici, un objet :py:class:`~sisppeo.products.l3.L3AlgoProduct` contenant une variable "spm-nechad" sera calculé à partir de l'image S2_GRS "path1". Pour l'enregistrer à l'emplacement "path2", il suffit d'ajouter une clé ``out_product`` ou ``output_dir`` au dictionnaire "params" et de modifier la dernière ligne :

.. code-block:: python

   params['out_product'] = path2
   l3algo_product = sisppeo.generate('l3 algo', params, True)[0] # ou "save=True"

*Rq: il est aussi possible de sauvegarder un produit L3 déjà généré en faisant* :code:`l3algo_product.save(path2)`. *Pour bénéficier de la génération automatique du nom permise par la méthode précédente (avec la clé* ``output_dir`` *en lieu et place de* ``out_product``\ *), il faut écrire :*

.. code-block:: python

   from sisppeo.utils.naming import (extract_info_from_input_product,
                                     generate_l3_filename)

   code_image, _, source, roi = extract_info_from_input_product(
       path1, 'S2_GRS',
       # optionnels : params.get('code_site', None), params.get('geom', None)
   )
   filename = generate_l3_filename(l3algo_product, code_image, source, roi)
   l3algo_product.save(dirname / filename)    # type(dirname) == pathlib.Path

De nombreuses autres clés sont disponibles pour le dictionnaire "params", cf. la suite de ce tutoriel.

.. _argu readers 2:

Arguments spécifiques à certains readers
----------------------------------------

GRS
^^^

Le booléen ``glint_corrected`` est utilisé pour choisir si le reader GRS va extraire les Rrs corrigées du glint ("Rrs", si ``glint_corrected=True`` [par défaut]) ou non corrigées de ce phénomène ("Rrs_g", si ``glint_corrected=False``\ ).

S2_THEIA
^^^^^^^^

theia_bands
"""""""""""

La clé ``theia_bands`` permet de choisir si le reader des produits THEIA va extraire les bandes "SRE" (pour Surface REflectance) ou "FRE" (pour Flat REflectance ; corrigées des `effets des pentes <https://labo.obs-mip.fr/multitemp/la-correction-des-variations-declairement-dues-au-relief/>`_ [par défaut]).

theia_masks
"""""""""""

La clé ``theia_mask`` permet d'utiliser les masques THEIA (CLM, MG2 et SAT) et le cas échéant de préciser quel bits prendre en compte (cf. `cette description <https://labo.obs-mip.fr/multitemp/sentinel-2/theias-sentinel-2-l2a-product-format/>`_\ ).

Par exemple :

.. code-block:: python

   params.update({'theia_masks': {
       'CLM': [0, 1, 3],
       'MG2': None
   }})

Si ``lst_theia_mask_bits=None``\ , tous les bits sont utilisés par défaut pour l'ensemble des masques donnés dans ``lst_theia_mask``. Dans le cas où, comme dans l'exemple ci-dessus, une entrée de la liste ``lst_theia_mask_bits`` vaut "None", alors le comportement par défaut (utilisation de tous les bits) ne sera appliqué que pour le masque correspondant.

C2RCC
^^^^^

La clé ``sensing_date`` permet d'indiquer la date d'acquisition du produit L1C dont est issu le produit C2RCC. C'est un argument temporaire, qui est là pour palier l'absence de métadonnées des produits C2RCC générés avec Snap. La date attendue doit être une chaîne de caractère au format "YYYY-MM-DD" ou bien un objet ``datetime.datetime``.

.. _argu algos 2:

Arguments relatifs aux algorithmes utilisés
-------------------------------------------

Pour spécifier un algorithme, on utilise la clé ``algo`` et on lui associe le nom dudit algorithme (e.g., ``algo=ndwi``\ ).

Certains algorithmes peuvent utiliser plusieurs bandes au choix et peuvent avoir plusieurs jeux de calibration. Par exemple, "spm-nechad" peut utiliser les bandes B2, B3, B4 et B5 (pour L8 ; pour S2, se référer au fichier "resources/wc_algo_config.yaml") et a 2 jeux de calibration disponibles : "Nechad_2010" et "Nechad_2016". Les valeurs par défaut sont respectivement "B4" et "Nechad_2016". Cependant, il est possible d'en choisir d'autres en utilisant les clés ``algo_band`` et ``algo_calib``.

Par exemple :

.. code-block:: python

   params.update({
       'algo': 'spm-nechad',
       'algo_band': 'B5',
       'algo_calib': 'Nechad_2010'
   })

*Rq: il est aussi possible d'utiliser les clés* ``lst_algo``\ , ``lst_algo_band`` *et* ``lst_calib`` *et de fournir des listes d'un seul élément (e.g.,* ``lst_algo=['spm-nechad']``\ *). Cela prend tous son sens lorsque l'on veut mutualiser la phase d'extraction des bandes et appliqués plusieurs algorithmes simultanément (cf.* :ref:`ci-après <mutualisation2>`\ *).*

Par ailleurs, il est possible d'utiliser son propre jeu de calibration en utilisant la même clé ``algo_calib`` mais en spécifiant le chemin vers son propre fichier YAML de calibration au lieu du nom de l'une des calibrations délivrées avec SISPPEO (situées dans le dossier "sisppeo/resources/wc_algocalibration").

Génération de produits masqués
------------------------------

Il est possible de générer des produits L3 masqués. Pour cela, il faut utiliser les clés ``l3mask``\ /\ ``l3mask_path`` et ``l3mask_type``\ , resp. un objet :py:class:`~sisppeo.products.l3.L3MaskProduct` (i.e., un masque créé avec SISPPEO et chargé en mémoire) / le path du masque (i.e., un masque créé avec SISPPEO [ou binaire et respectant les mêmes conventions] et sauvegardé sur le disque) et s'il est utilisé pour inclure ou exclure les zones masquées.

Par exemple :

.. code-block:: python

   params.update({
       'l3mask': l3mask_product, # ou 'l3mask_path: path/to/l3mask/product.nc
       'l3mask_type': 'IN' # or 'OUT'
   })

Il n'est pas possible d'utiliser à la fois des masques chargés en mémoire (via ``l3mask``\ ) et des masques sauvegardés sur le disque (via ``l3mask_type``\ ). Cependant, il est possible de masquer des produits a posteriori grâce à la fonction :py:func:`~sisppeo.products.l3.mask_product`.

Les masques chargés depuis le disque doivent être au format netCDF (et dans l'idéal générés via SISPPEO pour des raisons évidentes de compatibilités). Plusieurs masques sont disponibles :

* masque eau : `WaterDetect <https://github.com/cordmaur/WaterDetect>`_ ;

* masque nuage : `s2cloudless <https://github.com/sentinel-hub/sentinel2-cloud-detector>`_.

L'utilisation de plusieurs masques de manière combinée est possible, auquel cas on utilisera les clés ``lst_l3mask``\ /\ ``lst_l3mask_path`` et ``lst_l3mask_type`` (de la même manière que pour les algorithmes, il est possible d'utiliser ces clés et de fournir des listes d'un seul élément).

Par exemple, afin de conserver les zones d'eau sans nuages :

.. code-block:: python

   params.update({
       'lst_l3mask': [watermask, cloudmask], # ou 'lst_l3mask_path: [path/to/watermask, path/to/cloudmask]
       'lst_l3mask_type': ['IN', 'OUT']
   })

.. _ROI 2:

Traitement sur une zone d'intérêt
---------------------------------

Il est possible d'extraire et de traiter une zone limitée en lieu et place de toute l'image (pour des questions de performances/temps, d'intérêt, etc). Pour cela, il suffit de fournir un dictionnaire (optionnel) ``geom`` contenant les clés (optionnelles) suivantes :


* ``geometry`` doit être associée à un objet géométrique déjà chargé en mémoire (cf. `Shapely <https://shapely.readthedocs.io/en/stable/manual.html>`_\ ) ;

* ``shp`` doit être associée à un chemin d'accès à n shapefile (.shp) ;

* ``wkt`` doit être associée à un chemin d'accès à un fichier texte contenant une chaîne de caractère au format WKT (Well-Known Text).

* ``srid`` doit être associée à un code EPSG (correspondant au système de coordonnées dans lequel est fournie la zone d'intérêt] ; à utiliser avec ``geometry`` ou ``wkt`` si différent de "4326" (code EPSG pour le système géodésique WGS84 associé à des coordonnées géographiques [défaut]).

Par exemple :

.. code-block:: python

   params['geom'] = {
       'wkt': path/to/wkt/file.txt,
       'srid': 32622
   }

.. _resampling 2:

Rééchantillonnage
-----------------

Dans le cas où des bandes de résolutions différentes sont extraites (readers "S2_ESA" et "S2_THEIA") et utilisées au sein du même algorithme, il est possible de spécifier la résolution voulue en sortie en utilisant la clé ``out_resolution``. Seules les valeurs appartenant à l'union des résolutions des bandes utilisées sont autorisées. Par défaut, la résolution la plus grossière est utilisée.

Par exemple:

.. code-block:: python

   params['out_resolution'] = 20

.. _mutualisation2:

Optimisation : mutualisation de l'extraction des bandes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Si plusieurs traitements sont envisagé pour la même zone/image, il est possible de mutualiser l'étape d'extraction en spécifiant plusieurs algorithmes.

Par exemple :

.. code-block:: python

   params.update({
       'lst_algo': ['ndwi', 'spm-nechad'],
       'lst_algo_band': [None, 'B5'], # optionnel
       'lst_calib': [None, 'Nechad_2010'] # optionnel
   })

*Rq: il est possible de charger en mémoire un produit L3 depuis un fichier netCDF préalablement généré et enregistré sur le disque en utilisant la méthode de classe* :py:meth:`~sisppeo.products.l3.L3AlgoProduct.from_file`.

----

Remarque
========

Si vous avez une question ou si vous avez besoin d'informations complémentaires, i) consultez le reste de la documentation, ii) référez-vous au code de SISPPEO puis si besoin iii) contactez `moi <mailto:arthur.coque@inrae.fr>`_\.
