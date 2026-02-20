from typing import List, Dict

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel, EmailStr
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext

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

# ---------------- DATABASE ----------------
DATABASE_URL = "postgresql+psycopg2://investor_lens_user:StrongInvestorLens%40123@localhost:5432/investor_lens_db"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------------- JWT CONFIG ----------------
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key")
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


# ---------------- USER MODEL ----------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)


# Create tables
Base.metadata.create_all(bind=engine)


# ---------------- Pydantic Schemas ----------------
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ---------------- DB DEPENDENCY ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


# ---------------- ROUTES ----------------

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


# --- Models ---
class SubMetric(BaseModel):
    label: str
    value: int


class Category(BaseModel):
    title: str
    score: int
    type: str  # 'cdr' | 'transaction' | 'behavioral'
    subMetrics: List[SubMetric]


class DashboardScoreResponse(BaseModel):
    overallScore: int
    categories: List[Category]


class ScoreHistoryItem(BaseModel):
    id: str
    date: str
    overall: int
    cdr: int
    transaction: int
    behavioral: int
    change: int


# --- Mock Data ---
MOCK_CATEGORIES = [
    Category(
        title="CDR Score Card",
        score=65,
        type="cdr",
        subMetrics=[
            SubMetric(label="Call Frequency", value=60),
            SubMetric(label="SMS Frequency", value=40),
            SubMetric(label="Avg Call Duration", value=83),
        ],
    ),
    Category(
        title="Transaction Score Card",
        score=70,
        type="transaction",
        subMetrics=[
            SubMetric(label="Inflow Frequency", value=80),
            SubMetric(label="Outflow Frequency", value=60),
            SubMetric(label="Transaction Diversity", value=87),
        ],
    ),
    Category(
        title="Behavioral Score Card",
        score=55,
        type="behavioral",
        subMetrics=[
            SubMetric(label="Bill Payment", value=66),
            SubMetric(label="Savings Activity", value=50),
            SubMetric(label="Other Behavior", value=60),
        ],
    ),
]

MOCK_SCORE_HISTORY = [
    ScoreHistoryItem(id="1", date="Jan 15, 2026", overall=75, cdr=65, transaction=70, behavioral=55, change=4),
    ScoreHistoryItem(id="2", date="Dec 15, 2025", overall=71, cdr=62, transaction=68, behavioral=52, change=6),
    ScoreHistoryItem(id="3", date="Nov 15, 2025", overall=65, cdr=58, transaction=63, behavioral=48, change=-2),
    ScoreHistoryItem(id="4", date="Oct 15, 2025", overall=67, cdr=60, transaction=65, behavioral=50, change=3),
]

USER_DATA: Dict[str, Dict] = {
    "5": {  # user id "1"
        "categories": [
            Category(
                title="CDR Score Card",
                score=10,
                type="cdr",
                subMetrics=[
                    SubMetric(label="Call Frequency", value=60),
                    SubMetric(label="SMS Frequency", value=40),
                    SubMetric(label="Avg Call Duration", value=83),
                ],
            ),
            Category(
                title="Transaction Score Card",
                score=10,
                type="transaction",
                subMetrics=[
                    SubMetric(label="Inflow Frequency", value=80),
                    SubMetric(label="Outflow Frequency", value=60),
                    SubMetric(label="Transaction Diversity", value=87),
                ],
            ),
            Category(
                title="Behavioral Score Card",
                score=10,
                type="behavioral",
                subMetrics=[
                    SubMetric(label="Bill Payment", value=66),
                    SubMetric(label="Savings Activity", value=50),
                    SubMetric(label="Other Behavior", value=60),
                ],
            ),
        ],
        "history": [
            ScoreHistoryItem(id="1", date="Jan 15, 2026", overall=75, cdr=65, transaction=70, behavioral=55, change=4),
            ScoreHistoryItem(id="2", date="Dec 15, 2025", overall=71, cdr=62, transaction=68, behavioral=52, change=6),
            ScoreHistoryItem(id="3", date="Nov 15, 2025", overall=65, cdr=58, transaction=63, behavioral=48, change=-2),
            ScoreHistoryItem(id="4", date="Oct 15, 2025", overall=67, cdr=60, transaction=65, behavioral=50, change=3),
        ]
    },
    "2": {  # another user example
        "categories": [
            Category(
                title="CDR Score Card",
                score=80,
                type="cdr",
                subMetrics=[
                    SubMetric(label="Call Frequency", value=85),
                    SubMetric(label="SMS Frequency", value=75),
                    SubMetric(label="Avg Call Duration", value=90),
                ],
            ),
            Category(
                title="Transaction Score Card",
                score=60,
                type="transaction",
                subMetrics=[
                    SubMetric(label="Inflow Frequency", value=70),
                    SubMetric(label="Outflow Frequency", value=65),
                    SubMetric(label="Transaction Diversity", value=55),
                ],
            ),
            Category(
                title="Behavioral Score Card",
                score=50,
                type="behavioral",
                subMetrics=[
                    SubMetric(label="Bill Payment", value=50),
                    SubMetric(label="Savings Activity", value=45),
                    SubMetric(label="Other Behavior", value=55),
                ],
            ),
        ],
        "history": [
            ScoreHistoryItem(id="1", date="Jan 15, 2026", overall=70, cdr=80, transaction=60, behavioral=50, change=2),
            ScoreHistoryItem(id="2", date="Dec 15, 2025", overall=68, cdr=78, transaction=62, behavioral=48, change=1),
        ]
    }
}


# --- Routes ---
@app.get("/api/dashboard/score", response_model=DashboardScoreResponse)
def get_dashboard_score(user_id: str = Query(..., description="ID of the user")):
    user_data = USER_DATA.get(user_id)
    print(user_data)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    categories: List[Category] = user_data["categories"]
    overall_score = sum(cat.score for cat in categories) // len(categories)
    return {"overallScore": overall_score, "categories": categories}

@app.get("/api/dashboard/history", response_model=List[ScoreHistoryItem])
def get_dashboard_history(user_id: str = Query(..., description="ID of the user")):
    user_data = USER_DATA.get(user_id)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    return user_data["history"]
