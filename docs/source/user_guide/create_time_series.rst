*********************************************
Create and analize a time series (TimeSeries)
*********************************************

.. note::
   This tutorial will soon be available in English.

Création
========

Il existe différents moyens de créer une série temporelle avec SISPPEO.

Via la CLI
----------

En utilisant la CLI, il est possible de créer une série temporelle (masquée ou non) à partir de produits L1 ou L2.

Pour cela, il suffit de faire :

.. code-block:: shell

   sisppeo create-timeseries --input_product path1 --input_product path2 --product_type S2_GRS [--glint] --algo spm-nechad [--algo_band spm-nechad B5] [--algo_calib spm-nechad Nechad_2010] [--num_cpus 2] --out_product path3

Ici, un objet TimeSeries contenant une variable "spm-nechad" sera calculé à partir des images S2_GRS "path1" et "path2" et enregistré sous le nom "path3".

Les arguments entre crochets ("[...]") sont optionnels. D'autres arguments, ainsi que des raccourcis (par exemple ``-i`` pour ``--input_product`` ou ``-a`` pour ``--algo``\ ) sont disponibles. Pour plus d'information, faire :command:`sisppeo --help` / :command:`sisppeo create-timeseries --help`.

Arguments spécifiques à certains reader
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

cf. :ref:`le tuto relatif à la création de produits L3 <argu readers 1>`.

Arguments relatifs aux algorithmes utilisés
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

cf. :ref:`le tuto relatif à la création de produits L3 <argu algos 1>`.

Génération de produits masqués
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Il est possible de générer des séries temporelles masquées. Pour cela, il faut utiliser les arguments ``--tsmask_path`` et ``--tsmask_type``\ , de la même manière que l'on utilise ``--mask_path`` et ``--mask_type`` pour des produits L3 (à l'exception que le masque ici utilisé est un objet TimeSeries et non L3MaskProduct).

Il est aussi possible d'utiliser, :ref:`comme lors de la génération de produits L3 <maskslist>`, l'argument `--masks_list``\ , à la seul différene qu'ici il faudra l'appeler une fois par "input_product".

Traitement sur une zone d'intérêt
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

cf. :ref:`le tuto relatif à la création de produits L3 <ROI 1>`.

Rééchantillonnage
^^^^^^^^^^^^^^^^^

cf. :ref:`le tuto relatif à la création de produits L3 <resampling 1>`.

Optimisation : mutualisation de l'extraction des bandes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Si plusieurs traitements sont envisagés pour la même série temporelle d'images, il est possible de mutualiser l'étape d'extraction en spécifiant plusieurs algorithmes.

Par exemple :

.. code-block:: shell

   sisppeo create-timeseries --input_product path1 --input_product path2 --product_type S2_GRS --algo ndwi --algo spm-nechad --out_product path_out_ndwi --out_product path_out_spm

L'argument "algo" peut être appelé plusieurs fois (auquel cas, ``--out_product`` devra lui aussi-être appelé plusieurs fois [à moins d'utiliser ``--output_dir``\ , cf. `ci-après <#fichiers-de-sortie>`_\ ] et dans le même ordre).

Fichiers de sortie
^^^^^^^^^^^^^^^^^^

cf. :ref:`le tuto relatif à la création de produits L3 <sortie1>`.

Raccourcis : fichiers d'inputs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

