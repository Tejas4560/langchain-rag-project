from fastapi import FastAPI, UploadFile, File, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
from typing import List, Optional
import shutil
import os
import logging
from pathlib import Path

from rag import (
    get_rag_chain, 
    ingest_uploaded_files, 
    validate_environment,
    RAGException
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

import auth
from fastapi_sso.sso.google import GoogleSSO
from starlette.requests import Request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Document Assistant API",
    description="API for document-based question answering using RAG",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://172.29.172.179:3000",  # 👈 ADD THIS
        "http://frontend:80",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Google SSO
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Use BASE_URL environment variable if set, otherwise default to localhost for dev
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
google_sso = GoogleSSO(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, f"{BASE_URL}/auth/google/callback")


# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "data")
VECTOR_DB_PATH = os.path.join(BASE_DIR, "vectorstore", "db_faiss")

# Configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
ALLOWED_EXTENSIONS = {".pdf"}

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(VECTOR_DB_PATH), exist_ok=True)

class QuestionRequest(BaseModel):
    question: str
    
    @validator('question')
    def question_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Question cannot be empty')
        if len(v) > 1000:
            raise ValueError('Question too long (max 1000 characters)')
        return v.strip()

# Custom exception handler
@app.exception_handler(RAGException)
async def rag_exception_handler(request, exc: RAGException):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": str(exc), "type": "RAGException"}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "type": "HTTPException"}
    )

@app.on_event("startup")
async def startup_event():
    """Validate environment on startup"""
    try:
        validate_environment()
        logger.info("Application started successfully")
    except RAGException as e:
        logger.error(f"Startup validation failed: {e}")
        # Continue anyway but log the error

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "message": "RAG Document Assistant API",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    """Detailed health check"""
    has_documents = os.path.exists(VECTOR_DB_PATH) and os.path.isdir(VECTOR_DB_PATH)
    uploaded_files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith('.pdf')] if os.path.exists(UPLOAD_DIR) else []
    
    return {
        "status": "healthy",
        "vector_store_ready": has_documents,
        "uploaded_files_count": len(uploaded_files),
        "groq_api_configured": bool(os.getenv("GROQ_API_KEY"))
    }

