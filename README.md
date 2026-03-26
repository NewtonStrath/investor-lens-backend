# ⚙️ Investment Readiness Scoring System (Backend API)

## 📌 Overview

This project is the **backend service** for the Investment Readiness Scoring System developed as part of a Master’s
dissertation:

**“Design and Evaluation of a Data-Driven Scoring Model for Enhancing Investment Readiness among Low-Income Earners in
Emerging Economies.”**

The backend is responsible for **data processing, feature engineering, model execution, and score generation** using
simulated mobile money and behavioural data.

---

## 🎯 Purpose

The backend system is designed to:

- Process uploaded **transaction and CDR datasets**
- Perform **feature engineering** on behavioural data
- Generate **investment readiness scores**
- Expose APIs for frontend interaction
- Support experimentation with **machine learning models**

---

## 🧠 Core Functionality

- 📂 **Data Ingestion**
    - Accepts CSV uploads (transactions & CDR data)

- 🧹 **Data Preprocessing**
    - Handles missing values
    - Normalizes and scales features

- 🧮 **Feature Engineering**
    - Extracts behavioural indicators such as:
        - Transaction frequency
        - Balance stability
        - Spending patterns
        - Communication activity (CDR)

- 🤖 **Model Inference**
    - Loads trained machine learning model
    - Generates **investment readiness score**

- 📊 **API Responses**
    - Returns:
        - Score
        - Feature contributions
        - Insights

---

## 🛠️ Tech Stack

- **Python 3.10+**
- **FastAPI** – API framework
- **Pandas** – Data processing
- **NumPy** – Numerical operations
- **Scikit-learn** – Machine learning
- **Joblib** – Model serialization
- **Uvicorn** – ASGI server

---

## 📁 Project Structure

backend/
│── app/
│ │── main.py # FastAPI entry point
│ │── routes/ # API endpoints
│ │── services/ # Business logic
│ │── models/ # ML model loading
│ │── utils/ # Helper functions
│ │── schemas/ # Pydantic models
│
│── data/ # Sample/simulated datasets
│── notebooks/ # Model training notebooks
│── saved_models/ # Serialized models (.joblib)
│── requirements.txt # Dependencies


---

## 🚀 Getting Started

### 1. Clone Repository

```bash
git clone <your-repo-link>
cd backend
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt      # Windows
```

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

Server will run on

```bash
http://127.0.0.1:8000
```

### 📊 Data Disclaimer
- All data is simulated
- No real user data is used
- Designed to be privacy-preserving
### 🎓 Academic Context

This project is part of a Master’s dissertation at:

**Strathmore University – School of Computing and Engineering Sciences**

### Focus areas:

- Financial Inclusion
- Alternative Data
- Machine Learning in FinTech
### ⚠️ Limitations
- Prototype only
- Uses simulated data
- Not production-ready
### 🔮 Future Work
- Backend integration
- Real-time scoring
- Improved visualizations
- Cloud deployment
### 👤 Author

Newton Kipngeno