"""
  Copyright (c) 2016- by Dietmar W Weiss

  This is free software; you can redistribute it and/or modify it
  under the terms of the GNU Lesser General Public License as
  published by the Free Software Foundation; either version 3.0 of
  the License, or (at your option) any later version.

  This software is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
  Lesser General Public License for more details.

  You should have received a copy of the GNU Lesser General Public
  License along with this software; if not, write to the Free
  Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
  02110-1301 USA, or see the FSF site: http://www.fsf.org.

  Version:
      2018-05-24 DWW
"""

import sys
import numpy as np
import scipy.optimize
from Model import Model
#############################################
try:
    import krza_ga
except ImportError:
    print('??? module krza_ga not imported')
HAS_KRZA_GA = 'krza_ga' in sys.modules
#############################################


class LightGray(Model):
    """
    Light gray box model y=f(x, C)

    Extends the functionality of class Model by a train() method which fits
    the theoretical submodel f(x) with constant fit parameters 'C'

    Notes:
        - C0 (int, 1D or 2D array_like of float) is principally a mandatory
          argument. Alternatively, self.f() can return this value if called
          as self.f(None). In this case an 'C0' argument is not necessary
        - The number of outputs y.shape[1] is limited to 1, see self._nMaxOut

    Examples:
        def function(x, *args):
            c0, c1, c2, c3 = args if len(args) > 0 else np.ones(4)
            return [c0 + c1 * (c2 * np.sin(x[0]) + c3 * (x[1] - 1)**2)]

        def function2(x, *args):
            if x is None:
                return [1, 1, 1, 1]                    # initial fit parameters
            c0, c1, c2, c3 = args if len(args) > 0 else np.ones(4)
            return [c0 + c1 * (c2 * np.sin(x[0]) + c3 * (x[1] - 1)**2)]

        def method(self, x, *args):
            c0, c1, c2, c3 = args if len(args) > 0 else np.ones(4)
            return [c0 + c1 * (c2 * np.sin(x[0]) + c3 * (x[1] - 1)**2)]

        ### compact form:
        y = LightGray(function)(X=X, Y=Y, x=x, C0=4, trainers='lm')

        ### expanded form:
        # assign theoretical submodel as function or method ('self'-attribute)
        model = LightGray(function)  or
        model = LightGray(method)

        # (X, Y): training data
        X = [(1,2), (2,3), (4,5), (6,7), (7,8)]
        Y = [(1,), (2,), (3,), (4,), (5,)]     # alternatively: [1, 2, 3, 4, 5]

        # x: test data
        x = [(1, 4), (6, 6)]

        # before training, result of theoretical submodel f(x) is returned
        y = model(x=x)                           # predict with white box model

        # train light gray with data (X, Y), C0 has 9 random initial fit params
        model(X=X, Y=Y, C0=rand(9, [[-10, 10]] * 4))                    # train

        # after model is trained, it keeps its weights for further preddictions
        y = model(x=x)                      # predict with light gray box model

        # alternatively: combined train and pred, single initial fit par set C0
        y = model(X=X, Y=Y, C0=4, x=x)                      # train and predict
    """

    def __init__(self, f, identifier='LightGray'):
        """
        Args:
            f (method or function):
                theoretical submodel f(self, x) or f(x) for single data point

            identifier (string, optional):
                object identifier
        """
        super().__init__(identifier=identifier, f=f)

        self._nMaxOut = 1        # max nOut is '1' due to implementation limits

        # populate 'validTrainers' list
        self.scipyCurveFitters = ['trf',  # trust region reflective,constrained
                                  'lm',    # Levenberg-Marquardt, unconstrained
                                  'dogbox'                        # constrained
                                  ]
        self.scipyMinimizers = ['Nelder-Mead',
                                'Powell',
                                'CG',
                                'BFGS',
                                # 'Newton-CG',              # requires Jacobian
                                'L-BFGS-B',
                                'TNC',
                                'COBYLA',
                                'SLSQP',
                                # 'dogleg',                 # requires Jacobian
                                # 'trust-ncg',              # requires Jacobian
                                'basinhopping',        # global (brute) optimum
                                'differential_evolution',      # GLOBAL optimum
                                ]
        self.scipyEquationMinimizers = ['least_squares',          # constrained
                                        'leastsq',  # same as curve_fit with lm
                                        ]
        #############################################
        if HAS_KRZA_GA:
            self.geneticMinimizers = ['krza_ga']      # Krzystof's GA optimizer
        else:
            self.geneticMinimizers = []
        #############################################
        self.validTrainers = self.scipyCurveFitters + self.scipyMinimizers + \
            self.scipyEquationMinimizers + self.geneticMinimizers

    # function wrapper for scipy curve_fit
    def f_curve_fit(self, xT, *args, **kwargs):
        # xT.shape:(nInp, nPoint), xT.T.shape:(nPoint,nInp)
        return Model.predict(self, xT.T, *args,
                             **self.kwargsDel(kwargs, 'x')).ravel()

    # function wrapper for scipy minimize
    def meanSquareErrror(self, weights, **kwargs):
        y = Model.predict(self, self.X, *weights,
                          **self.kwargsDel(kwargs, 'x'))
        return np.mean((y - self.Y)**2)

    # function wrapper for scipy least_square and leastsq
    def difference(self, weights, **kwargs):
        return (Model.predict(self, self.X, *weights,
                              **self.kwargsDel(kwargs, 'x')) -
                self.Y).ravel()

    def optimize(self, trainer, c0, **kwargs):
        """
        Minimizes least squares: sum(self.f(self.X)-self.Y)^2)/X.size
            for SINGLE initial fit param set
        Updates self.ready and self.weights according to success of optimizer

        Args:
            trainer (str):
                type of optimizer for minimizing objective function

            c0 (1D array_like of float):
                initial guess of fit parameter set

            kwargs (dict, optional):
                keyword arguments:

                bounds (2-tuple of float or 2-tuple of 1D array_like of float):
                    list of pairs (xMin, xMax) limiting x

                ... specific optimizer options

        Returns:
            (dict {str: float or int or str}):
                results, see Model.train()

        """
        results = self.initResults('trainer', trainer)
        self.weights = None                       # required by Model.predict()
        self.ready = True                         # required by Model.predict()

        # scipy's curve_fit can probably be replaced by least_sqaures & lestsq
        if trainer in self.scipyCurveFitters:
            bounds = kwargs.get('bounds', (-np.inf, np.inf))
            if trainer == 'lm':
                bounds = (-np.inf, +np.inf)
            try:
                popt, pcov = scipy.optimize.curve_fit(
                    f=self.f_curve_fit,
                    xdata=self.X.T,                            # (nInp, nPoint)
                    ydata=self.Y.ravel(),                           # (nPoint,)
                    method=trainer, p0=c0,                            # (nTun,)
                    sigma=None, absolute_sigma=False, bounds=bounds)
                results['weights'] = np.atleast_1d(popt)
                results['iterations'] = -1
                results['evaluations'] = -1
            except RuntimeError:
                self.write('\n??? ', trainer, ': ', 'maxiter exceeded')

        elif trainer in self.scipyMinimizers:
            if trainer.startswith('bas'):
                nItMax = kwargs.get('nItMax', 100)

                res = scipy.optimize.basinhopping(
                    func=self.meanSquareErrror, x0=c0, niter=nItMax,
                    T=1.0,
                    stepsize=0.5, minimizer_kwargs=None,
                    take_step=None, accept_test=None, callback=None,
                    interval=50, disp=False, niter_success=None)

                if 'success' in res.message[0]:
                    results['weights'] = np.atleast_1d(res.x)
                    results['iterations'] = res.nit
                    results['evaluations'] = res.nfev
                else:
                    self.write('\n??? ', trainer, ': ', res.message)

            elif trainer.startswith('dif'):
                nItMax = kwargs.get('nItMax', None)

                res = scipy.optimize.differential_evolution(
                    func=self.meanSquareErrror, bounds=[[-10, 10]]*c0.size,
                    strategy='best1bin', maxiter=nItMax, popsize=15,
                    tol=0.01, mutation=(0.5, 1), recombination=0.7,
                    seed=None, disp=False, polish=True,
                    init='latinhypercube')

                if res.success:
                    results['weights'] = np.atleast_1d(res.x)
                    results['iterations'] = res.nit
                    results['evaluations'] = res.nfev
                else:
                    self.write('\n??? ', trainer, ': ', res.message)
            else:
                validKeys = ['nItMax', 'adaptive', 'goal']
                kw = {}
                if any(k in kwargs for k in validKeys):
                    kw['options'] = {}
                    kw['options']['maxiter'] = kwargs.get('nItMax', None)
                    if trainer == 'Nelder-Mead':
                        kw['options']['adaptive'] = kwargs.get('adaptive',
                                                               False)
                        kw['options']['xatol'] = kwargs.get('goal', 1e-4)

                try:
                    res = scipy.optimize.minimize(
                        fun=self.meanSquareErrror, x0=c0, method=trainer, **kw)
                    if res.success:
                        results['weights'] = np.atleast_1d(res.x)
                        results['iterations'] = res.nit \
                            if trainer != 'COBYLA' else -1
                        results['evaluations'] = res.nfev
                    else:
                        self.write('\n??? ', trainer, ': ', res.message)
                except scipy.optimize.OptimizeWarning:
                    results['weights'] = None
                    self.write('\n??? ', trainer, ': ', res.message)
                    print(kw)
                    print(kwargs)
                    assert 0

        elif trainer in self.scipyEquationMinimizers:
            if trainer.startswith('leastsq'):
                x, cov_x, infodict, mesg, ier = scipy.optimize.leastsq(
                    self.difference, c0, full_output=True)
                if ier in [1, 2, 3, 4]:
                    results['weights'] = np.atleast_1d(x)
                    results['iterations'] = -1
                    results['evaluations'] = infodict['nfev']
                else:
                    self.write('\n??? ', trainer, ': ', mesg)

            elif trainer == 'least_squares':
                res = scipy.optimize.least_squares(self.difference, c0)
                if res.success:
                    results['weights'] = np.atleast_1d(res.x)
                    results['iterations'] = -1
                    results['evaluations'] = res.nfev
                else:
                    self.write('\n??? ', trainer, ': ', res.message)

        elif trainer in self.geneticMinimizers:
            if HAS_KRZA_GA and trainer == 'krza_ga':
                #############################################
                validKeys = ['tol', 'options']  # see scipy's minimize
                kw = {k: kwargs[k] for k in validKeys if k in kwargs}
                res = krza_ga.minimize(
                    fun=self.meanSquareErrror, x0=c0, method=trainer, **kw)
                #############################################
                if res.success:
                    results['weights'] = np.atleast_1d(res.x)
                    results['iterations'] = -1  # res.nit
                    results['evaluations'] = res.nfev
                else:
                    self.write('\n??? ', trainer, ': ', res.message)
        else:
            assert 0, '??? LightGray, invalid trainer: ' + str(trainer)

        self.weights = results['weights']
        self.ready = self.weights is not None

        return results

    def train(self, X, Y, **kwargs):
        """
        Trains model, stores X and Y as self.X and self.Y, and stores result
        of best training trial as self.best.
        Fitted coefficients are stored as self._weights

        Args:
            X (2D or 1D array_like of float):
                training input, shape: (nPoint, nInp) or shape: (nPoint,)

            Y (2D or 1D array_like of float):
                training target, shape: (nPoint, nOut) or shape: (nPoint,)

            C0 (2D or 1D array_like of float, optional):
                sequence of initial guess of the tuning parameter sets,
                If missing, then initial values will be all 1
                C0.shape[1] is the number of fit parameters
                [IS PASSED IN KWARGS to be compatible to parallel.py]

            kwargs (dict, optional):
                keyword arguments:

                trainers (string or 1D array_like of string):
                    optimizer method of
                    - scipy.optimizer.curve_fit or
                    - scipy.optimizer.minimize or
                    - genetic algorithm
                    see: self.validTrainers
                    default: 'trf'

                bounds (2-tuple of float or 2-tuple of 1D array_like of float):
                    list of pairs (xMin, xMax) limiting x

        Returns:
            (dict {str: float or int or str}):
                results, see Model.train()

        Note:
            If argument 'C0' is not given, self.f(None) must return the number
            of tuning parameters or an array of initial tuning parameter sets
        """
        self.X = X if X is not None and Y is not None else self.X
        self.Y = Y if X is not None and Y is not None else self.Y

        # get series of initial fit par sets from 'C0', 'CInit' or self.f(None)
        C0 = self.kwargsGet(kwargs, ('C0', 'CInit'))
        if C0 is None:
            C0 = self.f(None)
        if isinstance(C0, int):
            C0 = np.ones(C0)
        C0 = np.atleast_2d(C0)                          # shape: (nTrial, nTun)

        # get trainers from kwargs
        trainers = self.kwargsGet(kwargs, ('trainers', 'trainer', 'train'))
        if trainers is None:
            trainers = self.validTrainers[0]
        trainers = np.atleast_1d(trainers)
        if trainers[0].lower() == 'all':
            trainers = self.validTrainers
        if any([tr not in self.validTrainers for tr in trainers]):
            trainers = self.validTrainers[0]
            self.write('??? invalid trainer found, correct to: ', trainers)

        # set detailed print (only if not silent)
        printDetails = kwargs.get('detailed', False)

        # loops over all trainers
        self.write('    fit (', None)
        self.best = self.initResults()
        for trainer in trainers:
            self.write(trainer, ', ' if trainer != trainers[-1] else '', None)

            # tries all initial fit parameter sets
            for iTrial, c0 in enumerate(C0):
                if printDetails:
                    if iTrial == 0:
                        self.write()
                    self.write('        C0: ', str(np.round(c0, 2)), None)

                results = self.optimize(
                    trainer, c0, **self.kwargsDel(kwargs, ('trainer', 'c0')))

                if results['weights'] is not None:
                    self.weights = results['weights']     # for Model.predict()
                    err = self.error(X=X, Y=Y, silent=True)
                    self.weights = None             # back to None for training
                    if self.best['L2'] > err['L2']:
                        self.best.update(results)
                        self.best.update(err)
                        self.best['iTrial'] = iTrial
                        if printDetails:
                            self.write(' +++', None)
                    if printDetails:
                        self.write(' L2: ', round(err['L2'], 6))
                else:
                    self.write(' ---')

        self.weights = self.best['weights']
        self.ready = self.weights is not None

        self.write('), w: ', None)
        self.write(str(np.round(self.weights, 4)))
        self.write('    best trainer: ', "'", self.best['trainer'], "'", None)
        self.write(', ', None)
        for key in ['L2', 'abs']:
            if key in self.best:
                self.write(key, ': ', float(str(round(self.best[key], 4))),
                           ', ', None)
        self.write('\n', '    ', None)
        for key in ['iTrial', 'iterations', 'evaluations']:
            if key in self.best:
                self.write(key, ': ', self.best[key], ', ', None)
        self.write()

        return self.best

    def predict(self, x, *args, **kwargs):
        """
        Executes Model, stores input x as self.x and output as self.y

        Args:
            x (2D or 1D array_like of float):
                prediction input, shape: (nPoint, nInp) or shape: (nInp)

            args(list arguments, optional):
                constant fit parameters if self._weights is None

            kwargs (dict, optional):
                keyword arguments

        Returns:
            (2D array of float):
                prediction output, shape: (nPoint, nOut)
        """
        args = self._weights if self._weights is not None else args
        return Model.predict(self, x, *args, **self.kwargsDel(kwargs, 'x'))