@app.post("/register", response_model=auth.UserResponse)
def register_user(user: auth.UserCreate, db: Session = Depends(auth.get_db)):
    db_user = db.query(auth.User).filter(auth.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = auth.get_password_hash(user.password)
    db_user = auth.User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/token", response_model=auth.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(auth.get_db)):
    user = db.query(auth.User).filter(auth.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}



@app.get("/auth/google/login")
async def google_login():
    """Redirect to Google Login"""
    return await google_sso.get_login_redirect()


@app.get("/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(auth.get_db)):
    """Process login response from Google and return user info"""
    try:
        user_info = await google_sso.verify_and_process(request)
        if not user_info:
             raise HTTPException(status_code=400, detail="Failed to login with Google")
    except Exception as e:
         raise HTTPException(status_code=400, detail=str(e))
    
    # Check if user exists
    # GoogleSSO returns email as ID usually or we match by email
    user_email = user_info.email
    db_user = db.query(auth.User).filter(auth.User.email == user_email).first()
    
    if not db_user:
        # Create new user
        # We use email as username or part of it for now
        username = user_email.split("@")[0]
        # ensure username uniqueness
        if db.query(auth.User).filter(auth.User.username == username).first():
            username = f"{username}_{os.urandom(4).hex()}"
            
        db_user = auth.User(
            username=username,
            email=user_email,
            hashed_password=None,
            provider="google"
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    
    # Create JWT token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": db_user.username}, expires_delta=access_token_expires
    )
    
    # Redirect to frontend with token
    # Adjust valid frontend URL as needed
    frontend_base_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    # Aggressive sanitation: remove trailing slash and specific paths like /login
    frontend_base_url = frontend_base_url.rstrip("/")
    if frontend_base_url.endswith("/login"):
        frontend_base_url = frontend_base_url[:-6] # Remove /login
    
    frontend_url = f"{frontend_base_url}/auth/callback?token={access_token}&username={db_user.username}"
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=frontend_url)
@app.post("/ask")
async def ask_question(req: QuestionRequest, current_user: auth.User = Depends(auth.get_current_active_user)):
    try:
        retriever, llm, prompt = get_rag_chain()

        docs = retriever.invoke(req.question)

        if not docs:
            return {
                "answer": "I could not find relevant information in the uploaded documents.",
                "sources": []
            }

        # FIX-1: Clean & limit context
        seen = set()
        clean_chunks = []

        for doc in docs:
            text = doc.page_content.strip()
            if text not in seen:
                clean_chunks.append(text)
                seen.add(text)

        context = "\n\n".join(clean_chunks[:3])

        response = llm.invoke(
            prompt.format(context=context, question=req.question)
        )

        # FIX-3: Clean answer output
        raw_answer = response.content.strip()
        unique_lines = []

        for line in raw_answer.splitlines():
            if line.strip() and line not in unique_lines:
                unique_lines.append(line)

        final_answer = "\n".join(unique_lines)

        # sources
        sources = []
        for doc in docs:
            src = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "N/A")
            sources.append(f"{os.path.basename(src)} — page {page}")

        return {
            "answer": final_answer,
            "sources": list(dict.fromkeys(sources))[:5]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...), 
    current_user: auth.User = Depends(auth.get_current_active_user)
):
    """
    Upload and index PDF files
    
    Args:
        files: List of PDF files to upload
        
    Returns:
        JSON with upload status and indexed file names
    """
    try:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files provided"
            )
        
        logger.info(f"Received {len(files)} files for upload")
        uploaded_filenames = []
        errors = []
        
        # Validate and save files
        for file in files:
            try:
                # Validate file extension
                file_ext = Path(file.filename).suffix.lower()
                if file_ext not in ALLOWED_EXTENSIONS:
                    errors.append(f"{file.filename}: Invalid file type (only PDF allowed)")
                    continue
                
                # Validate file size
                file.file.seek(0, 2)  # Seek to end
                file_size = file.file.tell()
                file.file.seek(0)  # Reset to beginning
                
                if file_size > MAX_FILE_SIZE:
                    errors.append(f"{file.filename}: File too large (max 50MB)")
                    continue
                
                if file_size == 0:
                    errors.append(f"{file.filename}: Empty file")
                    continue
                
                # Sanitize filename
                safe_filename = "".join(c for c in file.filename if c.isalnum() or c in ".-_ ")
                file_path = os.path.join(UPLOAD_DIR, safe_filename)
                
                # Save file
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                uploaded_filenames.append(safe_filename)
                logger.info(f"Saved file: {safe_filename}")
                
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {e}")
                errors.append(f"{file.filename}: {str(e)}")
        
        if not uploaded_filenames:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No files were uploaded successfully. Errors: {'; '.join(errors)}"
            )
        
        # Index uploaded files
        try:
            result = ingest_uploaded_files()
            logger.info("Files indexed successfully")
            
            response = {
                "message": result["message"],
                "files": uploaded_filenames,
                "chunks": result["chunks"],
                "errors": errors if errors else None
            }
            
            if result.get("failed_files"):
                response["failed_files"] = result["failed_files"]
            
            return response
            
        except RAGException as e:
            # Clean up uploaded files if indexing fails
            for filename in uploaded_filenames:
                try:
                    os.remove(os.path.join(UPLOAD_DIR, filename))
                except:
                    pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Indexing failed: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in upload_files: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during upload"
        )

@app.post("/reset")
async def reset_knowledge_base(current_user: auth.User = Depends(auth.get_current_active_user)):
    """
    Clear all uploaded documents and vector store
    
    Returns:
        JSON with reset status
    """
    try:
        deleted_files = 0
        
        # Remove vector store
        if os.path.exists(VECTOR_DB_PATH):
            shutil.rmtree(VECTOR_DB_PATH)
            logger.info("Removed vector store")
        
        # Remove uploaded files
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        deleted_files += 1
                except Exception as e:
                    logger.error(f"Error deleting {filename}: {e}")
        
        logger.info(f"Knowledge base reset: {deleted_files} files deleted")
        
        return {
            "message": "Knowledge base cleared successfully",
            "files_deleted": deleted_files
        }
        
    except Exception as e:
        logger.error(f"Error resetting knowledge base: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset knowledge base"
        )

@app.get("/files")
async def list_files(current_user: auth.User = Depends(auth.get_current_active_user)):
    """
    List all uploaded files
    
    Returns:
        JSON with list of uploaded files
    """
    try:
        if not os.path.exists(UPLOAD_DIR):
            return {"files": []}
        
        files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith('.pdf')]
        
        return {
            "files": files,
            "count": len(files)
        }
        
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list files"
        )