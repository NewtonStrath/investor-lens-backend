# --- Models ---
from typing import List, Literal

from pydantic import BaseModel, EmailStr


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


# ---------------- Pydantic Schemas ----------------
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Recommendation(BaseModel):
    priority: Literal["high", "medium", "low"]
    title: str
    description: str
    impact: str
    actions: List[str]


class RecommendationRequest(BaseModel):
    score: int


class RecommendationResponse(BaseModel):
    recommendations: List[Recommendation]

class ProcessRequest(BaseModel):
    customer_id: str