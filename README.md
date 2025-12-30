# LangChain RAG Project

This project is a React + FastAPI application for performing RAG (Retrieval Augmented Generation) on PDF documents.

## Authentication
The application uses JWT-based authentication.
- **Login**: `/login`
- **Register**: `/register`
- **Protected Routes**: Main Dashboard

## Prerequisites
- Python 3.9+
- Node.js 16+

## Setup & Running

### 1. Backend
Open a terminal and run:
```bash
cd backend
# Activate virtual environment
source ../venv/bin/activate
# Install dependencies (if not already done)
pip install -r ../requirements.txt
# Run server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend
Open a NEW terminal and run:
```bash
cd frontend
# Install dependencies (if not already done)
npm install
# Start React App
npm start
```

## Usage
1. Go to `http://localhost:3000`
2. Register a new account.
3. Loog in.
4. Upload PDFs and ask questions.
