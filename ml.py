"""
ml.py — ML feature engineering and inference for InvestorLens.

Models are trained in the Notebooks folder and saved as .joblib files.
Point MODELS_DIR to the folder containing:
    cdr_model.joblib
    transaction_model.joblib

By default it looks for a  models/  subdirectory next to this file.
"""
import logging
import os
import re
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Model directory ─────────────────────────────────────────────────────────
MODELS_DIR = Path(os.getenv("MODELS_DIR", str(Path(__file__).parent / "models")))

# Module-level cache so models are loaded only once per process
_cdr_bundle: Optional[dict] = None
_tx_bundle: Optional[dict] = None


def _load_bundle(filename: str) -> dict:
    path = MODELS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Model file not found: {path}\n"
            "Run the training notebook and copy (or symlink) the .joblib file "
            f"into  {MODELS_DIR}/"
        )
    bundle = joblib.load(path)
    logger.info("Loaded model bundle: %s  (features: %d)", filename, len(bundle["feature_cols"]))
    return bundle


def get_cdr_bundle() -> dict:
    global _cdr_bundle
    if _cdr_bundle is None:
        _cdr_bundle = _load_bundle("cdr_model.joblib")
    return _cdr_bundle


def get_tx_bundle() -> dict:
    global _tx_bundle
    if _tx_bundle is None:
        _tx_bundle = _load_bundle("transaction_model.joblib")
    return _tx_bundle


# ─── Scoring ──────────────────────────────────────────────────────────────────

def _apply_log_transform(X: pd.DataFrame, log_features: list) -> pd.DataFrame:
    """
    Apply log1p to absolute-amount features before MinMaxScaling.

    This makes the scaler scale-invariant: a user with $200 avg_amount
    and a user with $140k avg_amount produce feature values of 5.3 vs 11.8
    (ratio 2.2×) instead of 200 vs 140,000 (ratio 700×), so small-amount
    demo data still receives a meaningful score from a model trained on
    large-amount MoMTSim data.

    The same transform must be applied during training and inference.
    The list of transformed columns is stored in the model bundle as
    ``log_features`` so inference always matches training exactly.
    """
    X = X.copy()
    for col in log_features:
        if col in X.columns:
            X[col] = np.log1p(X[col].clip(lower=0))
    return X


def predict_score(bundle: dict, features_df: pd.DataFrame) -> float:
    """
    Run a trained LightGBM scorer and return a consistent 0–100 score.

    Normalization: raw_prediction / num_features * 100, clipped to [0, 100].
    This is consistent because the model was trained on y = sum(X_scaled),
    so the theoretical maximum raw prediction equals num_features (all
    MinMax-scaled features at 1.0).
    """
    model = bundle["model"]
    scaler = bundle["scaler"]
    feature_cols = bundle["feature_cols"]
    log_features = bundle.get("log_features", [])  # empty list → no transform (old bundles)

    X = features_df[feature_cols].fillna(0)
    X = _apply_log_transform(X, log_features)
    X_scaled = pd.DataFrame(scaler.transform(X), columns=feature_cols)
    raw = float(model.predict(X_scaled)[0])
    score = float(np.clip((raw / len(feature_cols)) * 100, 0, 100))
    return round(score, 1)


def get_sub_metrics(bundle: dict, features_df: pd.DataFrame, display: dict) -> dict:
    """
    Return normalized 0–100 values for a chosen set of sub-metric features.

    Args:
        bundle:       model bundle (model, scaler, feature_cols)
        features_df:  single-row DataFrame of engineered features
        display:      {label: feature_col} mapping of sub-metrics to show

    Uses the scaler's fitted data_min_ / data_max_ for consistent normalization.
    Log-transforms amount features before normalization to match training.
    """
    scaler = bundle["scaler"]
    feature_cols: list = bundle["feature_cols"]
    log_features: list = bundle.get("log_features", [])
    result: dict[str, int] = {}

    # Apply the same log transform used during training so sub-metric
    # normalization is consistent with the scaler's fitted ranges.
    transformed_df = _apply_log_transform(features_df, log_features)

    for label, feat in display.items():
        if feat not in feature_cols:
            result[label] = 0
            continue
        idx = feature_cols.index(feat)
        raw_val = float(transformed_df[feat].iloc[0]) if feat in transformed_df.columns else 0.0
        feat_min = float(scaler.data_min_[idx])
        feat_max = float(scaler.data_max_[idx])
        if feat_max > feat_min:
            normalized = (raw_val - feat_min) / (feat_max - feat_min) * 100
        else:
            normalized = 0.0
        result[label] = int(np.clip(normalized, 0, 100))

    return result


# CDR sub-metrics to display on the dashboard
CDR_DISPLAY_FEATURES = {
    "Call Frequency":   "total_calls_all",
    "Network Diversity": "unique_receiver_ratio",
    "Avg Call Duration": "avg_call_duration_out",
}

