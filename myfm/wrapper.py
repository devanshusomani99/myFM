import numpy as np
from scipy import (special, sparse as sps)
from tqdm import tqdm

from . import _myfm as core


def elem_wise_square(X):
    X_2 = X.copy()
    if sps.issparse(X_2):
        X_2.data[:] = X_2.data ** 2
    else:
        X_2 = X_2 ** 2
    return X_2

REAL = np.float64 

class MyFMRegressor(object):

    def __init__(
        self, rank,
        init_stdev=0.1, random_seed=42,
        alpha_0=1.0, beta_0=1.0, gamma_0=1.0, mu_0=0.0, reg_0=1.0,
    ):
        """Factorization machine with Gibbs sampling.

        Parameters
        ----------
        rank : int
            The number of factors.

        init_stdev : float, optional (defalult = 0.1)
            The standard deviation for initialization.
            The factorization machine weights are randomely sampled from
            `Normal(0, init_stdev)`.

        random_seed : integer, optional (default = 0.1)
            The random seed used inside the whole learning process.

        alpha_0 : float, optional (default = 1.0)
            The half of alpha parameter for the gamma-distribution
            prior for alpha, lambda_w and lambda_V.
            Together with beta_0, the priors for these parameters are
            alpha, lambda_w, lambda_v ~ Gamma(alpha_0 / 2, beta_0 / 2)

        beta_0 : float, optioal (default = 1.0)
            See the explanation for alpha_0 .

        gamma_0: float optional (default = 1.0)
            Inverse variance of the prior for mu_w, mu_v.
            Together with mu_0, the priors for these parameters are
            mu_w, mu_v ~ Normal(mu_0, 1 / gamma_0)

        mu_0:
            See the explanation for gamma_0.

        reg_0:
            Inverse variance of tthe prior for w0.
            w0 ~ Normal(0, 1 / reg_0)
        """
        self.rank = rank

        self.init_stdev = init_stdev
        self.random_seed = random_seed

        self.alpha_0 = alpha_0
        self.beta_0 = beta_0
        self.gamma_0 = gamma_0
        self.mu_0 = mu_0

        self.reg_0 = reg_0

        self.fms_ = []
        self.hypers_ = []

        self.n_groups_ = None

    def __str__(self):
        return "{class_name}(init_stdev={init_stdev}, alpha_0={alpha_0}, beta_0={beta_0}, gamma_0={gamma_0}, mu_0={mu_0}, reg_0={reg_0})".format(
            class_name=self.__class__.__name__,
            init_stdev=self.init_stdev,
            alpha_0=self.alpha_0, beta_0=self.beta_0,
            gamma_0=self.gamma_0, mu_0=self.mu_0,
            reg_0=self.reg_0
        )

    def fit(self, X, y, X_test=None, X_rel=[], y_test=None,
            n_iter=100, n_kept_samples=None, grouping=None, callback=None):
        """Performs Gibbs sampling to fit the data.
        Parameters
        ----------
        X : 2D array-like.
            Explanation variable.

        y : 1D array-like.
            Target variable.

        n_iter : int, optional (defalult = 100)
            Iterations to perform.

        n_kept_samples: int, optional (default = None)
            The number of samples to store.
            If `None`, the value is set to `n_iter` - 5.

        grouping: Integer array, optional (default = None)
            If not `None`, this specifies which column of X belongs to which group.
            That is, if grouping[i] is g, then, w_i and V_{i, r}
            will be distributed according to
            Normal(mu_w[g], lambda_w[g]) and Normal(mu_V[g, r], lambda_V[g,r]),
            respectively.
            If `None`, all the columns of X are assumed to belong to a single group 0.

        callback: function(int, fm, hyper) -> bool, optional(default = None)
            Called at the every end of each iteration.
        """
        if X_rel:
            shape_rel_all = {
                rel.mapper_size for rel in X_rel
            }
            if len(shape_rel_all) > 1:
                raise RuntimeError('At lease X or X_rel must be provided.')
            X_rel_shape = list(shape_rel_all)[0]
        else:
            X_rel_shape = None
            
        if X is None:
            if not X_rel:
                raise RuntimeError('At lease X or X_rel must be provided.')
            X = sps.csr_matrix((X_rel_shape, 0), dtype=REAL)
        else:
            if X_rel_shape is not None:
                if X.shape[0] != X_rel_shape:
                    raise RuntimeError('X and X_rel have different shape.')
            

        assert X.shape[0] == y.shape[0]
        dim_all = X.shape[1] + sum([rel.feature_size for rel in X_rel])

        if n_kept_samples is None:
            n_kept_samples = n_iter - 10
        else:
            assert n_iter >= n_kept_samples

        config_builder = core.ConfigBuilder()

        for key in ['alpha_0', 'beta_0', 'gamma_0', 'mu_0', 'reg_0']:
            value = getattr(self, key)
            getattr(config_builder, "set_{}".format(key))(value)
        if grouping is None:
            self.n_groups_ = 1
            config_builder.set_indentical_groups(dim_all)
        else:
            assert X.shape[1] == len(grouping)
            self.n_groups_ = np.unique(grouping).shape[0]
            config_builder.set_group_index(grouping)

        pbar = None
        if (X_test is None and y_test is None):
            do_test = False
        elif (X_test is not None and y_test is not None):
            assert X_test.shape[0] == y_test.shape[0]
            do_test = True
        else:
            raise RuntimeError("Must specify both X_test and y_test.")

        config_builder.set_n_iter(n_iter).set_n_kept_samples(n_kept_samples)

        X = sps.csr_matrix(X)
        if X.dtype != np.float64:
            X.data = X.data.astype(np.float64)
        y = self.process_y(y)
        self.set_tasktype(config_builder)

        config = config_builder.build()

        if callback is None:
            pbar = tqdm(total=n_iter)
            if do_test:
                X_test = sps.csr_matrix(X_test)
                X_test.data = X_test.data.astype(np.float64)
                y_test = self.process_y(y_test)
                X_test_2 = elem_wise_square(X_test)
            else:
                X_test_2 = None

            def callback(i, fm, hyper):
                pbar.update(1)
                if i % 5:
                    return False
                log_str = "alpha = {:.2f} ".format(hyper.alpha)
                log_str += "w0 = {:.2f} ".format(fm.w0)

                if do_test:
                    pred_this = self._predict_score_point(
                        fm, X_test, X_test_2)
                    val_results = self.measure_score(pred_this, y_test)
                    for key, metric in val_results.items():
                        log_str += " {}_this: {:.2f}".format(key, metric)

                pbar.set_description(log_str)
                return False

        try:
            self.fms_, self.hypers_ = \
                core.create_train_fm(self.rank, self.init_stdev, X, X_rel,
                                     y, self.random_seed, config, callback)
            return self
        finally:
            if pbar is not None:
                pbar.close()

    @classmethod
    def set_tasktype(cls, config_builder):
        config_builder.set_task_type(core.TaskType.REGRESSION)

    @classmethod
    def _predict_score_point(cls, fm, X, X_2):
        sqt = (fm.V ** 2).sum(axis=1)
        pred = ((X.dot(fm.V) ** 2).sum(axis=1) - X_2.dot(sqt)) / 2
        pred += X.dot(fm.w)
        pred += fm.w0
        return cls.process_score(pred)

    def _predict_score_mean(self, X):
        if not self.fms_:
            raise RuntimeError("No available sample.")
        X = sps.csr_matrix(X)
        X_2 = elem_wise_square(X)
        predictions = 0
        for fm_sample in self.fms_:
            predictions += self._predict_score_point(fm_sample, X, X_2)
        return predictions / len(self.fms_)

    def predict(self, X):
        return self._predict_score_mean(X)

    @classmethod
    def process_score(cls, y):
        return y

    @classmethod
    def process_y(cls, y):
        return y

    @classmethod
    def measure_score(cls, prediction, y):
        rmse = ((y - prediction) ** 2).mean() ** 0.5
        return {'rmse': rmse}

    def get_hyper_trace(self, dataframe=True):
        if dataframe:
            import pandas as pd
        columns = (
            ['alpha'] +
            ['mu_w[{}]'.format(g) for g in range(self.n_groups_)] +
            ['lambda_w[{}]'.format(g) for g in range(self.n_groups_)] +
            ['mu_V[{},{}]'.format(g, r) for g in range(self.n_groups_) for r in range(self.rank)] +
            ['lambda_V[{},{}]'.format(g, r) for g in range(
                self.n_groups_) for r in range(self.rank)]
        )

        res = []
        for hyper in self.hypers_:
            res.append(np.concatenate([
                [hyper.alpha], hyper.mu_w, hyper.lambda_w,
                hyper.mu_V.ravel(), hyper.lambda_V.ravel()
            ]))
        res = np.vstack(res)
        if dataframe:
            res = pd.DataFrame(res)
            res.columns = columns
            return res
        else:
            return [
                {key: sample[i] for i, key in enumerate(columns)}
                for sample in res
            ]


class MyFMClassifier(MyFMRegressor):
    @classmethod
    def set_tasktype(cls, config_builder):
        config_builder.set_task_type(core.TaskType.CLASSIFICATION)

    @classmethod
    def process_score(cls, score):
        return (1 + special.erf(score * np.sqrt(.5))) / 2

    @classmethod
    def process_y(cls, y):
        return y.astype(np.float64) * 2 - 1

    @classmethod
    def measure_score(cls, prediction, y):
        lp = np.log(prediction + 1e-15)
        l1mp = np.log(1 - prediction + 1e-15)
        gt = y > 0
        ll = - lp.dot(gt) - l1mp.dot(~gt)
        return {'ll': ll / prediction.shape[0]}

    def predict(self, X):
        return (self._predict_score_mean(X)) > 0.5

    def predict_proba(self, X):
        return self._predict_score_mean(X)
