"""
PDF to Wallet service integration.
"""

import io
import logging
import tempfile
from typing import Dict, List

logger = logging.getLogger(__name__)

# Import the modular PDF processor
import json
import os
from pathlib import Path

try:
    from .pdf_to_wallet.processor import WalletPassProcessor
    HAS_PDF_PROCESSOR = True
except ImportError as e:
    logger.warning(f"Direct import failed: {e}")
    HAS_PDF_PROCESSOR = False


class PDFService:
    """Service for converting PDF bytes to wallet passes"""
    
    def __init__(self):
        if HAS_PDF_PROCESSOR:
            try:
                self.processor = WalletPassProcessor()
                logger.info("PDF processor initialized successfully - using direct import")
            except Exception as e:
                logger.error(f"Failed to initialize PDF processor: {e}")
                self.processor = None
        else:
            self.processor = None
            logger.warning("PDF processor not available - will try subprocess method")
    
    def pdf_to_wallet(self, pdf_bytes: bytes, 
                     organization: str = "Test Organization",
                     pass_type_id: str = "pass.com.testorg.generic", 
                     team_id: str = "TEST123456",
                     pass_type: str = None,
                     timezone: str = "+00:00",
                     use_llm: bool = False) -> Dict:
        """
        Convert PDF bytes to wallet pass JSON.
        
        Args:
            pdf_bytes: PDF file content as bytes
            organization: Organization name for the pass
            pass_type_id: Apple Wallet pass type identifier
            team_id: Apple Developer team ID
            pass_type: Specific pass type or auto-detect if None
            timezone: Timezone offset for datetime fields
            use_llm: Whether to use LLM for enhanced field mapping          
        Returns:
            Dict containing wallet pass JSON structure
        """
        if not pdf_bytes:
            raise ValueError("No PDF content provided")
        
        logger.info(f"HAS_PDF_PROCESSOR: {HAS_PDF_PROCESSOR}, self.processor: {self.processor}")
        
        if not HAS_PDF_PROCESSOR or self.processor is None:
            logger.error("❌ PDF processor not available - direct import failed during initialization")
            logger.error("💡 Check that all dependencies are installed: pip install pymupdf opencv-python pillow")
            logger.error("💡 Verify that pdf_to_wallet module is properly installed and accessible")
            raise ValueError("PDF processing service is not available - check server configuration and dependencies")
        
        try:
            # Write PDF bytes to temporary file for processing
            # TODO:: how concurrent requests are handled?
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(pdf_bytes)
                tmp_file.flush()
                tmp_file_path = tmp_file.name
            
            # File is now closed, so processor can access it
            try:
                # Process the PDF
                passes = self.processor.process_pdf(
                    pdf_path=tmp_file_path,
                    organization=organization,
                    pass_type_id=pass_type_id,
                    team_id=team_id,
                    pass_type=pass_type,
                    timezone=timezone,
                    use_llm=use_llm,
                    api_key_env="OPENAI_API_KEY"
                )
                
                if not passes:
                    raise ValueError("No wallet passes generated from PDF")
                
                logger.info(f"🎉 DIRECT IMPORT SUCCESS - Generated {len(passes)} passes")
                if len(passes) == 1:
                    logger.info(f"🚀 Returning single pass: {passes[0].get('description', 'Unknown')}")
                    return passes[0]
                else:
                    logger.info(f"🚀 Returning all {len(passes)} passes as array")
                    return passes  # Return all passes
                
            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_file_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file: {cleanup_error}")
                
        except Exception as e:
            logger.error(f"❌ DIRECT IMPORT FAILED: {e}")
            raise ValueError(f"PDF processing failed: {str(e)}")