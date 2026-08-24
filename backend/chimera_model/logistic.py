"""Small deterministic NumPy implementations of Logistic Regression and Platt scaling."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def sigmoid(values: np.ndarray | float) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    clipped = np.clip(array, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-clipped))


class LogisticFitError(ValueError):
    """Raised when logistic fitting receives invalid data."""


@dataclass
class LogisticRegression:
    l2: float = 1e-4
    max_iterations: int = 80
    tolerance: float = 1e-10
    coefficients: np.ndarray | None = None
    intercept: float = 0.0
    iterations: int = 0

    def fit(self, features: np.ndarray, labels: np.ndarray) -> "LogisticRegression":
        x = np.asarray(features, dtype=np.float64)
        y = np.asarray(labels, dtype=np.float64)
        if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.shape[0] or x.shape[0] == 0:
            raise LogisticFitError("features must be 2D and labels must match its non-empty row count")
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            raise LogisticFitError("features and labels must be finite")
        if not np.all(np.isin(y, [0.0, 1.0])):
            raise LogisticFitError("labels must be binary 0/1 values")
        if self.l2 < 0 or self.max_iterations <= 0:
            raise LogisticFitError("invalid logistic hyperparameters")

        augmented = np.column_stack((np.ones(x.shape[0], dtype=np.float64), x))
        parameters = np.zeros(augmented.shape[1], dtype=np.float64)
        regularizer = np.eye(augmented.shape[1], dtype=np.float64) * self.l2
        regularizer[0, 0] = 0.0
        for iteration in range(1, self.max_iterations + 1):
            probabilities = sigmoid(augmented @ parameters)
            gradient = (augmented.T @ (probabilities - y)) / x.shape[0] + regularizer @ parameters
            curvature = probabilities * (1.0 - probabilities)
            hessian = (augmented.T @ (augmented * curvature[:, None])) / x.shape[0] + regularizer
            try:
                step = np.linalg.solve(hessian, gradient)
            except np.linalg.LinAlgError:
                step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
            parameters -= step
            if float(np.max(np.abs(step))) <= self.tolerance:
                self.iterations = iteration
                break
        else:
            self.iterations = self.max_iterations
        self.intercept = float(parameters[0])
        self.coefficients = parameters[1:].copy()
        return self

    def predict_logit(self, features: np.ndarray) -> np.ndarray:
        if self.coefficients is None:
            raise LogisticFitError("model has not been fitted")
        x = np.asarray(features, dtype=np.float64)
        if x.ndim != 2 or x.shape[1] != self.coefficients.shape[0]:
            raise LogisticFitError("feature matrix does not match fitted model")
        return self.intercept + x @ self.coefficients

    def predict_probability(self, features: np.ndarray) -> np.ndarray:
        return sigmoid(self.predict_logit(features))


@dataclass
class PlattCalibrator:
    """Fit sigmoid(a * base_logit + b) on the validation/calibration split."""

    l2: float = 1e-6
    max_iterations: int = 80
    a: float = 1.0
    b: float = 0.0
    iterations: int = 0

    def fit(self, logits: np.ndarray, labels: np.ndarray) -> "PlattCalibrator":
        x = np.asarray(logits, dtype=np.float64).reshape(-1, 1)
        y = np.asarray(labels, dtype=np.float64)
        if x.shape[0] == 0 or y.ndim != 1 or x.shape[0] != y.shape[0]:
            raise LogisticFitError("calibration logits and labels must have matching non-empty lengths")
        helper = LogisticRegression(l2=self.l2, max_iterations=self.max_iterations)
        helper.fit(x, y)
        self.a = float(helper.coefficients[0])
        self.b = float(helper.intercept)
        self.iterations = helper.iterations
        return self

    def transform(self, logits: np.ndarray) -> np.ndarray:
        return sigmoid(self.a * np.asarray(logits, dtype=np.float64) + self.b)
