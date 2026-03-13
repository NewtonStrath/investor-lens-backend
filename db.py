from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, Date, create_engine, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

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


# ---------------- DB DEPENDENCY ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Base = declarative_base()


class ScoreMetricDB(Base):
    __tablename__ = "score_metrics"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    category = Column(String)
    metric_label = Column(String)
    value = Column(Integer)
    metric_date = Column(Date)


# ---------------- USER MODEL ----------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)


class CDRFeatureDB(Base):
    __tablename__ = "cdr_features"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, index=True)

    total_calls = Column(Integer)
    avg_call_duration = Column(Float)
    unique_contacts = Column(Integer)


class TransactionFeatureDB(Base):
    __tablename__ = "transaction_features"

    id = Column(Integer, primary_key=True, index=True)

    customer_id = Column(Integer, index=True, nullable=False)

    total_transactions = Column(Integer, nullable=False)
    total_amount = Column(Float, nullable=False)
    avg_transaction = Column(Float, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