# Transaction sub-metrics to display on the dashboard
TX_DISPLAY_FEATURES = {
    "Transaction Volume":   "total_transactions",
    "Outgoing Amount":      "total_amount_sent",
    "Incoming/Outgoing Ratio": "incoming_outgoing_amount_ratio",
}


# ─── CDR feature engineering ──────────────────────────────────────────────────

def engineer_cdr_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replicates engineer_cdr_features from CDR_Notebook.ipynb.

    Expected columns (case-insensitive, spaces normalized to underscores):
        caller_id, caller_company, receiver_id, receiver_company,
        timestamp, duration_s
    """
    cdr = df.copy()
    # Normalise column names: lowercase, spaces→underscores, strip special chars
    # e.g. "Caller id" → "caller_id",  "Duration s." → "duration_s"
    cdr.columns = [
        re.sub(r"[^a-z0-9_]", "", c.strip().lower().replace(" ", "_"))
        for c in cdr.columns
    ]

    # Accept plain "duration" as an alias for "duration_s"
    if "duration" in cdr.columns and "duration_s" not in cdr.columns:
        cdr = cdr.rename(columns={"duration": "duration_s"})

    required = ["caller_id", "caller_company", "receiver_id", "receiver_company",
                "timestamp", "duration_s"]
    missing = [c for c in required if c not in cdr.columns]
    if missing:
        raise ValueError(f"Missing required CDR columns: {missing}")

    cdr["timestamp"] = pd.to_datetime(cdr["timestamp"], errors="coerce")
    cdr["duration_s"] = pd.to_numeric(cdr["duration_s"], errors="coerce")
    cdr = cdr.dropna(subset=["caller_id", "receiver_id", "timestamp", "duration_s"])

    # Time-based fields
    cdr["call_date"]   = cdr["timestamp"].dt.date
    cdr["hour"]        = cdr["timestamp"].dt.hour
    cdr["day_of_week"] = cdr["timestamp"].dt.dayofweek
    cdr["is_weekend"]  = cdr["day_of_week"].isin([5, 6]).astype(int)
    cdr["is_morning"]  = cdr["hour"].between(6, 11).astype(int)
    cdr["is_afternoon"]= cdr["hour"].between(12, 17).astype(int)
    cdr["is_evening"]  = cdr["hour"].between(18, 23).astype(int)
    cdr["is_night"]    = ((cdr["hour"] >= 0) & (cdr["hour"] < 6)).astype(int)

    # Network flags
    cdr["same_network"] = (
        cdr["caller_company"].fillna("").str.lower()
        == cdr["receiver_company"].fillna("").str.lower()
    ).astype(int)

    # Outgoing aggregations
    out = cdr.groupby("caller_id").agg(
        total_calls_out=("caller_id", "count"),
        total_call_duration_out=("duration_s", "sum"),
        avg_call_duration_out=("duration_s", "mean"),
        max_call_duration_out=("duration_s", "max"),
        min_call_duration_out=("duration_s", "min"),
        std_call_duration_out=("duration_s", "std"),
        unique_receivers=("receiver_id", "nunique"),
        active_days_out=("call_date", "nunique"),
        weekend_calls_out=("is_weekend", "sum"),
        morning_calls_out=("is_morning", "sum"),
        afternoon_calls_out=("is_afternoon", "sum"),
        evening_calls_out=("is_evening", "sum"),
        night_calls_out=("is_night", "sum"),
        onnet_calls_out=("same_network", "sum"),
    ).reset_index()

    out["std_call_duration_out"] = out["std_call_duration_out"].fillna(0)

    # Derived outgoing ratios
    out["avg_calls_per_active_day_out"] = out["total_calls_out"] / out["active_days_out"]
    out["avg_duration_per_active_day_out"] = out["total_call_duration_out"] / out["active_days_out"]
    out["onnet_call_ratio_out"] = np.where(
        out["total_calls_out"] > 0, out["onnet_calls_out"] / out["total_calls_out"], 0)
    out["unique_receiver_ratio"] = np.where(
        out["total_calls_out"] > 0, out["unique_receivers"] / out["total_calls_out"], 0)
    out["weekend_call_ratio_out"] = np.where(
        out["total_calls_out"] > 0, out["weekend_calls_out"] / out["total_calls_out"], 0)
    for period in ["morning", "afternoon", "evening", "night"]:
        out[f"{period}_call_ratio_out"] = np.where(
            out["total_calls_out"] > 0,
            out[f"{period}_calls_out"] / out["total_calls_out"], 0)

    # Incoming aggregations
    inc = cdr.groupby("receiver_id").agg(
        total_calls_in=("receiver_id", "count"),
        total_call_duration_in=("duration_s", "sum"),
        avg_call_duration_in=("duration_s", "mean"),
        unique_callers=("caller_id", "nunique"),
        active_days_in=("call_date", "nunique"),
    ).reset_index().rename(columns={"receiver_id": "caller_id"})

    features = out.merge(inc, on="caller_id", how="left")
    fill_cols = ["total_calls_in", "total_call_duration_in", "avg_call_duration_in",
                 "unique_callers", "active_days_in"]
    features[fill_cols] = features[fill_cols].fillna(0)

    # Combined interaction features
    features["call_balance_ratio"] = np.where(
        features["total_calls_in"] > 0,
        features["total_calls_out"] / features["total_calls_in"],
        features["total_calls_out"])
    features["duration_balance_ratio"] = np.where(
        features["total_call_duration_in"] > 0,
        features["total_call_duration_out"] / features["total_call_duration_in"],
        features["total_call_duration_out"])
    features["total_calls_all"]    = features["total_calls_out"] + features["total_calls_in"]
    features["total_duration_all"] = features["total_call_duration_out"] + features["total_call_duration_in"]

    return features


# ─── Transaction feature engineering ─────────────────────────────────────────

def engineer_transaction_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replicates extract_transaction_scoring_features from Transactions.ipynb.

    Accepts the demo data column format:
        type, amount, origin, old_orig_balance, new_orig_balance,
        name_destination, old_dest_balance, new_dest_balance

    Also accepts the original PaySim format (column names are normalised
    and remapped automatically).
    """
    tx = df.copy()
    # Normalise column names: lowercase, spaces→underscores, strip special chars
    tx.columns = [
        re.sub(r"[^a-zA-Z0-9_]", "", c.strip().lower().replace(" ", "_"))
        for c in tx.columns
    ]

    # ── Remap demo data column names → internal PaySim names ─────────────────
    # Also handles MoMTSim format (nameOrig/nameDest after normalisation → nameorig/namedest)
    column_aliases = {
        "type":             "action",
        "origin":           "idorig",
        "nameorig":         "idorig",    # MoMTSim: nameOrig → idorig
        "namedest":         "iddest",    # MoMTSim: nameDest → iddest
        "old_orig_balance": "oldbalanceorig",
        "new_orig_balance": "newbalanceorig",
        "name_destination": "iddest",
        "old_dest_balance": "oldbalancedest",
        "new_dest_balance": "newbalancedest",
    }
    tx = tx.rename(columns={k: v for k, v in column_aliases.items() if k in tx.columns})

    # Add a synthetic step column if absent (not used in scoring features)
    if "step" not in tx.columns:
        tx["step"] = 0

    tx["idorig"] = tx["idorig"].astype(str)
    tx["iddest"] = tx["iddest"].astype(str)

    required = ["step", "action", "amount", "idorig",
                "oldbalanceorig", "newbalanceorig",
                "iddest", "oldbalancedest", "newbalancedest"]
    missing = [c for c in required if c not in tx.columns]
    if missing:
        raise ValueError(f"Missing required transaction columns: {missing}")

    for col in ["step", "amount", "oldbalanceorig", "newbalanceorig",
                "oldbalancedest", "newbalancedest"]:
        tx[col] = pd.to_numeric(tx[col], errors="coerce")
    tx = tx.dropna(subset=["step", "amount", "idorig"])

    # Derived flags
    threshold = tx["amount"].quantile(0.75)
    tx["is_large_tx"] = (tx["amount"] > threshold).astype(int)
    tx["is_zero_balance_after"] = (tx["newbalanceorig"] <= 0).astype(int)
    tx["amount_to_oldbalance_ratio"] = np.where(
        tx["oldbalanceorig"] > 0, tx["amount"] / tx["oldbalanceorig"], 0)

    # Origin aggregations
    origin = tx.groupby("idorig").agg(
        total_transactions=("amount", "count"),
        total_amount_sent=("amount", "sum"),
        avg_amount_sent=("amount", "mean"),
        large_tx_count=("is_large_tx", "sum"),
        zero_balance_events=("is_zero_balance_after", "sum"),
        amount_to_oldbalance_ratio=("amount_to_oldbalance_ratio", "mean"),
    ).reset_index()

    origin["large_tx_ratio"] = origin["large_tx_count"] / origin["total_transactions"]
    origin["zero_balance_event_ratio"] = origin["zero_balance_events"] / origin["total_transactions"]

    # Destination aggregations
    dest = tx.groupby("iddest").agg(
        total_amount_received=("amount", "sum"),
        avg_amount_received=("amount", "mean"),
    ).reset_index().rename(columns={"iddest": "idorig"})

    features = origin.merge(dest, on="idorig", how="left")
    features[["total_amount_received", "avg_amount_received"]] = (
        features[["total_amount_received", "avg_amount_received"]].fillna(0))

    # Flow / ratio features
    features["net_transaction_flow"] = (
        features["total_amount_received"] - features["total_amount_sent"])
    features["incoming_outgoing_amount_ratio"] = np.where(
        features["total_amount_sent"] > 0,
        features["total_amount_received"] / features["total_amount_sent"], 0)

    unique_dest = (
        tx.groupby("idorig")["iddest"].nunique()
          .reset_index()
          .rename(columns={"iddest": "unique_destinations"})
    )
    features = features.merge(unique_dest, on="idorig", how="left")
    features["unique_destination_ratio"] = (
        features["unique_destinations"] / features["total_transactions"])

    return features