"products_list"
"""""""""""""""

Dans le cas où l'on souhaite compiler de nombreux produits (i.e. beaucoup de dates) au sein de notre série temporelle, il peut être intéressant et plus rapide (génération automatique par ex) d'utiliser un fichier texte regroupant les différentes entrées et qui sera appelé par l'argument ``--products_list`` (e.g., ``--products_list path/to/text/file.txt``\ ). Il devra contenir un en-tête (cf. exemple ci-après) ainsi que les valeurs de ces différents arguments pour chaque produit attendu (une ligne par produit), en laissant vide les arguments non pertinents.

Par exemple :::

   input_product masks_list
   path/to/input_product1 path/to/masks_listA
   path/to/input_product2
   path/to/input_product3 path/to/masks_listB

La colonne "input_product" est obligatoire ; "masks_list" est optionnelle.

Si utilisé, l'argument ``--products_list`` remplace les arguments ``--input_product`` (et potentiellement ``--masks_list``\ )

"algos_list"
""""""""""""

cf. :ref:`le tuto relatif à la création de produits L3 <algoslist>`.

Via le module
-------------

SISPPEO peut aussi être importé au sein d'un script Python afin de créer des séries temporelles à partir de produits L1-2, ou bien compiler des produits L3 déjà existants.

Depuis des produits L1 ou L2
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Il suffit de procéder de la manière suivante :

.. code-block:: python

   import sisppeo

   params = {
       'input_products': [path1, path2],
       'product_type': 'S2_GRS',
       'glint_corrected': True,
       'algo': 'spm-nechad',
   }
   timeseries = sisppeo.generate('time series', params)[0]

Ici, un objet TimeSeries contenant une variable "spm-nechad" sera calculé à partir des images S2_GRS  "path1" et "path2". Pour l'enregistré à l'emplacement "path3", il suffit d'ajouter une clé ``out_product`` ou ``output_dir`` au dictionnaire "params" et de modifier la dernière ligne :

.. code-block:: python

   params['out_product'] = path3
   timeseries = sisppeo.generate('time series', params, True)[0] # ou "save=True"

*Rq: il est aussi possible de sauvegarder une série temporelle déjà générée en faisant* :code:`timeseries.save(path3)`. *Pour bénéficier de la génération automatique du nom permise par la méthode précédente (avec la clé* ``output_dir`` *en lieu et place de* ``out_product``\ *), il faut écrire :*

.. code-block:: python

   from sisppeo.utils.naming import (extract_info_from_input_product,
                                                      generate_ts_filename)

   _, sat, source, roi = extract_info_from_input_product(
       path1, 'S2_GRS',
       # optionnels : params.get('code_site', None), params.get('geom', None)
   )
   filename = generate_ts_filename(l3algo_product, sat, source, roi)
   l3algo_product.save(dirname / filename)    # type(dirname) == pathlib.Path

De nombreuses autres clés sont disponibles pour le dictionnaire "params", cf. la suite de ce tutoriel.

Arguments spécifiques à certains readers
""""""""""""""""""""""""""""""""""""""""

cf. :ref:`le tuto relatif à la création de produits L3 <argu readers 2>`.

Arguments relatifs aux algorithes utilisés
""""""""""""""""""""""""""""""""""""""""""

cf. :ref:`le tuto relatif à la création de produits L3 <argu algos 2>`.

Génération de produits masqués
""""""""""""""""""""""""""""""

Il est possible de générer des séries temporelles masquées. Pour cela, il faut utiliser les clés ``ts_mask`` / ``ts_mask_path`` et ``tsmask_type``\ , resp. un objet TimeSeries (i.e., une série temporelle de masques créée avec SISPPEO et chargée en mémoire) / le path de la série temporelle de masques (i.e., une série temporelle de masques créée avec SISPPEO et sauvegardée sur le disque) et si elle est utilisée pour inclure ou exclure les zones masquées.

Par exemple :

.. code-block:: python

   params.update({
       'tsmask': tsmask_product, # ou 'tsmask_path: path/to/tsmask/product.nc
       'tsmask_type': 'IN' # or 'OUT'
   })

Il n'est pas possible d'utiliser à la fois des masques chargés en mémoire (via ``tsmask``\ ) et des masques sauvegardés sur le disque (via ``tsmask_path``\ ). Cependant, il est possible de masquer des séries temporelles a posteriori grâce à la fonction :py:func:`~sisppeo.products.timeseries.mask_time_series`.

L'utilisation de plusieurs séries temporelles de masques de manière combinée est possible, auquel cas on utilisera les clés ``lst_tsmask`` / ``lst_tsmask_path`` et ``lst_tsmask_type`` (de la même manière que pour les algorithmes, il est possible d'utiliser ces clés et de fournir des listes d'un seul élément).

