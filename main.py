import os
from collections import defaultdict
from io import StringIO
from typing import List, Dict

import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from db import get_db, User, ScoreMetricDB, CDRFeatureDB, TransactionFeatureDB
from model import Category, SubMetric, ScoreHistoryItem, DashboardScoreResponse, RegisterRequest, LoginRequest, \
    RecommendationResponse, RecommendationRequest, ProcessRequest
from util import hash_password, verify_password, create_jwt, generate_recommendations, get_csv_path

# ---------------- APP ----------------
app = FastAPI()

origins = [
    "http://localhost:5174",  # ← your frontend port
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/auth/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(
        User.email == data.email.lower()
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        name=data.name,
        email=data.email.lower(),
        password=hash_password(data.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User created successfully",
        "user": {
            "id": new_user.id,
            "name": new_user.name,
            "email": new_user.email
        }
    }


@app.post("/api/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.email == data.email.lower()
    ).first()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_jwt(user.id, user.email)

    return {
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    }


@app.get("/api/dashboard/score", response_model=DashboardScoreResponse)
def get_dashboard_score(
        user_id: str = Query(..., description="User ID"),
        db: Session = Depends(get_db)
):
    # Get latest metric date for user
    latest_date = db.query(
        func.max(ScoreMetricDB.metric_date)
    ).filter(
        ScoreMetricDB.user_id == user_id
    ).scalar()

    if not latest_date:
        return {"overallScore": 0, "categories": []}

    metrics = db.query(ScoreMetricDB).filter(
        ScoreMetricDB.user_id == user_id,
        ScoreMetricDB.metric_date == latest_date
    ).all()

    grouped = defaultdict(list)

    for m in metrics:
        grouped[m.category].append(
            SubMetric(
                label=m.metric_label,
                value=m.value
            )
        )

    categories = []
    category_scores = []

    for category, sub_metrics in grouped.items():
        score = int(sum(m.value for m in sub_metrics) / len(sub_metrics))
        category_scores.append(score)

        categories.append(
            Category(
                title=f"{category} Score Card",
                score=score,
                type=category,
                subMetrics=sub_metrics
            )
        )

    overall_score = int(sum(category_scores) / len(category_scores))
    print(categories)

    return DashboardScoreResponse(
        overallScore=overall_score,
        categories=categories
    )


@app.get("/api/dashboard/history", response_model=List[ScoreHistoryItem])
def get_dashboard_history(
        user_id: str = Query(..., description="ID of the user"),
        db: Session = Depends(get_db)
):
    rows = db.query(
        func.date_trunc("month", ScoreMetricDB.metric_date).label("month"),
        ScoreMetricDB.category,
        func.avg(ScoreMetricDB.value).label("score")
    ).filter(
        ScoreMetricDB.user_id == user_id
    ).group_by(
        "month", ScoreMetricDB.category
    ).order_by(
        "month"
    ).all()

    # Return empty list if no rows
    if not rows:
        return []

    history_map = defaultdict(dict)

    # Build structure like: {month: {category: score}}
    for r in rows:
        month = r.month.strftime("%b %d, %Y")
        history_map[month][r.category] = int(r.score)

    history = []
    previous_overall = None

    for i, (month, scores) in enumerate(history_map.items()):

        cdr = scores.get("cdr", 0)
        transaction = scores.get("transaction", 0)
        behavioral = scores.get("behavioral", 0)

        overall = int((cdr + transaction + behavioral) / 3)

        change = 0
        if previous_overall is not None:
            change = overall - previous_overall

        previous_overall = overall

        history.append(
            ScoreHistoryItem(
                id=str(i + 1),
                date=month,
                overall=overall,
                cdr=cdr,
                transaction=transaction,
                behavioral=behavioral,
                change=change
            )
        )

    return history


@app.post("/api/recommendations/{score_type}", response_model=RecommendationResponse)
def get_recommendations(score_type: str, request: RecommendationRequest):
    recommendations = generate_recommendations(score_type, request.score)

    return RecommendationResponse(
        recommendations=recommendations
    )


@app.post("/api/process/extract-cdr")
async def extract_cdr_features(
        customer_id: int = Form(...),
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    contents = await file.read()
    df = pd.read_csv(StringIO(contents.decode("utf-8")))
    print(df.head())

    # ===== Feature extraction =====
    total_calls = len(df)
    avg_duration = df["duration"].mean()
    unique_contacts = df["receiver_id"].nunique()

    features = CDRFeatureDB(
        customer_id=customer_id,
        total_calls=int(total_calls),
        avg_call_duration=float(avg_duration),
        unique_contacts=int(unique_contacts)
    )

    db.add(features)
    db.commit()

    return {"message": "CDR features extracted successfully"}


@app.post("/api/process/extract-transactions")
async def extract_transaction_features(
        customer_id: int = Form(...),
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    # Only allow CSV files
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    # Read CSV contents from memory
    contents = await file.read()
    df = pd.read_csv(StringIO(contents.decode("utf-8")))
    print(df.head())

    # ===== Feature extraction =====
    total_transactions = len(df)
    total_amount = df["amount"].sum()
    avg_transaction = df["amount"].mean()

    features = TransactionFeatureDB(
        customer_id=customer_id,
        total_transactions=int(total_transactions),
        total_amount=float(total_amount),
        avg_transaction=float(avg_transaction)
    )

    db.add(features)
    db.commit()

    return {"message": "Transaction features extracted successfully"}


class BehavioralFeatureDB:
    pass


@app.post("/api/process/compute-behavioral")
def compute_behavioral(req: ProcessRequest, db: Session = Depends(get_db)):
    cdr = db.query(CDRFeatureDB).filter(
        CDRFeatureDB.customer_id == req.customer_id
    ).first()

    tx = db.query(TransactionFeatureDB).filter(
        TransactionFeatureDB.customer_id == req.customer_id
    ).first()

    if not cdr or not tx:
        raise HTTPException(status_code=404, detail="Required features not found")

    # ===== Example behavioral computation =====
    behavioral_score = (
            (cdr.total_calls * 0.3) +
            (cdr.unique_contacts * 0.2) +
            (tx.total_transactions * 0.3) +
            (tx.total_amount * 0.2)
    )

    behavioral = BehavioralFeatureDB(
        customer_id=req.customer_id,
        behavioral_score=float(behavioral_score)
    )

    db.add(behavioral)
    db.commit()

    return {"message": "Behavioral score computed successfully"}


class MLScoreDB:
    pass


@app.post("/api/process/ml-score")
def compute_ml_score(req: ProcessRequest, db: Session = Depends(get_db)):
    cdr = db.query(CDRFeatureDB).filter(
        CDRFeatureDB.customer_id == req.customer_id
    ).first()

    tx = db.query(TransactionFeatureDB).filter(
        TransactionFeatureDB.customer_id == req.customer_id
    ).first()

    behavioral = db.query(BehavioralFeatureDB).filter(
        BehavioralFeatureDB.customer_id == req.customer_id
    ).first()

    if not cdr or not tx or not behavioral:
        raise HTTPException(status_code=404, detail="Required features missing")

    # ===== Replace with real ML model =====
    score = (
            (cdr.total_calls * 0.2) +
            (cdr.unique_contacts * 0.2) +
            (tx.total_transactions * 0.2) +
            (tx.total_amount * 0.2) +
            (behavioral.behavioral_score * 0.2)
    )

    ml_score = MLScoreDB(
        customer_id=req.customer_id,
        score=float(score)
    )

    db.add(ml_score)
    db.commit()

    return {
        "customer_id": req.customer_id,
        "investment_score": round(score, 2)
    }
