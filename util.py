import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from db import get_db, User
from model import Recommendation

load_dotenv()

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)
DATA_DIR = "data/uploads"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------------- JWT CONFIG ----------------
_jwt_secret = os.getenv("JWT_SECRET")
if not _jwt_secret:
    raise RuntimeError(
        "JWT_SECRET environment variable is not set. "
        "Add it to your .env file before starting the server."
    )
JWT_SECRET = _jwt_secret
JWT_ALGORITHM = "HS256"
JWT_EXP_MINUTES = 60


def create_jwt(user_id: int, email: str):
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXP_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def verify_jwt(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ---------------- AUTH DEPENDENCY ----------------
security = HTTPBearer()


def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
):
    payload = verify_jwt(credentials.credentials)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def generate_recommendations(score_type: str, score: int):
    """
    Generate AI-style recommendations based on score type and level.
    Score ranges: 0-20, 21-40, 41-60, 61-80, 81-100
    """
    if score_type == "cdr":
        if 0 <= score <= 20:
            return [
                Recommendation(
                    priority="high",
                    title="Increase Communication Significantly",
                    description="Very low communication frequency drastically reduces trust signals for investors.",
                    impact="Potential score improvement: +15 points",
                    actions=[
                        "Make daily calls to key contacts",
                        "Engage actively with professional network",
                        "Track call frequency and duration"
                    ],
                )
            ]
        elif 21 <= score <= 40:
            return [
                Recommendation(
                    priority="high",
                    title="Increase Call Activity",
                    description="Low communication frequency reduces investor trust.",
                    impact="Potential score improvement: +10 points",
                    actions=[
                        "Make regular calls to key contacts",
                        "Avoid long inactivity periods",
                        "Increase call duration consistency"
                    ],
                ),
                Recommendation(
                    priority="medium",
                    title="Expand Social Network",
                    description="A wider network improves credibility.",
                    impact="Potential score improvement: +6 points",
                    actions=[
                        "Connect with new contacts",
                        "Maintain regular communication",
                        "Engage in professional communities"
                    ],
                )
            ]
        elif 41 <= score <= 60:
            return [
                Recommendation(
                    priority="medium",
                    title="Share Financial Updates",
                    description="Regular updates improve transparency for investors.",
                    impact="Potential score improvement: +5 points",
                    actions=[
                        "Provide monthly summaries",
                        "Document income and investment activity",
                        "Communicate milestones clearly"
                    ],
                )
            ]
        elif 61 <= score <= 80:
            return [
                Recommendation(
                    priority="low",
                    title="Maintain Communication Consistency",
                    description="Your communication is strong; continue nurturing investor relationships.",
                    impact="Potential score improvement: +3 points",
                    actions=[
                        "Maintain regular contact",
                        "Provide timely updates",
                        "Keep communication logs organized"
                    ],
                )
            ]
        else:  # 81-100
            return [
                Recommendation(
                    priority="low",
                    title="Optimize Networking Strategically",
                    description="Your communication is excellent; focus on strategic networking.",
                    impact="Potential score improvement: +2 points",
                    actions=[
                        "Engage selectively with high-value contacts",
                        "Attend key professional events",
                        "Share achievements and updates strategically"
                    ],
                )
            ]

    if score_type == "transaction":
        if 0 <= score <= 20:
            return [
                Recommendation(
                    priority="high",
                    title="Significantly Improve Savings and Transaction Discipline",
                    description="Very low financial activity signals instability to investors.",
                    impact="Potential score improvement: +15 points",
                    actions=[
                        "Save at least 20% of income",
                        "Avoid unnecessary spending",
                        "Track every transaction"
                    ],
                )
            ]
        elif 21 <= score <= 40:
            return [
                Recommendation(
                    priority="high",
                    title="Improve Savings Behavior",
                    description="Low savings activity signals financial instability.",
                    impact="Potential score improvement: +12 points",
                    actions=[
                        "Save at least 10–20% of income",
                        "Reduce discretionary spending",
                        "Track expenses monthly"
                    ],
                ),
                Recommendation(
                    priority="medium",
                    title="Track Investment Opportunities",
                    description="Monitor investment avenues to increase credibility.",
                    impact="Potential score improvement: +7 points",
                    actions=[
                        "Record investment transactions",
                        "Analyze ROI periodically",
                        "Document lessons learned"
                    ],
                )
            ]
        elif 41 <= score <= 60:
            return [
                Recommendation(
                    priority="medium",
                    title="Diversify Transactions",
                    description="A diverse transaction pattern demonstrates financial literacy.",
                    impact="Potential score improvement: +5 points",
                    actions=[
                        "Use utility and recurring payments",
                        "Avoid irregular withdrawals",
                        "Invest in small instruments regularly"
                    ],
                )
            ]
        elif 61 <= score <= 80:
            return [
                Recommendation(
                    priority="low",
                    title="Monitor Investment Portfolio",
                    description="Maintain transparent financial records for investors.",
                    impact="Potential score improvement: +3 points",
                    actions=[
                        "Update portfolio tracker monthly",
                        "Check for unusual spending",
                        "Report updates to stakeholders"
                    ],
                )
            ]
        else:  # 81-100
            return [
                Recommendation(
                    priority="low",
                    title="Optimize Financial Strategy",
                    description="Excellent financial habits; focus on strategic investments.",
                    impact="Potential score improvement: +2 points",
                    actions=[
                        "Identify high-ROI investment opportunities",
                        "Minimize low-value transactions",
                        "Share financial summaries selectively with investors"
                    ],
                )
            ]

    if score_type == "behavioral":
        if 0 <= score <= 20:
            return [
                Recommendation(
                    priority="high",
                    title="Establish Basic Behavioral Discipline",
                    description="Very poor behavioral patterns drastically reduce investor confidence.",
                    impact="Potential score improvement: +15 points",
                    actions=[
                        "Enable automatic payments",
                        "Set up strict reminders",
                        "Maintain a balance buffer"
                    ],
                )
            ]
        elif 21 <= score <= 40:
            return [
                Recommendation(
                    priority="high",
                    title="Improve Bill Payment Consistency",
                    description="Late payments reduce behavioral score and investor confidence.",
                    impact="Potential score improvement: +12 points",
                    actions=[
                        "Pay all obligations on time",
                        "Set reminders for key bills",
                        "Maintain a balance buffer"
                    ],
                ),
                Recommendation(
                    priority="medium",
                    title="Build Creditworthiness",
                    description="Consistent behavioral patterns improve financial responsibility perception.",
                    impact="Potential score improvement: +8 points",
                    actions=[
                        "Limit late payments",
                        "Maintain stable income-to-expense ratio",
                        "Avoid unnecessary debts"
                    ],
                )
            ]
        elif 41 <= score <= 60:
            return [
                Recommendation(
                    priority="medium",
                    title="Maintain Behavioral Consistency",
                    description="Moderate behavioral score; focus on reliable patterns for investors.",
                    impact="Potential score improvement: +5 points",
                    actions=[
                        "Continue timely payments",
                        "Track recurring bills",
                        "Document financial behavior"
                    ],
                )
            ]
        elif 61 <= score <= 80:
            return [
                Recommendation(
                    priority="low",
                    title="Enhance Behavioral Transparency",
                    description="Good behavioral score; maintain consistency and transparency.",
                    impact="Potential score improvement: +3 points",
                    actions=[
                        "Share behavioral records selectively",
                        "Keep track of key transactions",
                        "Maintain timely payments"
                    ],
                )
            ]
        else:  # 81-100
            return [
                Recommendation(
                    priority="low",
                    title="Optimize Behavioral Influence",
                    description="Excellent behavioral patterns; focus on strategic financial behavior.",
                    impact="Potential score improvement: +2 points",
                    actions=[
                        "Model best practices for peers",
                        "Document consistent behavioral patterns",
                        "Leverage positive behavior for investor trust"
                    ],
                )
            ]

    return []


def get_csv_path(customer_id: str, file_type: str):
    """
    Example:
    uploads/
        123_cdr.csv
        123_transactions.csv
    """
    return os.path.join(DATA_DIR, f"{customer_id}_{file_type}.csv")
