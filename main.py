from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from datetime import datetime, timedelta
import jwt  # pip install pyjwt
import random

# ---------------- FastAPI App ----------------
app = FastAPI(title="Investment Readiness System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- DATABASE ----------------
DATABASE_URL = "sqlite:///./users.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# ---------------- JWT CONFIG ----------------
JWT_SECRET = "super-secret-key"  # Use environment variable in production
JWT_ALGORITHM = "HS256"
JWT_EXP_MINUTES = 60

vehicles = [
    {
        "id": "v1",
        "registrationNumber": "KBA 123A",
        "model": "Mercedes Actros",
        "capacity": "20T",
        "status": "On Trip",
        "currentDriverId": "d1",
        "lastServiceDate": "2023-09-15",
        "nextServiceDate": "2023-12-15",
        "insuranceExpiry": "2024-01-20",
        "fuelEfficiency": 3.2,
        "totalDistance": 125000,
        "location": { "lat": -1.2921, "lng": 36.8219 }
    },
    {
        "id": "v2",
        "registrationNumber": "KBC 456B",
        "model": "Scania R450",
        "capacity": "25T",
        "status": "Available",
        "lastServiceDate": "2023-10-01",
        "nextServiceDate": "2024-01-01",
        "insuranceExpiry": "2024-02-15",
        "fuelEfficiency": 3.5,
        "totalDistance": 98000,
        "location": { "lat": -4.0435, "lng": 39.6682 }
    }
]

def create_jwt(user_id: int, email: str):
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXP_MINUTES)
    payload = {"sub": user_id, "email": email, "exp": expire}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def verify_jwt(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------- USER MODEL ----------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)  # plain text (insecure!)

Base.metadata.create_all(bind=engine)

# ---------------- Pydantic Schemas ----------------
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# ---------------- AUTH DEPENDENCY ----------------
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_jwt(credentials.credentials)
    db: Session = SessionLocal()
    user = db.query(User).filter(User.id == payload["sub"]).first()
    db.close()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# ---------------- ROUTES ----------------
@app.post("/register")
def register(data: RegisterRequest):
    db: Session = SessionLocal()
    if db.query(User).filter(User.email == data.email).first():
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        name=data.name,
        email=data.email,
        password=data.password  # stored in plain text (not secure)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()
    return {"message": "User created successfully", "user": {"id": new_user.id, "name": new_user.name, "email": new_user.email}}

@app.post("/login")
def login(data: LoginRequest):
    db: Session = SessionLocal()
    user = db.query(User).filter(User.email == data.email).first()
    db.close()
    if not user or user.password != data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_jwt(user.id, user.email)
    return {"token": token, "user": {"id": user.id, "name": user.name, "email": user.email}}

@app.get("/dashboard")
def get_dashboard(current_user: User = Depends(get_current_user)):
    MOCK_DATA = {
        "overallScore": 10,
        "categories": [
            {
                "title": "CDR Score Card",
                "score": 65,
                "subMetrics": [
                    {"label": "Call Frequency", "value": 60},
                    {"label": "SMS Frequency", "value": 40},
                    {"label": "Avg Call Duration", "value": 83},
                    {"label": "Unique Calls", "value": 60},
                ],
            },
            {
                "title": "Transaction Score Card",
                "score": 10,
                "subMetrics": [
                    {"label": "Inflow Frequency", "value": 80},
                    {"label": "Outflow Frequency", "value": 60},
                    {"label": "Transaction Diversity", "value": 87},
                ],
            },
            {
                "title": "Behavioral Score Card",
                "score": 55,
                "subMetrics": [
                    {"label": "Bill Payment", "value": 66},
                    {"label": "Savings Activity", "value": 50},
                    {"label": "Other Behavior", "value": 60},
                ],
            },
        ],
        "lastUpdated": "2026-01-15T14:34:00"
    }
    return MOCK_DATA

@app.get("/vehicles/{vehicle_id}/location")
def get_vehicle_location(vehicle_id: str):
    # Replace with DB or GPS provider call
    return {
        "vehicleId": vehicle_id,
        "lat": -1.2921 + random.uniform(-0.01, 0.01),
        "lng": 36.8219 + random.uniform(-0.01, 0.01),
        "speed": random.randint(0, 90),
        "heading": random.randint(0, 360),
        "updatedAt": datetime.utcnow()
    }

@app.get("/vehicles/{vehicle_id}/location")
def get_vehicle_location(vehicle_id: str):
    # Replace with DB or GPS provider call
    return {
        "vehicleId": vehicle_id,
        "lat": -1.2921 + random.uniform(-0.01, 0.01),
        "lng": 36.8219 + random.uniform(-0.01, 0.01),
        "speed": random.randint(0, 90),
        "heading": random.randint(0, 360),
        "updatedAt": datetime.utcnow()
    }

def move_vehicle(v):
    if v["status"] == "On Trip":
        v["location"]["lat"] += random.uniform(-0.01, 0.01)
        v["location"]["lng"] += random.uniform(-0.01, 0.01)

@app.get("/vehicles")
def get_vehicles():
    for v in vehicles:
        move_vehicle(v)
    return vehicles