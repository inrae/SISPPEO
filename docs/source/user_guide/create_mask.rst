*****************************
Create a mask (L3MaskProduct)
*****************************

.. note::
   This tutorial will soon be available in English.

*Rq: lire au préalable les tutoriels sur* :doc:`la création de produits L3 </user_guide/create_l3algo>` *et de* :doc:`séries temporelles </user_guide/create_time_series>` *afin de prendre en main SISPPEO.*

Il est possible de créer des masques (binaires) avec SISPPEO, que ce soit via la CLI ou bien en important SISPPEO dans une console ou un script Python.

2 masques sont actuellement disponibles :

* masque eau : `WaterDetect <https://github.com/cordmaur/WaterDetect>`_ ;

* masque nuage : `s2cloudless <https://github.com/sentinel-hub/sentinel2-cloud-detector>`_.

Avec la CLI, il faut utiliser la commande :command:`sisppeo create-l3mask`\ , tandis qu'en tant que module, il faut utiliser la clé "l3 mask" lors de l'appel de la fonction :py:func:`sisppeo.generate() <sisppeo.main.generate>`.

Les arguments utilisés sont similaires à ceux utilisés lors de la création de produits L3 ou de séries temporelles, exceptés :

* ``--mask`` | ``mask``\ /\ ``lst_mask`` au lieu de (resp.) ``--algo`` | ``algo``\ /\ ``lst_algo`` ;

* un nouvel argument spécifique : ``--proc_res`` | ``processing_resolution``\ /\ ``lst_proc_res``. Cet argument optionnel permet de spécifier la résolution utilisée lors du traitement, si on la veut différente (= moins fine) que celle du ou des produits en sortie (-> permet de fortement alléger les calculs pour des résultats parfois comparables).

De même que pour les produits L3, on peut compiler des masques en séries temporelles (ou bien créer directement des séries temporelles de masques). Il suffit pour cela d'utiliser la commande ``sisppeo create-timeseries-mask`` (CLI) ou la clé "time series (mask)" lors de l'appel de la commande ``sisppeo.generate``.

*Rq: il est recommandé par l'auteur de WaterDetect d'utiliser des images L2A obtenues avec MAJA (bandes "SRE"), avec les masques CLM (bits 1 et 5) et MG2 (bits 4, 5, 6, 7 et 8).*

----

Remarque
========

Si vous avez une question ou si vous avez besoin d'information complémentaire, i) consultez le reste de la documentation, ii) référez-vous au code de SISPPEO puis si besoin iii) contactez `moi <mailto:arthur.coque@inrae.fr>`_\.
