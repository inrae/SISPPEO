import ast
import configparser
from importlib.resources import path
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

with path(__package__, 'WaterDetect.ini') as p:
    config_file = p


class DWConfig:
    _config_file = p
    _defaults = {'reference_band': 'Red',
                 'maximum_invalid': '0.8',
                 'create_composite': 'True',
                 'pdf_reports': 'False',
                 'save_indices': 'False',
                 'texture_streching': 'False',
                 'clustering_method': 'aglomerative',
                 'min_clusters': '1',
                 'max_clusters': '5',
                 'clip_band': 'None',
                 'clip_value': 'None',
                 'classifier': 'naive_bayes',
                 'train_size': '0.1',
                 'min_train_size': '1000',
                 'max_train_size': '10000',
                 'score_index': 'calinsk',
                 'detectwatercluster': 'maxmndwi',
                 'clustering_bands': "[['ndwi', 'Nir']]",
                 'graphs_bands': "[['mbwi', 'mndwi'], ['ndwi', 'mbwi']]",
                 'plot_ts': 'False'
                 }

    def __init__(self, config_file=None):
        self.config = self.load_config_file(config_file)

    def return_defaults(self, section, key):

        default_value = self._defaults[key]

        print('Key {} not found in section {}: using default value {}'.format(key, section, default_value))

        return default_value

    def get_option(self, section, key, evaluate: bool):

        try:
            str_value = self.config.get(section, key)

        except Exception:
            str_value = self.return_defaults(section, key)

        if evaluate and str == type(str_value):
            try:
                return ast.literal_eval(str_value)
            except Exception:
                return str_value
        else:
            return str_value

    def load_config_file(self, config_file):

        if config_file:
            self._config_file = config_file

        print('Loading configuration file {}'.format(self._config_file))

        DWutils.check_path(self._config_file)

        config = configparser.ConfigParser()
        config.read(self._config_file)

        return config

    @property
    def average_results(self):
        return self.get_option('Clustering', 'average_results', evaluate=True)

    @property
    def min_positive_pixels(self):
        return self.get_option('Clustering', 'min_positive_pixels', evaluate=True)

    @property
    def clustering_method(self):
        return self.get_option('Clustering', 'clustering_method', evaluate=False)

    @property
    def linkage(self):
        return self.get_option('Clustering', 'linkage', evaluate=False)

    @property
    def train_size(self):
        return self.get_option('Clustering', 'train_size', evaluate=True)

    @property
    def min_train_size(self):
        return self.get_option('Clustering', 'min_train_size', evaluate=True)

    @property
    def max_train_size(self):
        return self.get_option('Clustering', 'max_train_size', evaluate=True)

    @property
    def score_index(self):
        return self.get_option('Clustering', 'score_index', evaluate=False)

    @property
    def classifier(self):
        return self.get_option('Clustering', 'classifier', evaluate=False)

    @property
    def detect_water_cluster(self):
        return self.get_option('Clustering', 'detectwatercluster', evaluate=False)

    @property
    def min_clusters(self):
        return self.get_option('Clustering', 'min_clusters', evaluate=True)

    @property
    def max_clusters(self):
        return self.get_option('Clustering', 'max_clusters', evaluate=True)

    @property
    def clustering_bands(self):

        bands_lst = self.get_option('Clustering', 'clustering_bands', evaluate=True)

        # if bands_keys is not a list of lists, transform it
        if type(bands_lst[0]) == str:
            bands_lst = [bands_lst]

        return bands_lst

    @property
    def clip_band(self):
        bands_lst = self.get_option('Clustering', 'clip_band', evaluate=True)

        if type(bands_lst) == str:
            return [bands_lst]
        else:
            return bands_lst if bands_lst is not None else []

    @property
    def clip_inf_value(self):
        value = self.get_option('Clustering', 'clip_inf_value', evaluate=True)

        if value is not None:
            return value if type(value) is list else [value]
        else:
            return []

    @property
    def clip_sup_value(self):
        value = self.get_option('Clustering', 'clip_sup_value', evaluate=True)

        if value is not None:
            return value if type(value) is list else [value]
        else:
            return []


