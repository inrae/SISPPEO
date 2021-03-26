# Écrire et ajouter un nouvel algorithme à SISPPEO

## Introduction

Dans SISPPEO, les algorithmes de télédétection se présentent sous la forme
d'une classe. Cette dernière comporte deux méthodes à implémenter :
- `__init__`, pour initialiser un algorithme pour un type de produit
satellitaire donné (e.g., "S2_GRS") et optionnellement pour une calibration
(i.e. un ensemble de paramètres) et une bande données ;
- `__call__`, qui permet d'appeler directement l'instance de classe (à la
manière d'une fonction). Cette méthode renvoie le tableau de résultats (ainsi
que les paramètres/coefficients utilisés lors des calculs).

Chaque algorithme contient par ailleurs 2 attributs publics :
- `name`, qui est le "label" (i.e. court nom en camel_case, ~id de l'algo
utilisé pour le sélectionner lors de la création d'un produit L3) de
l'algorithme ;
- `requested_bands`, qui est la liste des bandes utilisées par l'algorithme.

## Structure minimale

```python
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
```

## Exemples

### 1. Cas "trivial" (i.e. pas de bande ni de calibration à spécifier) : NDWI

```python
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
```

#### 1. Initialisation : *\_\_init\_\_*

L'initialisation de cet algorithme requiert un paramètre nommé `product_type`,
qui permet de renseigner le type de produit que l'algorithme va être amené à
traiter. Cela permet d'aller automatiquement chercher dans le fichier de
configuration (ici *"resources/wc_algo_config.yaml"*) dudit algorithme les
bandes nécessaires (i.e. à extraire).

Dans le cas où cet algorithme n'est pas fait pour ce produit satellitaire, un
message d'erreur est renvoyé.

#### 2. Méthode *\_\_call\_\_*

Cette méthode prend en entrée les tableaux (*xarray.DataArray*) des bandes
précédemment extraites (par le reader) et renvoie le tableau
(*xarray.DataArray*) de résultats (ici, du NDWI) ainsi qu'un dictionnaire vide
(aui peut contenir les paramètres/coefficients utilisés lors des calculs, s'il
y en a).

### 3. Cas où plusieurs calibrations et bandes utilisables possibles : SPMNechad

```python
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
```

Cf. [le cas simple](#1-initialisation-__init__).

Ici, en plus de précédemment, il faut spécifier une bande à utiliser (parmis
celles autorisées dans le fichier de configuration de l'algorithme, ici : de
"B4" à "B8A"). Si aucune bande n'est précisée par l'utilisateur,
`_default_band` (ici, "B4") est utilisée.

En plus de cela, différentes calibrations sont disponibles. Elles peuvent être :

- fournies par l'utilisateur sous la forme d'un chemin d'accès à un fichier de
configuration correctement formaté (pour cela, se référer à ceux déjà fournis
avec SISPPEO) ;
- choisies parmis celles disponible "de base" et à retrouver dans le fichier de
calibration de l'algorithme (ici
*"resources/wc_algo_calibration/spm_nechad.yaml"*). Pour spm-nechad par
exemple, les calibrations disponibles sont "Nechad_2010" et "Nechad_2016".

```python
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
```

Cf. [le cas simple](#1-initialisation-__init__).

Ici, contrairement à précédemment, le dictionnaire renvoyé n'est pas vide : il
contient les différents paramètres/coefficients relatifs à la configuration (de
l'algorithme) choisie.

## "Intégration" de l'algorithme

Il faut ensuite importer la classe (i.e. l'algorithme) nouvellement créée dans
le fichier *\_\_init\_\_.py* du module auquel il appartient (e.g. wcproducts).
Ex :

```python
from sisppeo.wcproducts.spm import SPMGet, SPMHan, SPMNechad, TURBIDogliotti
```

## Remarque

Si vous avez une question ou si vous avez besoin d'informations
complémentaires, i) référez-vous aux différents algorithmes fournis avec
le paquet `SISPPEO.wcproducts` puis si besoin ii) contacter
l'[auteur](#auteur-du-document) de ce tutoriel.

<br>

# Auteur du document

Arthur Coqué (arthur.coque@inrae.fr)
