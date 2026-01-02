from dotenv import load_dotenv
import os
import shutil
import logging
from typing import Optional

load_dotenv()

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Absolute paths with better error handling
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
VECTOR_DB_PATH = os.path.join(BASE_DIR, "vectorstore", "db_faiss")

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.dirname(VECTOR_DB_PATH), exist_ok=True)

# Configuration
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = "llama-3.1-8b-instant"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
RETRIEVAL_K = 5

class RAGException(Exception):
    """Custom exception for RAG operations"""
    pass

def get_embeddings():
    """Get embeddings model with error handling"""
    try:
        return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    except Exception as e:
        logger.error(f"Failed to load embeddings model: {e}")
        raise RAGException(f"Embeddings model initialization failed: {e}")

def get_rag_chain():
    """Initialize and return RAG chain components"""
    try:
        # Check if vector store exists
        if not os.path.exists(VECTOR_DB_PATH):
            raise RAGException("Vector store not found. Please upload documents first.")
        
        embeddings = get_embeddings()
        
        # Load vector store with error handling
        try:
            db = FAISS.load_local(
                VECTOR_DB_PATH,
                embeddings,
                
            )
        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            raise RAGException("Failed to load document index. Please re-upload your documents.")
        
        retriever = db.as_retriever(search_kwargs={"k": RETRIEVAL_K})
        
        # Initialize LLM with error handling
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RAGException("GROQ_API_KEY not found in environment variables")
        
        try:
            llm = ChatGroq(
                model=LLM_MODEL,
                temperature=0,
                api_key=api_key
            )
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise RAGException(f"Failed to initialize language model: {e}")
        
        prompt = ChatPromptTemplate.from_template(
"""
You are an expert technical assistant.

TASK:
- Answer the question using the context below
- Provide ONE clear, concise answer
- DO NOT repeat the same sentence
- DO NOT copy text verbatim multiple times
- Summarize when information is repeated
- If multiple chunks say the same thing, say it ONCE

Context:
{context}

Question:
{question}

Answer (clear, concise, no repetition):
"""
)

        
        logger.info("RAG chain initialized successfully")
        return retriever, llm, prompt
        
    except RAGException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_rag_chain: {e}")
        raise RAGException(f"Failed to initialize RAG chain: {e}")

def ingest_uploaded_files():
    """Process and index uploaded PDF files"""
    try:
        # Check if data directory has files
        pdf_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".pdf")]
        
        if not pdf_files:
            raise RAGException("No PDF files found to process")
        
        logger.info(f"Processing {len(pdf_files)} PDF files")
        documents = []
        failed_files = []
        
        # Load documents with individual error handling
        for file in pdf_files:
            try:
                file_path = os.path.join(DATA_DIR, file)
                loader = PyPDFLoader(file_path)
                docs = loader.load()
                
                if not docs:
                    logger.warning(f"No content extracted from {file}")
                    failed_files.append(file)
                    continue
                    
                documents.extend(docs)
                logger.info(f"Successfully loaded {file} ({len(docs)} pages)")
            except Exception as e:
                logger.error(f"Failed to load {file}: {e}")
                failed_files.append(file)
        
        if not documents:
            raise RAGException("No content could be extracted from the uploaded files")
        
        # Split documents
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        docs = splitter.split_documents(documents)
        logger.info(f"Created {len(docs)} text chunks")
        
        if not docs:
            raise RAGException("Document splitting resulted in no chunks")
        
        # Create embeddings and vector store
        embeddings = get_embeddings()
        
        # Remove old vector store if exists
        if os.path.exists(VECTOR_DB_PATH):
            shutil.rmtree(VECTOR_DB_PATH)
            logger.info("Removed old vector store")
        
        # Create new vector store
        db = FAISS.from_documents(docs, embeddings)
        db.save_local(VECTOR_DB_PATH)
        
        logger.info(f"Successfully indexed {len(pdf_files)} files into {len(docs)} chunks")
        
        if failed_files:
            logger.warning(f"Failed to process: {', '.join(failed_files)}")
            return {
                "success": True,
                "message": f"Indexed {len(pdf_files) - len(failed_files)} files successfully",
                "chunks": len(docs),
                "failed_files": failed_files
            }
        
        return {
            "success": True,
            "message": f"Successfully indexed {len(pdf_files)} files",
            "chunks": len(docs),
            "failed_files": []
        }
        
    except RAGException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during ingestion: {e}")
        raise RAGException(f"Document indexing failed: {e}")

def validate_environment():
    """Validate required environment variables and dependencies"""
    errors = []
    
    if not os.getenv("GROQ_API_KEY"):
        errors.append("GROQ_API_KEY not found in environment")
    
    if not os.path.exists(DATA_DIR):
        errors.append(f"Data directory not found: {DATA_DIR}")
    
    if errors:
        raise RAGException(f"Environment validation failed: {', '.join(errors)}")
    
    logger.info("Environment validation passed")
    return True