class DWutils:
    @staticmethod
    def check_path(path_str, is_dir=False):
        """
        Check if the path/file exists and returns a Path variable with it
        :param path_str: path string to test
        :param is_dir: whether if it is a directory or a file
        :return: Path type variable
        """

        if path_str is None:
            return None

        path = Path(path_str)

        if is_dir:
            if not path.is_dir():
                raise OSError('The specified folder {} does not exist'.format(path_str))
        else:
            if not path.exists():
                raise OSError('The specified file {} does not exist'.format(path_str))

        print(('Folder' if is_dir else 'File') + ' {} verified.'.format(path_str))
        return path

    @staticmethod
    def calc_normalized_difference(img1, img2, mask=None):
        """
        Calc the normalized difference of given arrays (img1 - img2)/(img1 + img2).
        Updates the mask if any invalid numbers (ex. np.inf or np.nan) are encountered
        :param img1: first array
        :param img2: second array
        :param mask: initial mask, that will be updated
        :return: nd array filled with -9999 in the mask and the mask itself
        """

        # changement for negative SRE scenes
        if mask is not None:
            min_cte = np.min([np.min(img1[~mask]), np.min(img2[~mask])])
        else:
            min_cte = np.min([np.min(img1), np.min(img2)])

        if min_cte <= 0:
            min_cte = -min_cte + 0.001
        else:
            min_cte = 0

        nd = ((img1 + min_cte) - (img2 + min_cte)) / ((img1 + min_cte) + (img2 + min_cte))

        # if any of the bands is set to zero in the pixel, makes a small shift upwards, as proposed by olivier hagole
        # https://github.com/olivierhagolle/modified_NDVI
        # nd = np.where((img1 > 0) & (img2 > 0), (img1-img2) / (img1 + img2), np.nan)
        # (img1+0.005-img2-0.005) / (img1+0.005 + img2+0.005))

        # nd = np.where((img1 <= 0) & (img2 <= 0), np.nan, (img1-img2) / (img1 + img2))

        # nd = (img1-img2) / (img1 + img2)

        # nd[~mask] = MinMaxScaler(feature_range=(-1,1), copy=False).fit_transform(nd[~mask].reshape(-1,1)).reshape(-1)

        nd[nd > 1] = 1
        nd[nd < -1] = -1

        # if result is infinite, result should be 1
        nd[np.isinf(nd)] = 1

        # nd_mask = np.isinf(nd) | np.isnan(nd) | mask
        nd_mask = np.isnan(nd) | mask

        nd = np.ma.array(nd, mask=nd_mask, fill_value=-9999)

        return nd.filled(), nd.mask

    @staticmethod
    def get_train_test_data(data, train_size, min_train_size, max_train_size):
        """
        Split the provided data in train-test bunches
        :param min_train_size: minimum data quantity for train set
        :param max_train_size: maximum data quantity for train set
        :param train_size: percentage of the data to be used as train dataset
        :param data: data to be split
        :return: train and test datasets
        """
        dataset_size = data.shape[0]

        if (dataset_size * train_size) < min_train_size:
            train_size = min_train_size / dataset_size
            train_size = 1 if train_size > 1 else train_size

        elif (dataset_size * train_size) > max_train_size:
            train_size = max_train_size / dataset_size

        return train_test_split(data, train_size=train_size)

    @staticmethod
    def create_bands_dict(bands_array, bands_order):

        bands_dict = {}
        for i, band in enumerate(bands_order):
            bands_dict.update({band: bands_array[:, :, i]})

        return bands_dict

    @staticmethod
    def listify(lst, uniques=[]):
        # pdb.set_trace()
        for item in lst:
            if isinstance(item, list):
                uniques = DWutils.listify(item, uniques)
            else:
                uniques.append(item)
        return uniques.copy()