# Examples ####################################################################

if __name__ == '__main__':
    ALL = 0

    from plotArrays import plot_X_Y_Yref
    import Model as md
    from White import White

    def f(self, x, *args, **kwargs):
        """
        Theoretical submodel for single data point

        Aargs:
            x (1D array_like of float):
                input

            args (argument list):
                fit parameters as positional arguments

            kwargs (dict, optional):
                keyword arguments {str: float or int or str}
        """
        p = args if len(args) > 0 else np.ones(4)
        y0 = p[0] + p[1] * np.sin(p[2] * x[0]) + p[3] * (x[1] - 1.5)**2
        return [y0]

    s = 'Creates exact output y_exa(X), add noise, target is Y(X)'
    print('-' * len(s) + '\n' + s + '\n' + '-' * len(s))

    noise_abs = 0.25
    noise_rel = 10e-2
    X = md.grid(8, [-1, 8], [0, 3])
    y_exa = White(f)(x=X, silent=True)
    Y = md.noise(y_exa, absolute=noise_abs, relative=noise_rel)
    plot_X_Y_Yref(X, Y, y_exa, ['X', 'Y_{nse}', 'y_{exa}'])

    if 1 or ALL:
        s = 'Fits model, compare: y(X) vs y_exa(X)'
        print('-' * len(s) + '\n' + s + '\n' + '-' * len(s))

        # train with 9 random initial tuning parameter sets
        C0 = md.rand(16, [0, 2], [0, 2], [0, 2], [0, 2])
        model = LightGray(f)

#############################################
        if HAS_KRZA_GA:
            trainer = 'krza_ga'
        else:
            trainer = ['all']
            # ['leastsq', 'least_squares', 'differential_evolution']
        y = model(X=X, Y=Y, C0=C0, x=X, trainer=trainer, detailed=True,
                  nItMax=5000)
#############################################

        plot_X_Y_Yref(X, y, y_exa, ['X', 'y', 'y_{exa}'])
        if 0:
            print('best:', model.best)
            df = model.xy2frame()
            print('=== df:\n', df)

    if 0 or ALL:
        def f2(self, x, *args, **kwargs):
            if x is None:
                return 4
            p = args if len(args) > 0 else np.ones(4)
            y0 = p[0] + p[1] * np.sin(p[2] * x[0]) + p[3] * (x[1] - 1.5)**2
            return [y0]

        # train with single initial tuning parameter set, nTun from f2(None)
        y = LightGray(f2)(X=X, Y=Y, x=X, silent=not True, trainer='all')
