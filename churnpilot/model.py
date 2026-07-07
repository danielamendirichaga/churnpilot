"""Model training — the bounded menu, in a leakage-safe pipeline, with a baseline floor.

Mirrors the author's established practice stack (see ``local-notes/``): a leakage-safe
``ColumnTransformer`` fit on train only, L1 ``LogisticRegressionCV``, ccp-pruned trees, and
XGBoost tuned by ``GridSearchCV`` + ``StratifiedKFold`` — plus optional SMOTE (``imblearn``,
train-folds only) and **isotonic calibration** (the piece the course relied on but never did).

Menu: ``logistic`` (L1) · ``tree`` (pruned) · ``rf`` (bagging) · ``xgboost`` (boosting).
Default = fast fixed hyperparameters; ``--tune`` runs the course's search. A majority-class
baseline floor is always reported. Emits a :class:`ModelCard` artifact with lineage.

This module is allowed to import scikit-learn / xgboost (the tested metric core is not).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline as SkPipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import metrics as m
from .artifacts import ArtifactBase, content_hash
from .config import ChurnConfig

MODELS = ("logistic", "tree", "rf", "xgboost")
_HP_KEYS = {
    "logistic": ["C", "solver", "l1_ratio"],
    "rf": ["n_estimators", "min_samples_leaf"],
    "xgboost": ["n_estimators", "learning_rate", "max_depth", "subsample", "colsample_bytree"],
}


class ModelError(ValueError):
    """Raised for an unknown model or an unsupported option combination."""


class ModelCard(ArtifactBase):
    artifact: Literal["model-card"] = "model-card"
    model_family: str
    tuned: bool
    smote: bool
    calibrated: bool
    n_features: int
    features: list[str]
    hyperparams: dict
    train_metrics: dict
    baseline_metrics: dict


def feature_columns(df: pd.DataFrame, config: ChurnConfig) -> tuple[list[str], list[str]]:
    """Split the configured features into (numeric, categorical), excluding id/date/target/value."""
    cols = config.columns
    reserved = {cols.id_col, cols.date_col, cols.target_col, cols.value_col}
    feats = (
        [c for c in df.columns if c not in reserved]
        if cols.features == "auto"
        else list(cols.features)
    )
    numeric = [
        c
        for c in feats
        if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])
    ]
    categorical = [c for c in feats if c not in numeric]
    return numeric, categorical


def _preprocessor(numeric: list[str], categorical: list[str], model: str) -> ColumnTransformer:
    """Leakage-safe preprocessing (fit on train only), tailored per model family."""
    if model == "xgboost":
        num = "passthrough"  # xgboost handles NaN natively (sparsity-aware splits)
        cat = SkPipeline(
            [
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]
        )
    elif model == "logistic":
        num = SkPipeline(
            [("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
        )
        cat = SkPipeline(
            [
                ("impute", SimpleImputer(strategy="most_frequent")),
                (
                    "onehot",
                    OneHotEncoder(drop="first", handle_unknown="ignore", sparse_output=False),
                ),
            ]
        )
    else:  # tree, rf
        num = SkPipeline([("impute", SimpleImputer(strategy="median"))])
        cat = SkPipeline(
            [
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]
        )
    return ColumnTransformer(
        [("num", num, numeric), ("cat", cat, categorical)],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def _estimator(model: str, seed: int, tune: bool):
    if model == "logistic":
        from sklearn.linear_model import LogisticRegression, LogisticRegressionCV

        if tune:  # the course's L1 LogisticRegressionCV (l1_ratios=[1.0] = pure L1)
            return LogisticRegressionCV(
                Cs=np.logspace(-3, 3, 7),
                cv=5,
                scoring="neg_log_loss",
                solver="saga",
                l1_ratios=[1.0],
                max_iter=3000,
                refit=True,
                random_state=seed,
                n_jobs=-1,
            )
        return LogisticRegression(
            C=1.0, solver="saga", l1_ratio=1.0, max_iter=2000, random_state=seed
        )
    if model == "rf":
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(
            n_estimators=300, min_samples_leaf=20, random_state=seed, n_jobs=-1
        )
    if model == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=300,
            learning_rate=0.1,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            random_state=seed,
            n_jobs=-1,
            verbosity=0,
        )
    raise ModelError(f"unknown model {model!r} (use {' | '.join(MODELS)})")


def _assemble(pre: ColumnTransformer, est, smote: bool, seed: int):
    if smote:
        from imblearn.over_sampling import SMOTE
        from imblearn.pipeline import Pipeline as ImbPipeline

        return ImbPipeline(
            [("preprocess", pre), ("smote", SMOTE(random_state=seed)), ("model", est)]
        )
    return SkPipeline([("preprocess", pre), ("model", est)])


def _fit_tree(pre: ColumnTransformer, X: pd.DataFrame, y: np.ndarray, seed: int, tune: bool):
    """Decision tree; ``--tune`` = cost-complexity pruning (the course's method)."""
    from sklearn.model_selection import cross_val_score
    from sklearn.tree import DecisionTreeClassifier

    xt = pre.fit_transform(X, y)
    if tune:
        alphas = (
            DecisionTreeClassifier(random_state=seed).cost_complexity_pruning_path(xt, y).ccp_alphas
        )
        alphas = np.unique(alphas[alphas >= 0])
        if len(alphas) > 12:
            alphas = alphas[np.linspace(0, len(alphas) - 1, 12).astype(int)]
        best_a, best_s = 0.0, -np.inf
        for a in alphas:
            s = cross_val_score(
                DecisionTreeClassifier(random_state=seed, ccp_alpha=a),
                xt,
                y,
                scoring="neg_log_loss",
                cv=3,
            ).mean()
            if s > best_s:
                best_s, best_a = s, float(a)
        tree = DecisionTreeClassifier(random_state=seed, ccp_alpha=best_a)
        hp = {"ccp_alpha": best_a}
    else:
        tree = DecisionTreeClassifier(max_depth=6, min_samples_leaf=50, random_state=seed)
        hp = {"max_depth": 6, "min_samples_leaf": 50}
    tree.fit(xt, y)
    return SkPipeline([("preprocess", pre), ("model", tree)]), hp


def _tune_xgb(pre: ColumnTransformer, X: pd.DataFrame, y: np.ndarray, seed: int):
    """XGBoost via GridSearchCV + StratifiedKFold (the course's approach, smaller grid)."""
    from sklearn.model_selection import GridSearchCV, StratifiedKFold
    from xgboost import XGBClassifier

    pipe = SkPipeline(
        [
            ("preprocess", pre),
            (
                "model",
                XGBClassifier(
                    objective="binary:logistic",
                    eval_metric="logloss",
                    tree_method="hist",
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=seed,
                    n_jobs=1,
                    verbosity=0,
                ),
            ),
        ]
    )
    grid = {
        "model__learning_rate": [0.01, 0.03, 0.1],
        "model__n_estimators": [200, 400],
        "model__max_depth": [3, 4],
    }
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=seed)
    search = GridSearchCV(pipe, grid, scoring="neg_log_loss", cv=cv, n_jobs=-1)
    search.fit(X, y)
    hp = {k.replace("model__", ""): v for k, v in search.best_params_.items()}
    return search.best_estimator_, hp


