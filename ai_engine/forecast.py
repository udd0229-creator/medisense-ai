"""
Demand forecasting for each medicine.

Method: Linear Regression on the last 90 days of daily sales with
  * a time index (captures rising / falling trend)
  * day-of-week dummy variables (captures weekly pattern)
The last 14 days are held out to measure Mean Absolute Error (MAE) against a
simple 7-day moving average. The better of the two methods is used for the
30-day forecast, so the system never does worse than the simple baseline.
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Sum
from sklearn.linear_model import LinearRegression

HISTORY_DAYS = 90
HOLDOUT_DAYS = 14


def daily_sales(medicine, days=HISTORY_DAYS, today=None):
    from inventory.models import Sale

    today = today or date.today()
    start = today - timedelta(days=days - 1)
    qs = (Sale.objects.filter(medicine=medicine, sale_date__gte=start, sale_date__lte=today)
          .values("sale_date").annotate(q=Sum("quantity")))
    idx = pd.date_range(start, today, freq="D")
    s = pd.Series(0.0, index=idx)
    for r in qs:
        s[pd.Timestamp(r["sale_date"])] = r["q"]
    return s


def _design(dates, t0):
    t = np.array([(d - t0).days for d in dates], dtype=float)
    dow = np.zeros((len(dates), 6))
    for i, d in enumerate(dates):
        if d.dayofweek < 6:
            dow[i, d.dayofweek] = 1
    return np.column_stack([t, dow])


def _fit_predict(train, future_index):
    t0 = train.index[0]
    model = LinearRegression().fit(_design(train.index, t0), train.values)
    return np.clip(model.predict(_design(future_index, t0)), 0, None)


def forecast_medicine(medicine, horizon=None, today=None):
    horizon = horizon or settings.MEDISENSE["FORECAST_DAYS"]
    today = today or date.today()
    hist = daily_sales(medicine, today=today)
    future_idx = pd.date_range(today + timedelta(days=1), periods=horizon, freq="D")

    active_days = int((hist > 0).sum())
    if active_days < 14:
        rate = float(hist.tail(30).mean())
        return {
            "history": hist, "forecast": pd.Series(rate, index=future_idx),
            "method": "Moving average (too little history)", "mae": None,
            "baseline_mae": None, "daily_mean": rate, "daily_std": float(hist.tail(60).std()),
            "total": rate * horizon,
        }

    train, test = hist.iloc[:-HOLDOUT_DAYS], hist.iloc[-HOLDOUT_DAYS:]
    lr_pred = _fit_predict(train, test.index)
    ma_pred = np.repeat(train.tail(7).mean(), HOLDOUT_DAYS)
    lr_mae = float(np.mean(np.abs(test.values - lr_pred)))
    ma_mae = float(np.mean(np.abs(test.values - ma_pred)))

    if lr_mae <= ma_mae:
        fc = _fit_predict(hist, future_idx)
        method = "Linear Regression (trend + weekday)"
    else:
        fc = np.repeat(hist.tail(7).mean(), horizon)
        method = "7-day moving average"
    fc = pd.Series(fc, index=future_idx)
    return {
        "history": hist, "forecast": fc, "method": method,
        "mae": round(min(lr_mae, ma_mae), 2), "lr_mae": round(lr_mae, 2),
        "baseline_mae": round(ma_mae, 2),
        "daily_mean": float(fc.mean()), "daily_std": float(hist.tail(60).std()),
        "total": float(fc.sum()),
    }
