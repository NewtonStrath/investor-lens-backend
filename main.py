import logging
from collections import defaultdict
from datetime import date
from io import StringIO
from typing import List

import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import (
    get_db, engine, Base,
    User, ScoreMetricDB,
    CDRFeatureDB, TransactionFeatureDB,
    BehavioralFeatureDB, MLScoreDB,
)
from ml import (
    get_cdr_bundle, get_tx_bundle,
    predict_score, get_sub_metrics,
    engineer_cdr_features, engineer_transaction_features,
    CDR_DISPLAY_FEATURES, TX_DISPLAY_FEATURES,
)
from model import (
    Category, SubMetric, ScoreHistoryItem, DashboardScoreResponse,
    RegisterRequest, LoginRequest,
    RecommendationResponse, RecommendationRequest,
    ProcessRequest,
)
from util import (
    hash_password, verify_password, create_jwt,
    generate_recommendations, get_current_user,
)

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- APP ----------------
app = FastAPI()

origins = [
    "http://localhost:5174",
    "http://localhost:5173",
    "http://localhost:3000",
    "https://investorlens-d23aa.firebaseapp.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified / created.")
    # Eagerly load ML models so the first request isn't slow
    try:
        get_cdr_bundle()
        get_tx_bundle()
        logger.info("ML models loaded successfully.")
    except FileNotFoundError as e:
        logger.warning("ML model not found at startup: %s", e)


# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email.lower()).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        name=data.name,
        email=data.email.lower(),
        password=hash_password(data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User created successfully",
        "user": {"id": new_user.id, "name": new_user.name, "email": new_user.email},
    }


