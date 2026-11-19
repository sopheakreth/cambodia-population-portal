"""Rare-event task (Weeks 8, 10, 13): which communes are urban (sangkat)?

One imblearn Pipeline holds every fitted step, so scaling, encoding and SMOTE
are re-fitted inside each CV fold (no leakage). The test set is used once.

NOTE on leakage: `district_type` (Krong / Khan / Srok) almost decides the
answer, because Khan and Krong districts contain mostly sangkat. Train the
model with and without it and discuss the difference in the notebook.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, confusion_matrix,
                             precision_score, recall_score, f1_score)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.config import SEED
from src.pipeline import COMMUNE_DB_FEATURES

NUMERIC = ["villages", "communes_in_district"]
CATEGORICAL = ["pro_code"]          # add "district_type" to see the leakage effect


def prepare(com: pd.DataFrame, use_district_type: bool = False, use_db: bool = False):
    """Return X, y, categorical columns and numeric columns.

    `use_db` adds the 2011 commune-database features (electricity, households, land, rice);
    communes without a 2011 row are filled with the median inside the CV pipeline.
    """
    df = com.dropna(subset=["is_sangkat"]).copy()
    cats = CATEGORICAL + (["district_type"] if use_district_type else [])
    nums = NUMERIC + ([c for c in COMMUNE_DB_FEATURES if c in df] if use_db else [])
    X = df[nums + cats].copy()
    X["pro_code"] = X["pro_code"].astype(str)
    y = df["is_sangkat"].astype(int)
    return X, y, cats, nums


def build_pipeline(cats: list[str], use_smote: bool = True, nums: list[str] | None = None) -> Pipeline:
    pre = ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), nums or NUMERIC),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5), cats),
    ])
    steps = [("prep", pre)]
    if use_smote:
        steps.append(("smote", SMOTE(random_state=SEED)))
    steps.append(("clf", LogisticRegression(max_iter=2000, class_weight=None, random_state=SEED)))
    return Pipeline(steps)


def cost_threshold(y_true, proba, cost_fn: float = 3.0, cost_fp: float = 1.0):
    """Pick the probability cut-off with the lowest total cost."""
    grid = np.round(np.arange(0.05, 0.96, 0.01), 2)
    costs = []
    for t in grid:
        pred = (proba >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
        costs.append(cost_fn * fn + cost_fp * fp)
    best = int(np.argmin(costs))
    return float(grid[best]), pd.DataFrame({"threshold": grid, "cost": costs})


def metrics_at(y_true, proba, threshold: float) -> dict:
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "threshold": threshold,
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }


def run(com: pd.DataFrame, use_district_type: bool = False, cost_fn: float = 3.0,
        cost_fp: float = 1.0, test_size: float = 0.25, use_db: bool = False) -> dict:
    """Full Week-10 workflow. Returns everything the app and notebook display."""
    X, y, cats, nums = prepare(com, use_district_type, use_db)
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=SEED)
    pipe = build_pipeline(cats, nums=nums)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    oof = cross_val_predict(pipe, X_tr, y_tr, cv=cv, method="predict_proba")[:, 1]
    thr, cost_curve = cost_threshold(y_tr, oof, cost_fn, cost_fp)

    pipe.fit(X_tr, y_tr)
    test_proba = pipe.predict_proba(X_te)[:, 1]          # the one and only use of the test set
    return {
        "base_rate": float(y.mean()),
        "n": int(len(y)),
        "threshold": thr,
        "cost_curve": cost_curve,
        "cv": metrics_at(y_tr, oof, thr),
        "cv_pr_auc": float(average_precision_score(y_tr, oof)),
        "test": metrics_at(y_te, test_proba, thr),
        "test_pr_auc": float(average_precision_score(y_te, test_proba)),
        "y_test": y_te.values, "proba_test": test_proba,
        "pipeline": pipe,
    }


def pca_index(df: pd.DataFrame, cols: list[str], n: int = 1) -> tuple[pd.Series, float]:
    """Week 8: first principal component of standardised indicators + variance kept."""
    Z = StandardScaler().fit_transform(df[cols].dropna())
    p = PCA(n_components=n, random_state=SEED).fit(Z)
    idx = pd.Series(p.transform(Z)[:, 0], index=df[cols].dropna().index, name="pca_index")
    return idx, float(p.explained_variance_ratio_[:n].sum())