Par exemple, afin de conserver les zones d'eau sans nuages :

.. code-block:: python

   params.update({
       'lst_tsmask': [watermask, cloudmask], # ou 'lst_tsmask_path: [path/to/watermask, path/to/cloudmask]
       'lst_tsmask_type': ['IN', 'OUT']
   })

Il est aussi possible de fournir des listes de listes de masques qui ne sont pas encore compilés en séries temporelles avec les arguments ``lst_l3masks`` / ``lst_l3masks_paths`` et ``lst_l3masks_types``.

Traitement sur une zone d'intérêt
"""""""""""""""""""""""""""""""""

cf. :ref:`le tuto relatif à la création de produits L3 <ROI 2>`.

Rééchantillonnage
"""""""""""""""""

cf. :ref:`le tuto relatif à la création de produits L3 <resampling 2>`.

Optimisation : mutualisation de l'extraction des bandes
"""""""""""""""""""""""""""""""""""""""""""""""""""""""

cf. :ref:`le tuto relatif à la création de produits L3 <mutualisation2>`.

Depuis des produits L3
^^^^^^^^^^^^^^^^^^^^^^

... en mémoire
""""""""""""""

Il suffit de procéder de la manière suivante :

.. code-block:: python

   from sisppeo.products import TimeSeries

   timeseries = TimeSeries.from_l3products([pdt1, pdt2, ..., pdtN])

... stockés sur le disque
"""""""""""""""""""""""""

Il suffit de procéder de la manière suivante :

.. code-block:: python

   from sisppeo.products import TimeSeries

   timeseries = TimeSeries.from_files([path1, path2, ..., pathN])

*Rq: il est possible de charger en mémoire une série temporelles depuis un fichier netCDF préalablement généré et enregistré sur le disque en utilisant la méthode de classe* :py:meth:`~sisppeo.products.timeseries.TimeSeries.from_file`.

Analyse
=======

Il est possible :


* d'extraire un ou plusieurs points, avec ou sans buffer : :py:func:`~sisppeo.utils.products.CoordinatesMixin.extract_point`, :py:func:`~sisppeo.utils.products.CoordinatesMixin.extract_points`;
* de calculer une poignée d'indicateurs statistiques classiques sur les différentes variables et images de la série temporelle : :py:func:`~sisppeo.products.timeseries.TimeSeries.compute_stats`;
* de plot une série temporelle pour un ou plusieurs points, pour une ou plusieurs variables : :py:func:`~sisppeo.products.timeseries.TimeSeries.plot_1d`;
* de plot un timelapse (sous la forme d'une mosaïque d'images) pour une ou plusieurs variables : :py:func:`~sisppeo.products.timeseries.TimeSeries.plot_2d`;
* de plot une carte des moyennes sur la série temporelle (pour une ou plusieurs variables) : :py:func:`~sisppeo.products.timeseries.TimeSeries.get_mean_map`, :py:func:`~sisppeo.products.timeseries.TimeSeries.plot_stats_maps`;
* de plot une carte des valeurs min/max sur la série temporelle (pour une ou plusieurs variables) : :py:func:`~sisppeo.products.timeseries.TimeSeries.get_min_map`, :py:func:`~sisppeo.products.timeseries.TimeSeries.get_max_map`, :py:func:`~sisppeo.products.timeseries.TimeSeries.plot_stats_maps`;
* d'étudier la répartition des valeurs pour une variable donnée à une date t (sous la forme d'un histogramme) : :py:func:`~sisppeo.products.timeseries.TimeSeries.plot_hists`.

----

Remarque
========

Si vous avez une question ou si vous avez besoin d'informations complémentaires, i) consultez le reste de la documentation, ii) référez-vous au code de SISPPEO puis si besoin iii) contactez `moi <mailto:arthur.coque@inrae.fr>`_\.
