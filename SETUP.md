# ProofLedger — Quick Setup & Installation Guide

## 1. Prerequisites
- **Python**: 3.9+
- **Node.js**: 18+ (with npm)
- **PayPal Developer Account**: Sandbox client ID and secret (configured in `.env`)

---

## 2. Quickstart

### Backend Setup
```bash
# Clone the repository
cd /path/to/paypal

# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI server from repo root (Port 8000)
python3 -m uvicorn backend.main:app --reload --port 8000
```

### Frontend Setup
```bash
# In a new terminal window:
cd frontend

# Install Node dependencies
npm install

# Start Vite development server (Port 5173)
npm run dev
```

### Accessing the Application
- Open your browser to `http://localhost:5173`.
- Backend Swagger documentation available at `http://localhost:8000/docs`.

---

## 3. Running Test Suites
```bash
# Run full unique test suite across ai/tests and backend (324 tests)
python3 -m pytest ai/tests/ backend/ -q

# Run specialized PayPal Dispute Rescue + Final Sprint tests (22 tests)
python3 -m pytest backend/test_paypal_dispute_rescue_suite.py backend/test_sprint_final_features.py -v

# Run live headless Chrome E2E browser workflow check (requires backend :8000 & frontend :5173)
python3 scripts/e2e_browser_verify.py
```

