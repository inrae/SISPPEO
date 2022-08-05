# Copyright 2020 UMR GET
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
from sklearn import cluster
from sklearn import metrics
from sklearn.mixture import GaussianMixture as GMM
from sklearn.naive_bayes import GaussianNB
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import cross_val_score
from sklearn.svm import LinearSVC
from sklearn.model_selection import GridSearchCV
from .DWCommon import DWConfig, DWutils
import logging

class DWImageClustering:

    def __init__(self, bands, bands_keys, invalid_mask, config: DWConfig):

        self.bands, self.bands_keys, self.invalid_mask = self.check_necessary_bands(bands, bands_keys, invalid_mask)

        self.config = config

        self.data_as_columns = None
        self.clusters_labels = None
        self.clusters_params = None
        self.cluster_matrix = None
        self.water_cluster = None
        self.water_mask = None
        self.best_k = None

        return

    @staticmethod
    def check_necessary_bands(bands, bands_keys, invalid_mask):
        """
        Check if the bands_keys combination for the clustering algorithm are available in bands
        and if they all have the same shape
        :param invalid_mask: array mask with the invalid pixels
        :param bands: image bands available
        :param bands_keys: bands combination
        :return: bands and bands_keys
        """

        if type(bands) is not dict:
            raise OSError('Bands not in dictionary format')

        # if len(bands) != len(bands_keys):
        #     raise OSError('Bands and bands_keys have different sizes')

        # get the first band as reference of size
        ref_band = list(bands.keys())[0]
        ref_shape = bands[ref_band].shape

        # check the invalid_mask
        if invalid_mask is not None and invalid_mask.shape != ref_shape:
            raise OSError('Invalid mask and {} with different shape in clustering core'.format(ref_band))
        elif invalid_mask is None:
            invalid_mask = np.zeros(ref_shape, dtype=bool)

        # check if the MNDWI index exist
        if 'mndwi' not in bands.keys():
            mndwi, mndwi_mask = DWutils.calc_normalized_difference(bands['Green'], bands['Mir2'], invalid_mask)
            invalid_mask |= mndwi_mask
            bands.update({'mndwi': mndwi})

        # check if the NDWI index exist
        if 'ndwi' not in bands.keys():
            ndwi, ndwi_mask = DWutils.calc_normalized_difference(bands['Green'], bands['Nir'], invalid_mask)
            invalid_mask |= ndwi_mask
            bands.update({'ndwi': ndwi})

        # check if the list contains the required bands
        for band in bands_keys:

            if band not in bands.keys():
                raise OSError('Band {}, not available in the dictionary'.format(band))

            if type(bands[band]) is not np.ndarray:
                raise OSError('Band {} is not a numpy array'.format(band))

            if ref_shape != bands[band].shape:
                raise OSError('Bands {} and {} with different size in clustering core'.format(band, ref_band))

        return bands, bands_keys, invalid_mask

    def bands_to_columns(self):
        """
        Convert self.bands to a column type matrix where each band is a column
        It follows the order of the keys ordered
        :return: column type matrix
        """

        # load all the bands in the dictionary as numpy arrays columns
        # the bands will appear in sorted order
        valid_data_list = []

        for key in sorted(self.bands.keys()):
            band_array = self.bands[key]

            valid_data_list.append(band_array[~self.invalid_mask])

        # prepare the multidimensional data array (bands as columns)
        data = np.c_[valid_data_list].transpose()

        return data

    ############################################################################
    # Clustering related functions
    # -------------------------------------------------------------------------#
    def apply_cluster(self, data):
        """
        Apply the cluster algorithm to the data. Number of cluster is in self.best_k
        :param data: data to be clustered
        :return: Vector with the labels
        """
        # before calling the clustering function, normalize the data using min_max_scaler
        # scaled_data = preprocessing.minmax_scale(data)

        if self.config.clustering_method == 'kmeans':
            cluster_model = cluster.KMeans(n_clusters=self.best_k, init='k-means++')
        elif self.config.clustering_method == 'gauss_mixture':
            cluster_model = GMM(n_components=self.best_k, covariance_type='full')
        else:
            cluster_model = cluster.AgglomerativeClustering(n_clusters=self.best_k, linkage='ward')

        cluster_model.fit(data)
        return cluster_model.labels_

    def find_best_k(self, data):
        """
        Find the best number of clusters according to an metrics.
        :param data: data to be tested
        :return: number of clusters
        """
        # # split data for a smaller set (for performance purposes)
        # train_data, test_data = getTrainTestDataset(data, train_size, min_train_size=1000)

        min_k = self.config.min_clusters
        max_k = self.config.max_clusters

        if min_k == max_k:
            logging.info('Same number for minimum and maximum clusters: k = {}'.format(min_k))
            self.best_k = min_k
            return self.best_k

        if self.config.score_index == 'silhouete':
            logging.info('Selection of best number of clusters using Silhouete Index:')
        else:
            logging.info('Selection of best number of clusters using Calinski-Harabasz Index:')

        computed_metrics = []

        for num_k in range(min_k, max_k + 1):
            # cluster_model = cluster.KMeans(n_clusters=num_k, init='k-means++')
            cluster_model = cluster.AgglomerativeClustering(n_clusters=num_k, linkage='ward')

            labels = cluster_model.fit_predict(data)

            if self.config.score_index == 'silhouete':
                computed_metrics.append(metrics.silhouette_score(data, labels))
                logging.info('k={} :Silhouete index={}'.format(num_k, computed_metrics[num_k - min_k]))

            else:
                computed_metrics.append(metrics.calinski_harabasz_score(data, labels))
                logging.info('k={} :Calinski_harabasz index={}'.format(num_k, computed_metrics[num_k - min_k]))

        # the best solution is the one with higher index
        self.best_k = computed_metrics.index(max(computed_metrics)) + min_k

        return self.best_k

    def calc_clusters_params(self, data, clusters_labels):
        """
        Calculate parameters for each encountered cluster.
        Mean, Variance, Std-dev
        :param data: Clustered data
        :param clusters_labels: Labels for the data
        :return: List with cluster statistics
        """
        clusters_params = []
        for label_i in range(self.best_k):
            # first slice the values in the indexed cluster
            cluster_i = data[clusters_labels == label_i, :]

            cluster_param = {'clusterid': label_i}
            cluster_param.update({'mean': np.mean(cluster_i, 0)})
            cluster_param.update({'variance': np.var(cluster_i, 0)})
            cluster_param.update({'stdev': np.std(cluster_i, 0)})
            cluster_param.update({'diffb2b1': cluster_param['mean'][1] - cluster_param['mean'][0]})
            clusters_params.append(cluster_param)

        return clusters_params

    def identify_water_cluster(self):
        """
        Finds the water cluster within all the clusters.
        It can be done using MNDWI or Mir2 bands
        :return: water cluster object
        """

        if self.config.detect_water_cluster == 'maxmndwi':
            if 'mndwi' not in self.bands.keys():
                raise OSError('MNDWI band necessary for detecting water with maxmndwi option')

            water_cluster = self.detect_cluster('value', 'max', 'mndwi')

        elif self.config.detect_water_cluster == 'minmir2':
            if 'mndwi' not in self.bands.keys():
                raise OSError('Mir2 band necessary for detecting water with minmir2 option')
            water_cluster = self.detect_cluster('value', 'min', 'Mir2')

        else:
            raise OSError('Method {} for detecting water cluster does not exist'.
                          format(self.config.detect_water_cluster))

        return water_cluster

    def detect_cluster(self, param, logic, band1, band2=None):
        """
        Detects a cluster according to a specific metrics
        :param param: Which parameter to search (mean, std-dev, variance,  ...)
        :param logic: Max or Min
        :param band1: The band related to the parameter
        :param band2:
        :return: Cluster object that satisfies the logic
        """
        # get the bands available in the columns
        available_bands = sorted(self.bands.keys())

        param_list = []
        if band1:
            idx_band1 = available_bands.index(band1)
        if band2:
            idx_band2 = available_bands.index(band2)

        for clt in self.clusters_params:
            if param == 'diff':
                if not idx_band2:
                    raise OSError('Two bands needed for diff method')
                param_list.append(clt['mean'][idx_band1] - clt['mean'][idx_band2])

            elif param == 'value':
                param_list.append(clt['mean'][idx_band1])

        if logic == 'max':
            idx_detected = param_list.index(max(param_list))
        else:
            idx_detected = param_list.index(min(param_list))

        return self.clusters_params[idx_detected]

    ############################################################################
    # Classification functions
    # -------------------------------------------------------------------------#
    def supervised_classification(self, data, train_data, clusters_labels):
        """
        Applies a machine learning supervised classification
        :param data: new data to be classified
        :param train_data: reference data
        :param clusters_labels: labels for the reference data
        :return: labels for the new data
        """
        if self.config == 'SVM':
            clusters_labels = self.apply_svm(data, clusters_labels, train_data)
        elif self.config.classifier == 'MLP':
            clusters_labels = self.apply_mlp(data, clusters_labels, train_data)
        else:
            clusters_labels = self.apply_naive_bayes(data, clusters_labels, train_data)

        return clusters_labels

    @staticmethod
    def apply_svm(data, clusters_labels, clusters_data):
        """
        Apply Support Vector Machine to classify data
        :param data: new data to be classified
        :param clusters_labels: labels for the reference data
        :param clusters_data: reference data
        :return: labels for the new data
        """
        # train a SVM classifier with the data and labels provided
        # before it, test a grid to check the best C parameter
        grid = GridSearchCV(LinearSVC(), {'C': [1.0, 2.0, 4.0, 8.0, 50, 100, 100000]})

        grid.fit(clusters_data, clusters_labels)

        logging.info('Applying clusters Suport Vector Machine classifier')
        logging.info('Cross_val_score:{}'.format(grid.best_score_))

        model = grid.best_estimator_
        model.fit(clusters_data, clusters_labels)

        # return the new predicted labels for the whole dataset
        return model.predict(data)

    @staticmethod
    def apply_naive_bayes(data, clusters_labels, clusters_data):
        """
        Apply Naive Bayes classifier to classify data
        :param data: new data to be classified
        :param clusters_labels: labels for the reference data
        :param clusters_data: reference data
        :return: labels for the new data
        """
        # train a NB classifier with the data and labels provided
        model = GaussianNB()

        logging.info('Applying clusters based naive bayes classifier')
        # logging.info('Cross_val_score:{}'.format(cross_val_score(model, clusters_data, clusters_labels)))

        model.fit(clusters_data, clusters_labels)

        # return the new predicted labels for the whole dataset
        return model.predict(data)

    @staticmethod
    def apply_mlp(data, clusters_labels, clusters_data):
        """
        Apply Multilayer Perceptron classifier to classify data
        :param data: new data to be classified
        :param clusters_labels: labels for the reference data
        :param clusters_data: reference data
        :return: labels for the new data
        """
        clf = MLPClassifier(solver='lbfgs', alpha=0.1, hidden_layer_sizes=(8, 8), random_state=1)

        logging.info('Applying clusters based Multilayer Perceptron classifier')
        logging.info('Cross_val_score:{}'.format(cross_val_score(clf, clusters_data, clusters_labels)))

        clf.fit(clusters_data, clusters_labels)

        return clf.predict(data)

    def create_matrice_cluster(self, indices_array):
        """
        Recreates the matrix with the original shape with the cluster labels for each pixel
        :param indices_array: position of the clustered pixels in the matrix
        :return: clustered image (0-no data, 1-water, 2, 3, ... - other)
        """
        # create an empty matrix
        matrice_cluster = np.zeros_like(list(self.bands.values())[0])

        # apply water pixels to value 1
        matrice_cluster[indices_array[0][self.clusters_labels == self.water_cluster['clusterid']],
                        indices_array[1][self.clusters_labels == self.water_cluster['clusterid']]] = 1

        # loop through the remaining labels and apply value >= 3
        new_label = 2
        for label_i in range(self.best_k):
            if label_i != self.water_cluster['clusterid']:
                matrice_cluster[indices_array[0][self.clusters_labels == label_i],
                                indices_array[1][self.clusters_labels == label_i]] = new_label
                new_label += 1

        return matrice_cluster

    ############################################################################
    # Other utility functions
    # -------------------------------------------------------------------------#
    def split_data_by_bands(self, data, selected_keys):
        """
        Gets data in column format (each band is a column) and returns only the desired bands
        :param data: data in column format
        :param selected_keys: bands keys to be extracted
        :return: data in column format only with the selected bands
        """
        bands_index = []
        bands_keys = list(sorted(self.bands.keys()))

        for key in selected_keys:
            bands_index.append(bands_keys.index(key))

        return data[:, bands_index]

    def create_product_name(self):

        clustering = self.config.clustering_method
        classifier = self.config.classifier
        clip_band = self.config.clip_band

        if clustering == 'aglomerative':
            product_name = 'AC_'
        elif clustering == 'gauss_mixture':
            product_name = 'GM_'
        elif clustering == 'kmeans':
            product_name = 'KM_'
        else:
            product_name = 'ERROR_'

        if classifier == 'naive_bayes':
            product_name += 'NB_'
        elif classifier == 'MLP':
            product_name += 'MLP_'
        elif classifier == 'Hull':
            product_name += 'Hull_'
        elif classifier == 'SVM':
            product_name += 'SVM'
        else:
            product_name += 'ERROR_'

        if clip_band:
            product_name += 'CM_'
        for key in self.bands_keys:
            product_name += str(key)

        return product_name

    ############################################################################
    # MAIN run_detect_water function
    # -------------------------------------------------------------------------#
    def run_detect_water(self, config=None):
        """
        Runs the detect_water function
        :param config: Options dictionary for the processing
        :return: clustered matrix where 1= water
        """
        # if passed options, override the existing options
        self.config = config if type(config) == DWConfig else self.config

        # Transform the rasters in a matrix where each band is a column
        self.data_as_columns = self.bands_to_columns()

        # two line vectors indicating the indexes (line, column) of valid pixels
        ind_data = np.where(~self.invalid_mask)

        # if algorithm is not kmeans, split data for a smaller set (for performance purposes)
        if self.config.clustering_method == 'kmeans':
            train_data_as_columns = self.data_as_columns
        else:
            # original train data keeps all the bands
            train_data_as_columns, _ = DWutils.get_train_test_data(self.data_as_columns,
                                                                   self.config.train_size,
                                                                   self.config.min_train_size,
                                                                   self.config.max_train_size)

        # create data bunch only with the bands used for clustering
        split_train_data_as_columns = self.split_data_by_bands(train_data_as_columns, self.bands_keys)
        split_data_as_columns = self.split_data_by_bands(self.data_as_columns, self.bands_keys)

        # find the best clustering solution (k = number of clusters)
        self.best_k = self.find_best_k(split_train_data_as_columns)

        # apply the clusterization algorithm and return labels and train dataset
        train_clusters_labels = self.apply_cluster(split_train_data_as_columns)

        # calc statistics for each cluster
        self.clusters_params = self.calc_clusters_params(train_data_as_columns, train_clusters_labels)

        # detect the water cluster
        self.water_cluster = self.identify_water_cluster()

        # if we are dealing with aglomerative cluster or other diff from kmeans, we have only a sample of labels
        # we need to recreate labels for all the points using supervised classification
        if self.config.clustering_method != 'kmeans':
            self.clusters_labels = self.supervised_classification(split_data_as_columns,
                                                                  split_train_data_as_columns,
                                                                  train_clusters_labels)
        else:
            self.clusters_labels = train_clusters_labels

        # after obtaining the final labels, if clip MIR is not None, clip MIR above threshold
        if self.config.clip_value:
            self.clusters_labels[(self.clusters_labels == self.water_cluster['clusterid']) &
                                 (self.bands[self.config.clip_band][~self.invalid_mask] > self.config.clip_value)] = -1

        # create an cluster array based on the cluster result (water will be value 1)
        self.cluster_matrix = self.create_matrice_cluster(ind_data)
        self.water_mask = self.cluster_matrix == 1

        return self.cluster_matrix

# todo: fazer a rotina ficar genrica para as bandas do machine learning
# todo: deixar o train_data para poder fazer um gráfico mais rápido depois???
# todo: usar o conceito de driver para o Landsat e Theia
# todo: criar um config ou passar os options para o wrapper
