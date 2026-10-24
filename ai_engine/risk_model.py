"""
Expiry Risk Prediction (Random Forest classifier).

train_model()   -> trains on the simulated dataset, compares with Logistic
                   Regression and Decision Tree, saves the model and metrics.
predict_batches() -> risk probability, level, expected loss and recommended
                   action for every batch in stock.
"""
import json
from datetime import date, datetime

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from .features import FEATURE_COLUMNS, batch_features
from .training_data import simulate_dataset

MODEL_FILE = "expiry_risk_rf.joblib"
METRICS_FILE = "expiry_risk_metrics.json"
_cache = {"model": None, "mtime": None}


def _paths():
    d = settings.ML_MODEL_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d / MODEL_FILE, d / METRICS_FILE


def _scores(y_true, y_pred, y_prob):
    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred), 4),
        "recall": round(recall_score(y_true, y_pred), 4),
        "f1": round(f1_score(y_true, y_pred), 4),
        "roc_auc": round(roc_auc_score(y_true, y_prob), 4),
    }


def train_model(n_samples=6000, seed=42, save_dataset=True):
    df = simulate_dataset(n_samples, seed)
    if save_dataset:
        settings.DATASET_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(settings.DATASET_DIR / "expiry_training_data.csv", index=False)

    X, y = df[FEATURE_COLUMNS], df["expired"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y)

    candidates = {
        "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "Decision Tree": DecisionTreeClassifier(max_depth=8, random_state=seed),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=12, min_samples_leaf=5,
            class_weight="balanced", random_state=seed, n_jobs=-1),
    }
    comparison = {}
    for name, clf in candidates.items():
        clf.fit(X_train, y_train)
        prob = clf.predict_proba(X_test)[:, 1]
        comparison[name] = _scores(y_test, (prob >= 0.5).astype(int), prob)

    rf = candidates["Random Forest"]
    prob = rf.predict_proba(X_test)[:, 1]
    pred = (prob >= 0.5).astype(int)
    metrics = {
        "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "algorithm": "Random Forest (200 trees, max depth 12)",
        "n_samples": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "positive_rate": round(float(y.mean()), 4),
        **_scores(y_test, pred, prob),
        "confusion_matrix": confusion_matrix(y_test, pred).tolist(),
        "feature_importance": sorted(
            [{"feature": f, "importance": round(float(v), 4)}
             for f, v in zip(FEATURE_COLUMNS, rf.feature_importances_)],
            key=lambda r: -r["importance"]),
        "comparison": comparison,
    }

    model_path, metrics_path = _paths()
    joblib.dump(rf, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2))
    _cache["model"] = None
    return metrics


def load_metrics():
    _, metrics_path = _paths()
    if metrics_path.exists():
        return json.loads(metrics_path.read_text())
    return None


def load_model():
    model_path, _ = _paths()
    if not model_path.exists():
        train_model()
    mtime = model_path.stat().st_mtime
    if _cache["model"] is None or _cache["mtime"] != mtime:
        _cache["model"] = joblib.load(model_path)
        _cache["mtime"] = mtime
    return _cache["model"]


def risk_level(prob):
    cfg = settings.MEDISENSE
    if prob >= cfg["HIGH_RISK"]:
        return "High"
    if prob >= cfg["MEDIUM_RISK"]:
        return "Medium"
    return "Low"


def recommend(level, days_to_expiry, accepts_returns, coverage):
    """Rule-based action advice on top of the ML risk level."""
    if level == "Expired":
        return "Remove from shelf immediately; return to supplier or send for safe disposal."
    if level == "High":
        if days_to_expiry <= 90 and accepts_returns:
            return "Return to supplier before expiry, or sell at 20–30% discount."
        if days_to_expiry <= 90:
            return "Sell at 20–30% discount and place at the counter; stop reordering."
        return "Stop reordering; offer 10–15% discount or transfer to a busier outlet."
    if level == "Medium":
        if coverage > 1:
            return "Monitor weekly; display prominently and avoid new orders until stock falls."
        return "Monitor weekly; dispense strictly FEFO."
    return "No action needed; normal FEFO dispensing."


def predict_batches(batches=None, today=None):
    """Return a list of dicts with risk details for every batch in stock."""
    from inventory.models import Batch

    today = today or date.today()
    if batches is None:
        batches = Batch.objects.in_stock().select_related("medicine", "supplier",
                                                         "medicine__category")
    batches = list(batches)
    live = [b for b in batches if b.expiry_date > today and b.quantity > 0]
    expired = [b for b in batches if b.expiry_date <= today and b.quantity > 0]

    results = []
    rows = batch_features(live, today)
    if rows:
        model = load_model()
        X = pd.DataFrame([f for _, f in rows], columns=FEATURE_COLUMNS)
        probs = model.predict_proba(X)[:, 1]
        for (b, f), p in zip(rows, probs):
            p = float(p)
            level = risk_level(p)
            sellable = f["avg_daily_sales"] * f["days_to_expiry"] - f["qty_ahead"]
            unsold = int(np.clip(b.quantity - max(sellable, 0), 0, b.quantity))
            results.append({
                "batch": b, "features": f, "probability": round(p * 100, 1),
                "level": level, "expected_unsold": unsold,
                "expected_loss": round(unsold * float(b.purchase_price), 2),
                "action": recommend(level, f["days_to_expiry"],
                                    bool(b.supplier and b.supplier.accepts_returns),
                                    f["coverage_ratio"]),
            })
    for b in expired:
        results.append({
            "batch": b, "features": None, "probability": 100.0, "level": "Expired",
            "expected_unsold": b.quantity,
            "expected_loss": round(b.quantity * float(b.purchase_price), 2),
            "action": recommend("Expired", 0, False, 0),
        })
    order = {"Expired": 0, "High": 1, "Medium": 2, "Low": 3}
    results.sort(key=lambda r: (order[r["level"]], -r["probability"],
                                r["batch"].expiry_date))
    return results
