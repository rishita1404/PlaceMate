# PlaceMate AI

> **Prepare Smarter. Apply Faster. Get Career-Ready.**

PlaceMate AI is an AI-assisted career discovery and job application preparation platform tailored for college students, interns, and fresh graduates. It brings together resume analysis, explainable job matching, eligibility verification, interview preparation, and end-to-end application tracking in one unified interface.

---

## 🌟 Key Features

1. **🔐 Authentication & Role Management**
   - Secure student registration and login with JWT access tokens and bcrypt password hashing.
   - Separation of student workflows and administrative management.

2. **👤 Verified Career Profile**
   - Structured academic records (institution, degree, graduation year, GPA/percentage).
   - Skills inventory, verified work experience, academic projects, and certifications.
   - Explicit student confirmation workflow to ensure only verified data powers matching.

3. **📄 Resume Parser (PyMuPDF)**
   - Text extraction from text-based PDF resumes with page count detection.
   - Rejection of scanned/image-only PDFs with clear feedback for manual entry or re-export.

4. **🎯 Transparent Job Matching**
   - Deterministic, explainable compatibility scoring (required skills: 50%, preferred skills: 20%, experience: 30%).
   - Detailed breakdown showing matched vs. missing skills and supporting student projects.

5. **✔️ Placement Eligibility Engine**
   - Verification of general criteria (degree, graduation year cutoff, minimum GPA).
   - College-specific placement constraint verification.

6. **💡 Interview Preparation**
   - Practice questions organized by provenance: source-backed past interview questions, AI-generated practice questions, and community submissions.

7. **📊 Application Tracker**
   - Lifecycle tracking: `draft`, `applied`, `submitted_confirmed`, `under_review`, `interview_scheduled`, `offer`, `rejected`, `withdrawn`.
   - Requires receipt/reference numbers for confirmed submissions.

8. **⚙️ Admin Console**
   - Manual job listing importation and college eligibility rules management.

---

## 🏗️ Architecture

```text
PlaceMate/
├── app/
│   ├── api/             # FastAPI REST endpoints (auth, profiles, resumes, jobs, applications, admin)
│   ├── integrations/    # External AI clients (Azure AI / Gemini)
│   ├── services/        # Business logic (matching, eligibility, resume parsing, interview prep)
│   ├── ui/              # Streamlit frontend
│   │   ├── app.py       # Streamlit entry point
│   │   ├── api_client.py# HTTP client connecting UI to FastAPI backend
│   │   └── views/       # Modular view renderers (auth, dashboard, profile, resume, jobs, tracker, admin)
│   ├── models.py        # SQLAlchemy ORM models
│   ├── schemas.py       # Pydantic v2 schemas
│   ├── config.py        # Centralized settings loaded via pydantic-settings
│   └── database.py      # Async SQLite session management
├── data/
│   ├── sample_jobs.json # Seed job opportunities
│   └── seed.py          # Database seeding script
├── tests/               # Pytest automated test suite
├── requirements.txt     # Python dependencies
└── pyproject.toml       # Project configuration
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.12+
- macOS / Linux / Windows

### 2. Environment Setup
Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create your `.env` configuration:
```bash
cp .env.example .env
```

### 3. Seed Database
Initialize tables and load starter opportunities:
```bash
python -m data.seed
```

### 4. Run the Backend API
Start the FastAPI server:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```
Interactive Swagger docs: `http://127.0.0.1:8002/docs`

### 5. Run the Frontend UI
In a separate terminal, start Streamlit:
```bash
streamlit run app/ui/app.py --server.port 8501
```
Open `http://localhost:8501` in your browser.

---

## 🧪 Testing

Run the automated test suite (39/39 passing):

```bash
pytest tests/ -v
```

---

## 🛡️ Privacy & Security
- Passwords hashed using bcrypt.
- Secrets and uploaded PDF resumes are excluded from Git via `.gitignore`.
- Resume text is securely stored and never exposed across student accounts.
