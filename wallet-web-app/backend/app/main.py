"""
FastAPI backend for PDF to Wallet conversion.
"""

import json
import logging
import os
import re
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .services.pdf_service import PDFService
from .services.email_service import EmailService
from .services.rate_limiter import RateLimiter

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PDF to Wallet API",
    description="Convert PDF tickets to Apple Wallet passes",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Initialize services
pdf_service = PDFService()
email_service = EmailService()
rate_limiter = RateLimiter(max_requests=5, window_seconds=300)  # 5 requests per 5 minutes

# Constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME_TYPES = {"application/pdf"}


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def validate_email(email: str) -> bool:
    """Basic RFC 5322 email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal"""
    if not filename:
        return "upload.pdf"
    
    # Remove path separators and dangerous characters
    safe_chars = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Ensure it has pdf extension
    if not safe_chars.lower().endswith('.pdf'):
        safe_chars += '.pdf'
    
    return safe_chars[:100]  # Limit length


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "PDF to Wallet API"}


@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "services": {
            "email": email_service.has_sendgrid,
            "pdf_processor": pdf_service.processor is not None
        }
    }


@app.post("/api/process")
async def process_pdf(
    request: Request,
    file: UploadFile = File(...),
    email: str = Form(...)
):
    """
    Process PDF and email wallet JSON.
    
    Args:
        file: PDF file upload
        email: Email address to send result to
    
    Returns:
        Success/error response
    """
    client_ip = get_client_ip(request)
    
    try:
        # Rate limiting
        if not rate_limiter.is_allowed(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=429,
                detail={
                    "ok": False,
                    "error": "Too many requests. Please try again later.",
                    "reset_time": rate_limiter.get_reset_time(client_ip)
                }
            )
        
        # Validate email
        if not email or not validate_email(email):
            raise HTTPException(
                status_code=400,
                detail={"ok": False, "error": "Invalid email address format"}
            )
        
        # Validate file presence
        if not file:
            raise HTTPException(
                status_code=400,
                detail={"ok": False, "error": "No file provided"}
            )
        
        # Validate file type
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail={"ok": False, "error": "Only PDF files are allowed"}
            )
        
        # Read file content
        file_content = await file.read()
        
        # Validate file size
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail={"ok": False, "error": "File size exceeds 10MB limit"}
            )
        
        if len(file_content) == 0:
            raise HTTPException(
                status_code=400,
                detail={"ok": False, "error": "Empty file provided"}
            )
        
        # Sanitize filename for logging
        safe_filename = sanitize_filename(file.filename or "upload.pdf")
        
        # Log processing start
        logger.info(f"Processing PDF: {safe_filename}, size: {len(file_content)} bytes, client: {client_ip}")
        
        # Process PDF
        try:
            # Get configuration from environment variables
            organization = os.getenv("WALLET_ORGANIZATION", "Wallet App")
            pass_type_id = os.getenv("WALLET_PASS_TYPE_ID", "pass.com.walletapp.generic")
            team_id = os.getenv("WALLET_TEAM_ID", "DEMO123456")
            use_llm = os.getenv("OPENAI_API_KEY") is not None
            
            wallet_data = pdf_service.pdf_to_wallet(
                pdf_bytes=file_content,
                organization=organization,
                pass_type_id=pass_type_id,
                team_id=team_id,
                use_llm=use_llm
            )
            if not wallet_data:
                raise ValueError("PDF processing returned empty result")
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            raise HTTPException(
                status_code=422,
                detail={"ok": False, "error": "Failed to process PDF. Please ensure it's a valid ticket PDF."}
            )
        
        # Send email with .pkpass files (falls back to JSON if PKPass generation fails)
        try:
            email_sent = await email_service.send_wallet_pkpass(email, wallet_data)
            if not email_sent:
                raise ValueError("Email sending failed")
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            raise HTTPException(
                status_code=500,
                detail={"ok": False, "error": "Failed to send email. Please try again later."}
            )
        
        # Log success
        logger.info(f"Successfully processed and emailed wallet pass(es) to {email}")
        
        return {"ok": True}
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error processing request: {e}")
        raise HTTPException(
            status_code=500,
            detail={"ok": False, "error": "Internal server error. Please try again later."}
        )


@app.exception_handler(413)
async def request_entity_too_large_handler(request: Request, exc):
    """Handle request entity too large errors"""
    return JSONResponse(
        status_code=413,
        content={"ok": False, "error": "File size exceeds 10MB limit"}
    )


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