def train_model(
    train_df: pd.DataFrame,
    config: ChurnConfig,
    model: str = "logistic",
    smote: bool = False,
    calibrate: bool = False,
    tune: bool = False,
    seed: int = 42,
) -> tuple[object, ModelCard]:
    """Fit ``model`` on ``train_df`` and return (fitted estimator, ModelCard)."""
    if model not in MODELS:
        raise ModelError(f"unknown model {model!r} (use {' | '.join(MODELS)})")
    numeric, categorical = feature_columns(train_df, config)
    cols = config.columns
    X = train_df[numeric + categorical]
    y = (train_df[cols.target_col] == cols.positive_value).astype(int).to_numpy()
    pre = _preprocessor(numeric, categorical, model)

    if model == "tree":
        if smote or calibrate:
            raise ModelError("smote/calibrate are not supported with the pruned 'tree' model")
        estimator, hyperparams = _fit_tree(pre, X, y, seed, tune)
    elif model == "xgboost" and tune:
        if smote or calibrate:
            raise ModelError("smote/calibrate are not supported with --tune xgboost")
        estimator, hyperparams = _tune_xgb(pre, X, y, seed)
    else:
        est = _estimator(model, seed, tune)
        hyperparams = {k: v for k, v in est.get_params().items() if k in _HP_KEYS.get(model, [])}
        pipe = _assemble(pre, est, smote, seed)
        if calibrate:
            from sklearn.calibration import CalibratedClassifierCV

            estimator = CalibratedClassifierCV(pipe, method="isotonic", cv=3)
            estimator.fit(X, y)
        else:
            pipe.fit(X, y)
            estimator = pipe

    proba = estimator.predict_proba(X)[:, 1]
    train_metrics = {
        "auc": m.roc_auc(y, proba),
        "ks": m.ks_table(y, proba).ks,
        "top_decile_lift": m.top_decile_lift(y, proba),
    }

    from sklearn.dummy import DummyClassifier

    base = DummyClassifier(strategy="prior").fit(X, y)
    baseline_metrics = {"auc": m.roc_auc(y, base.predict_proba(X)[:, 1])}

    card = ModelCard(
        model_family=model,
        tuned=tune,
        smote=smote,
        calibrated=calibrate,
        n_features=len(numeric) + len(categorical),
        features=numeric + categorical,
        hyperparams=hyperparams,
        train_metrics=train_metrics,
        baseline_metrics=baseline_metrics,
        parent_sha256=content_hash(train_df),
    )
    return estimator, card


def save_model(estimator: object, path: str | Path) -> None:
    joblib.dump(estimator, path)


def load_model(path: str | Path) -> object:
    return joblib.load(path)
