"""
PDF to Wallet service integration.
"""

import io
import logging
import tempfile
from typing import Dict, List

logger = logging.getLogger(__name__)

# Import the modular PDF processor
try:
    from .pdf_to_wallet.wallet_pass_converter.processor import WalletPassProcessor
    HAS_PDF_PROCESSOR = True
except ImportError as e:
    logger.error(f"Failed to import PDF processor: {e}")
    HAS_PDF_PROCESSOR = False


class PDFService:
    """Service for converting PDF bytes to wallet passes"""
    
    def __init__(self):
        if HAS_PDF_PROCESSOR:
            self.processor = WalletPassProcessor()
        else:
            self.processor = None
            logger.warning("PDF processor not available - using fallback")
    
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
        
        if not HAS_PDF_PROCESSOR:
            # Fallback implementation for when processor is not available
            logger.warning("Using fallback PDF processor")
            return self._fallback_processor(pdf_bytes)
        
        try:
            # Write PDF bytes to temporary file for processing
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(pdf_bytes)
                tmp_file.flush()
                
                # Process the PDF
                passes = self.processor.process_pdf(
                    pdf_path=tmp_file.name,
                    organization=organization,
                    pass_type_id=pass_type_id,
                    team_id=team_id,
                    pass_type=pass_type,
                    timezone=timezone,
                    use_llm=use_llm,
                    llm_provider="anthropic",
                    api_key_env="ANTHROPIC_API_KEY"
                )
                
                # Clean up temp file
                import os
                os.unlink(tmp_file.name)
                
                if not passes:
                    raise ValueError("No wallet passes generated from PDF")
                
                # Return the first pass (or could return all passes)
                return passes[0]
                
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            # Fall back to basic implementation
            return self._fallback_processor(pdf_bytes)
    
    def _fallback_processor(self, pdf_bytes: bytes) -> Dict:
        """
        Fallback implementation when main processor is unavailable.
        """
        return {
            "formatVersion": 1,
            "passTypeIdentifier": "pass.com.walletapp.generic",
            "teamIdentifier": "DEMO123456",
            "organizationName": "Wallet App Demo",
            "description": "Demo Wallet Pass",
            "serialNumber": f"DEMO_{len(pdf_bytes)}",
            "foregroundColor": "rgb(255, 255, 255)",
            "backgroundColor": "rgb(0, 122, 255)",
            "labelColor": "rgb(255, 255, 255)",
            "barcode": {
                "format": "PKBarcodeFormatQR",
                "message": f"DEMO_BARCODE_{len(pdf_bytes)}",
                "messageEncoding": "iso-8859-1"
            },
            "generic": {
                "primaryFields": [
                    {
                        "key": "title",
                        "label": "TITLE",
                        "value": "Demo Pass"
                    }
                ],
                "secondaryFields": [
                    {
                        "key": "subtitle",
                        "label": "SUBTITLE",
                        "value": f"Generated from {len(pdf_bytes)} byte PDF"
                    }
                ]
            }
        }