@app.post("/api/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "token": create_jwt(user.id, user.email),
        "user": {"id": user.id, "name": user.name, "email": user.email},
    }


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/api/dashboard/score", response_model=DashboardScoreResponse)
def get_dashboard_score(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    user_id = current_user.id

    latest_date = db.query(func.max(ScoreMetricDB.metric_date)).filter(
        ScoreMetricDB.user_id == user_id
    ).scalar()

    if not latest_date:
        return DashboardScoreResponse(overallScore=0, categories=[])

    metrics = db.query(ScoreMetricDB).filter(
        ScoreMetricDB.user_id == user_id,
        ScoreMetricDB.metric_date == latest_date,
    ).all()

    grouped = defaultdict(list)
    for m in metrics:
        grouped[m.category].append(SubMetric(label=m.metric_label, value=m.value))

    categories = []
    category_scores = []
    for category, sub_metrics in grouped.items():
        score = int(sum(m.value for m in sub_metrics) / len(sub_metrics))
        category_scores.append(score)
        categories.append(Category(
            title=f"{category.capitalize()} Score Card",
            score=score,
            type=category,
            subMetrics=sub_metrics,
        ))

    overall_score = int(sum(category_scores) / len(category_scores)) if category_scores else 0
    logger.info("Dashboard score for user %d: %d", user_id, overall_score)
    return DashboardScoreResponse(overallScore=overall_score, categories=categories)


@app.get("/api/dashboard/history", response_model=List[ScoreHistoryItem])
def get_dashboard_history(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    user_id = current_user.id

    rows = db.query(
        func.date_trunc("month", ScoreMetricDB.metric_date).label("month"),
        ScoreMetricDB.category,
        func.avg(ScoreMetricDB.value).label("score"),
    ).filter(
        ScoreMetricDB.user_id == user_id
    ).group_by("month", ScoreMetricDB.category).order_by("month").all()

    if not rows:
        return []

    history_map: dict = defaultdict(dict)
    for r in rows:
        history_map[r.month.strftime("%b %d, %Y")][r.category] = int(r.score)

    history = []
    previous_overall = None
    for i, (month, scores) in enumerate(history_map.items()):
        cdr = scores.get("cdr", 0)
        transaction = scores.get("transaction", 0)
        behavioral = scores.get("behavioral", 0)
        overall = int((cdr + transaction + behavioral) / 3)
        change = (overall - previous_overall) if previous_overall is not None else 0
        previous_overall = overall
        history.append(ScoreHistoryItem(
            id=str(i + 1), date=month, overall=overall,
            cdr=cdr, transaction=transaction, behavioral=behavioral, change=change,
        ))
    return history


# ─── Recommendations ──────────────────────────────────────────────────────────

@app.post("/api/recommendations/{score_type}", response_model=RecommendationResponse)
def get_recommendations(score_type: str, request: RecommendationRequest):
    return RecommendationResponse(
        recommendations=generate_recommendations(score_type, request.score)
    )


# ─── Processing pipeline ──────────────────────────────────────────────────────

@app.post("/api/process/extract-cdr")
async def extract_cdr_features(
        customer_id: int = Form(...),
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    contents = await file.read()
    df = pd.read_csv(StringIO(contents.decode("utf-8")))
    logger.info("CDR upload for customer %d — %d rows", customer_id, len(df))

    # Assign all records to this customer so feature engineering returns one row
    df["caller_id"] = str(customer_id)

    try:
        features_df = engineer_cdr_features(df)

        # Run ML model
        bundle = get_cdr_bundle()
        cdr_score = predict_score(bundle, features_df)

        # Pull a few raw values for storage
        row = features_df.iloc[0]
        total_calls = int(row.get("total_calls_all", 0))
        avg_duration = float(row.get("avg_call_duration_out", 0.0))
        unique_contacts = int(row.get("unique_receivers", 0))

        # Upsert CDR features row
        db.query(CDRFeatureDB).filter(CDRFeatureDB.customer_id == customer_id).delete()
        db.add(CDRFeatureDB(
            customer_id=customer_id,
            total_calls=total_calls,
            avg_call_duration=avg_duration,
            unique_contacts=unique_contacts,
            cdr_score=cdr_score,
        ))
        db.commit()

        logger.info("CDR score for customer %d: %.1f", customer_id, cdr_score)
        return {"message": "CDR features extracted successfully", "cdr_score": cdr_score}

    except HTTPException:
        raise
    except ValueError as e:
        logger.error("CDR validation error for customer %d: %s", customer_id, e)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("CDR processing failed for customer %d", customer_id)
        raise HTTPException(status_code=500, detail=f"CDR processing error: {str(e)}")


@app.post("/api/process/extract-transactions")
async def extract_transaction_features(
        customer_id: int = Form(...),
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    contents = await file.read()
    df = pd.read_csv(StringIO(contents.decode("utf-8")))
    logger.info("Transaction upload for customer %d — %d rows", customer_id, len(df))

    # Normalize column names (the function does this too, but do it early
    # so we can identify the customer's ID before feature engineering)
    import re
    df.columns = [
        re.sub(r"[^a-zA-Z0-9_]", "", c.strip().lower().replace(" ", "_"))
        for c in df.columns
    ]

    # Identify the customer's own ID in the file.
    # The uploaded file contains the customer's outgoing transactions
    # (where they are the originator) and optionally incoming transactions
    # (where they appear as the destination, sent by others).
    # We find the most frequent originator — that is the customer's ID.
    orig_col = "origin" if "origin" in df.columns else "idorig"
    dest_col = "name_destination" if "name_destination" in df.columns else "iddest"
    customer_file_id = str(df[orig_col].value_counts().index[0])
    logger.info(
        "Transaction file customer ID detected as '%s' (%d / %d rows as origin)",
        customer_file_id,
        (df[orig_col].astype(str) == customer_file_id).sum(),
        len(df),
    )

    # Do NOT overwrite origin — keep the file as-is so both outgoing
    # (origin = customer_file_id) and incoming (dest = customer_file_id)
    # transactions are credited correctly by engineer_transaction_features.

    try:
        features_df = engineer_transaction_features(df)

        # Find the customer's row in the engineered feature matrix
        features_df["idorig"] = features_df["idorig"].astype(str)
        cust_features = features_df[features_df["idorig"] == customer_file_id]
        if cust_features.empty:
            raise ValueError(
                f"Could not find features for the detected customer ID '{customer_file_id}'. "
                "Ensure the file contains the customer's outgoing transactions."
            )
        features_df = cust_features

        # Run ML model
        bundle = get_tx_bundle()
        tx_score = predict_score(bundle, features_df)

        row = features_df.iloc[0]
        total_tx = int(row.get("total_transactions", 0))
        total_amt = float(row.get("total_amount_sent", 0.0))
        avg_tx = float(row.get("avg_amount_sent", 0.0))

        db.query(TransactionFeatureDB).filter(
            TransactionFeatureDB.customer_id == customer_id
        ).delete()
        db.add(TransactionFeatureDB(
            customer_id=customer_id,
            total_transactions=total_tx,
            total_amount=total_amt,
            avg_transaction=avg_tx,
            tx_score=tx_score,
        ))
        db.commit()

        logger.info("Transaction score for customer %d: %.1f", customer_id, tx_score)
        return {"message": "Transaction features extracted successfully", "tx_score": tx_score}

    except HTTPException:
        raise
    except ValueError as e:
        logger.error("Transaction validation error for customer %d: %s", customer_id, e)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Transaction processing failed for customer %d", customer_id)
        raise HTTPException(status_code=500, detail=f"Transaction processing error: {str(e)}")


@app.post("/api/process/compute-behavioral")
def compute_behavioral(req: ProcessRequest, db: Session = Depends(get_db)):
    cdr_row = db.query(CDRFeatureDB).filter(
        CDRFeatureDB.customer_id == req.customer_id
    ).first()
    tx_row = db.query(TransactionFeatureDB).filter(
        TransactionFeatureDB.customer_id == req.customer_id
    ).first()

    if not cdr_row or not tx_row:
        raise HTTPException(status_code=404, detail="CDR or transaction features not found. "
                                                     "Run extract steps first.")
    if cdr_row.cdr_score is None or tx_row.tx_score is None:
        raise HTTPException(status_code=422, detail="ML scores not yet computed. "
                                                     "Re-run the extract steps.")

    # Behavioral score = equal-weighted average of CDR and transaction ML scores
    behavioral_score = (cdr_row.cdr_score + tx_row.tx_score) / 2.0

    db.query(BehavioralFeatureDB).filter(
        BehavioralFeatureDB.customer_id == req.customer_id
    ).delete()
    db.add(BehavioralFeatureDB(
        customer_id=req.customer_id,
        behavioral_score=round(behavioral_score, 1),
    ))
    db.commit()

    logger.info("Behavioral score for customer %d: %.1f", req.customer_id, behavioral_score)
    return {"message": "Behavioral score computed successfully",
            "behavioral_score": round(behavioral_score, 1)}


@app.post("/api/process/ml-score")
def compute_ml_score(req: ProcessRequest, db: Session = Depends(get_db)):
    cdr_row = db.query(CDRFeatureDB).filter(
        CDRFeatureDB.customer_id == req.customer_id
    ).first()
    tx_row = db.query(TransactionFeatureDB).filter(
        TransactionFeatureDB.customer_id == req.customer_id
    ).first()
    behavioral_row = db.query(BehavioralFeatureDB).filter(
        BehavioralFeatureDB.customer_id == req.customer_id
    ).first()

    if not cdr_row or not tx_row or not behavioral_row:
        raise HTTPException(status_code=404, detail="Required feature records missing. "
                                                     "Run all extract and behavioral steps first.")

    cdr_score = round(cdr_row.cdr_score or 0.0)
    tx_score = round(tx_row.tx_score or 0.0)
    behavioral_score = round(behavioral_row.behavioral_score or 0.0)
    overall_score = round((cdr_score + tx_score + behavioral_score) / 3)

    # Persist overall ML score
    db.query(MLScoreDB).filter(MLScoreDB.customer_id == req.customer_id).delete()
    db.add(MLScoreDB(customer_id=req.customer_id, score=float(overall_score)))

    # ── Bridge to score_metrics so the dashboard reflects this run ──
    today = date.today()
    user_id = req.customer_id

    db.query(ScoreMetricDB).filter(
        ScoreMetricDB.user_id == user_id,
        ScoreMetricDB.metric_date == today,
    ).delete()

    # Re-engineer features to get normalised sub-metric values
    cdr_sub_metrics: dict[str, int] = {}
    tx_sub_metrics: dict[str, int] = {}

    try:
        # Reconstruct a minimal single-row DataFrame from stored aggregated values
        # and run get_sub_metrics to get normalised 0-100 sub-metric values.
        cdr_proxy = pd.DataFrame([{
            "total_calls_all": cdr_row.total_calls or 0,
            "unique_receiver_ratio": (
                cdr_row.unique_contacts / cdr_row.total_calls
                if cdr_row.total_calls else 0.0
            ),
            "avg_call_duration_out": cdr_row.avg_call_duration or 0.0,
        }])
        cdr_bundle = get_cdr_bundle()
        cdr_sub_metrics = get_sub_metrics(cdr_bundle, cdr_proxy, CDR_DISPLAY_FEATURES)

        tx_proxy = pd.DataFrame([{
            "total_transactions": tx_row.total_transactions or 0,
            "total_amount_sent": tx_row.total_amount or 0.0,
            "incoming_outgoing_amount_ratio": 0.0,  # not stored; use neutral 0
        }])
        tx_bundle = get_tx_bundle()
        tx_sub_metrics = get_sub_metrics(tx_bundle, tx_proxy, TX_DISPLAY_FEATURES)

        # ── Scale-mismatch guard ───────────────────────────────────────────────
        # The model scaler is fitted on the training dataset (e.g. large PaySim
        # amounts). If the uploaded data lives in a very different range, all
        # sub-metrics normalise to near-zero even though the ML score is non-zero.
        # When that happens, fall back to the ML score so the Score Card is
        # consistent with the model output rather than showing a flat zero.
        if cdr_score > 0 and all(v <= 2 for v in cdr_sub_metrics.values()):
            logger.warning("CDR sub-metrics all near-zero — using cdr_score as proxy")
            cdr_sub_metrics = {k: cdr_score for k in cdr_sub_metrics}

        if tx_score > 0 and all(v <= 2 for v in tx_sub_metrics.values()):
            logger.warning("TX sub-metrics all near-zero — using tx_score as proxy")
            tx_sub_metrics = {k: tx_score for k in tx_sub_metrics}

    except Exception as e:
        logger.warning("Sub-metric computation fell back to score values: %s", e)
        cdr_sub_metrics = {"Call Frequency": cdr_score, "Network Diversity": cdr_score,
                           "Avg Call Duration": cdr_score}
        tx_sub_metrics = {"Transaction Volume": tx_score, "Outgoing Amount": tx_score,
                          "Incoming/Outgoing Ratio": tx_score}

    behavioral_sub_metrics = {
        "CDR Signal":         cdr_score,
        "Transaction Signal": tx_score,
        "Behavioral Score":   behavioral_score,
    }

    metric_rows = []
    for label, value in cdr_sub_metrics.items():
        metric_rows.append(ScoreMetricDB(
            user_id=user_id, category="cdr",
            metric_label=label, value=value, metric_date=today,
        ))
    for label, value in tx_sub_metrics.items():
        metric_rows.append(ScoreMetricDB(
            user_id=user_id, category="transaction",
            metric_label=label, value=value, metric_date=today,
        ))
    for label, value in behavioral_sub_metrics.items():
        metric_rows.append(ScoreMetricDB(
            user_id=user_id, category="behavioral",
            metric_label=label, value=value, metric_date=today,
        ))

    db.bulk_save_objects(metric_rows)
    db.commit()

    logger.info(
        "ML score for customer %d — CDR: %d, TX: %d, Behavioral: %d, Overall: %d",
        req.customer_id, cdr_score, tx_score, behavioral_score, overall_score,
    )
    return {
        "customer_id": req.customer_id,
        "investment_score": overall_score,
        "breakdown": {
            "cdr": cdr_score,
            "transaction": tx_score,
            "behavioral": behavioral_score,
        },
    }
