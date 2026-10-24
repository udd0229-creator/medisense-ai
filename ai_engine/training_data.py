"""
Generates the training dataset for the expiry-risk model.

A real pharmacy rarely has thousands of labelled historical batches, so the
dataset is SIMULATED from realistic pharmacy patterns:

  * each medicine has a daily demand rate (log-normal: most items sell a few
    units a day, a few sell 20-30 a day)
  * the rate observed in the last 30 days is a noisy estimate of the true rate
  * future demand drifts up or down (trend + random change)
  * FEFO: a batch only starts selling after the batches ahead of it are used

Label (expired = 1) is decided by simulating sales day by day until expiry:
if at least 5% of the batch is still unsold on the expiry date, the batch is
counted as "expired / at risk".
"""
import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS, derive


def simulate_dataset(n=6000, seed=42):
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        true_rate = float(rng.lognormal(mean=np.log(3.0), sigma=0.9))
        days_to_expiry = int(rng.integers(5, 721))
        quantity = int(np.clip(true_rate * rng.uniform(5, 400), 5, 3000))
        qty_ahead = 0 if rng.random() < 0.5 else int(true_rate * rng.uniform(0, 120))
        unit_price = float(np.round(rng.lognormal(np.log(45), 0.8), 2))

        # What the pharmacy observes: last 30 and last 7 days of sales
        observed_30 = rng.poisson(true_rate * 30) / 30
        observed_7 = rng.poisson(true_rate * 7) / 7
        trend = (observed_7 / observed_30) if observed_30 > 0 else 1.0

        # What actually happens in future (unknown at prediction time)
        drift = float(rng.lognormal(0, 0.35)) * (min(trend, 3) ** 0.3)
        future_rate = true_rate * drift
        sold_until_expiry = rng.poisson(future_rate * days_to_expiry)
        sold_from_batch = max(0, min(quantity, sold_until_expiry - qty_ahead))
        unsold = quantity - sold_from_batch
        expired = int(unsold >= max(1, 0.05 * quantity))

        feats = derive(days_to_expiry, quantity, qty_ahead, observed_30, min(trend, 5.0),
                       unit_price)
        feats["expired"] = expired
        rows.append(feats)
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS + ["expired"])
