**************
User Workspace
**************

.. note::
   This tutorial will soon be available in English.

Il est possible de définir un espace dans lequel stocker différents algorithmes, masques et calibrations que SISPPEO sera en mesure d'aller chercher comme s'ils étaient "natifs" (ils apparaissent même dans les ``--help`` de la CLI !).

Cela peut être utile pour les raisons suivantes (liste non-exhaustive) :

* problèmes de permissions sur un serveur partagé : SISPPEO est installé à un emplacement où l'utilisateur n'a pas la permission d'effectuer des modifications. Définir un workspace dans son "/home" (exemple) permet de passer outre ce problème.

* rapidité de développement : créer ou apporter des modifications aux algorithmes situés dans ledit workspace ne nécessite pas une réinstallation de SISPPEO.

Le workspace se structure de la manière suivante :::

   <workspace>
   ├── custom_algorithms
   │         └── __init__.py
   ├── custom_masks
   │         └── __init__.py
   └── resources
       ├── algo_calibration
       ├── algo_config.yaml
       └── mask_config.yaml

Cette structure étant calquée sur celle interne à SISPPEO, la marche à suivre pour le développement d'un nouvel algorithme reste celle présentée dans :doc:`ce tutoriel </development/add_algo>`.

L'\ **unique différence** réside dans la ligne suivante :

.. code-block:: python

   from sisppeo.utils.config import wc_algo_config as algo_config, wc_calib

... qui devient :

.. code-block:: python

   from sisppeo.utils.config import user_algo_config as algo_config, user_calib

Attention : si vous donnez le même nom à l'un de vos algorithmes (attribut "name" de votre classe) qu'à un algorithme existant, vous ne serez pas en mesure de l'utiliser.

----

Remarque
========

Si vous avez une question ou si vous avez besoin d'informations complémentaires, i) référez-vous aux différents algorithmes fournis avec le paquet :py:mod:`sisppeo.wcproducts` puis si besoin ii) contactez `moi <mailto:arthur.coque@inrae.fr>`_\.
