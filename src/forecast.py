"""Time series (Week 11): split in time, naive baseline vs. a simple model.

Annual population data has no seasonal pattern, so "season" is reported as
absent rather than forced. The trend is separated with a rolling mean / Holt.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import Holt


def time_split(s: pd.Series, test_start: int) -> tuple[pd.Series, pd.Series]:
    """Split an annual series (index = year) at `test_start`. No shuffling."""
    s = s.dropna().sort_index()
    return s[s.index < test_start], s[s.index >= test_start]


def naive_drift(train: pd.Series, horizon: list[int]) -> pd.Series:
    """'Same as last time': last value + last observed annual change."""
    step = train.iloc[-1] - train.iloc[-2]
    last_year = train.index[-1]
    return pd.Series([train.iloc[-1] + step * (y - last_year) for y in horizon], index=horizon)


def holt_forecast(train: pd.Series, horizon: list[int], damped: bool = True) -> pd.Series:
    """Holt linear trend (optionally damped)."""
    model = Holt(train.values, damped_trend=damped, initialization_method="estimated").fit()
    pred = model.forecast(len(horizon))
    return pd.Series(np.asarray(pred), index=horizon)


def errors(actual: pd.Series, pred: pd.Series) -> dict[str, float]:
    a, p = actual.align(pred, join="inner")
    return {
        "MAE": float(np.mean(np.abs(a - p))),
        "MAPE_%": float(np.mean(np.abs((a - p) / a)) * 100),
        "n": int(len(a)),
    }


def evaluate(series: pd.Series, test_start: int = 2015,
             train_start: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit on train_start <= year < test_start, score on the rest. Returns (predictions, scores).

    `train_start` lets the user leave out early years: the 1970s and the 1990s contain
    swings (war, repatriation) that a smooth trend model cannot be expected to follow.
    """
    if train_start is not None:
        series = series[series.index >= train_start]
    train, test = time_split(series, test_start)
    horizon = list(test.index)
    preds = pd.DataFrame({
        "actual": test,
        "naive_drift": naive_drift(train, horizon),
        "holt_damped": holt_forecast(train, horizon),
    })
    scores = pd.DataFrame({
        m: errors(preds["actual"], preds[m]) for m in ("naive_drift", "holt_damped")
    }).T
    scores["beats_naive"] = scores["MAE"] < scores.loc["naive_drift", "MAE"]
    return preds, scores


def forecast_ahead(series: pd.Series, end_year: int, train_start: int | None = None) -> pd.DataFrame:
    """Forecast from the year after the last observation to `end_year`, fitting on all
    years from `train_start`. Same two models as the backtest (no probability band: the
    history has structural breaks, so a band from past errors would look more exact than it is).
    """
    s = series.dropna().sort_index()
    if train_start is not None:
        s = s[s.index >= train_start]
    horizon = list(range(int(s.index.max()) + 1, end_year + 1))
    if not horizon:
        return pd.DataFrame(columns=["naive_drift", "holt_damped"])
    return pd.DataFrame({"naive_drift": naive_drift(s, horizon), "holt_damped": holt_forecast(s, horizon)})


def trend_component(series: pd.Series, window: int = 5) -> pd.Series:
    """Centred rolling mean as a simple trend estimate."""
    return series.rolling(window, center=True).mean()
