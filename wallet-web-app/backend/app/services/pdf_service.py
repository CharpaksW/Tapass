"""
PDF to Wallet service integration.
"""

import io
import logging
import tempfile
from typing import Dict, List

logger = logging.getLogger(__name__)

# Import the modular PDF processor
import subprocess
import sys
import json
import os
from pathlib import Path

try:
    from .pdf_to_wallet.wallet_pass_converter.processor import WalletPassProcessor
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
            # Try using the modular script as subprocess
            logger.info("🔄 USING SUBPROCESS METHOD - Starting modular PDF processor via subprocess")
            try:
                result = self._subprocess_processor(pdf_bytes, organization, pass_type_id, team_id, use_llm)
                logger.info("✅ SUBPROCESS SUCCESS - Returning real processed data!")
                logger.info(f"📊 Real data preview: {str(result)[:200]}...")
                return result
            except Exception as e:
                logger.error(f"❌ SUBPROCESS FAILED - Error: {e}")
                logger.warning("⬇️ FALLING BACK to basic processor")
                fallback_result = self._fallback_processor(pdf_bytes)
                logger.info(f"📝 Fallback data preview: {str(fallback_result)[:200]}...")
                return fallback_result
        
        try:
            # Write PDF bytes to temporary file for processing
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
                    llm_provider="anthropic",
                    api_key_env="ANTHROPIC_API_KEY"
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
            logger.warning("⬇️ FALLING BACK to basic processor")
            return self._fallback_processor(pdf_bytes)
    
    def _subprocess_processor(self, pdf_bytes: bytes, organization: str, 
                             pass_type_id: str, team_id: str, use_llm: bool) -> Dict:
        """
        Use the modular PDF processor script as subprocess when direct import fails.
        """
        tmp_file_path = None
        try:
            # Write PDF bytes to temporary file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(pdf_bytes)
                tmp_file.flush()
                tmp_file_path = tmp_file.name
            
            # File is now closed, so subprocess can access it
            # Get the path to the modular script
            script_path = Path(__file__).parent / "pdf_to_wallet" / "pdf_to_wallet_pass_modular.py"
            
            # Build command
            cmd = [
                sys.executable, str(script_path),
                tmp_file_path,
                "--organization", organization,
                "--pass-type-id", pass_type_id,
                "--team-id", team_id
            ]
            
            if use_llm:
                cmd.append("--use-llm")
            
            # Run the subprocess
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info("🎉 SUBPROCESS COMPLETED SUCCESSFULLY!")
                logger.info(f"📤 Raw stdout length: {len(result.stdout)} characters")
                # Parse JSON output
                try:
                    passes = json.loads(result.stdout)
                    logger.info(f"✅ JSON PARSED - Found {len(passes)} passes")
                    if passes and len(passes) > 0:
                        if len(passes) == 1:
                            logger.info(f"🚀 RETURNING SINGLE PASS - Type: {passes[0].get('description', 'Unknown')}")
                            logger.info(f"🔍 Pass preview: {str(passes[0])[:300]}...")
                            return passes[0]
                        else:
                            logger.info(f"🚀 RETURNING ALL {len(passes)} PASSES")
                            logger.info(f"🔍 First pass preview: {str(passes[0])[:200]}...")
                            return passes  # Return all passes
                    else:
                        raise ValueError("No passes generated")
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON PARSE FAILED: {e}")
                    logger.error(f"📄 Raw stdout: {result.stdout[:500]}...")
                    raise ValueError(f"Invalid JSON output: {e}")
            else:
                logger.error(f"Subprocess failed with return code {result.returncode}")
                logger.error(f"Stderr: {result.stderr}")
                logger.error(f"Stdout: {result.stdout}")
                raise ValueError(f"PDF processing failed: {result.stderr}")
                    
        except Exception as e:
            logger.error(f"Subprocess processor failed: {e}")
            # Re-raise the exception so the higher level can handle fallback
            raise
        finally:
            # Always try to cleanup temp file if it exists
            if tmp_file_path:
                try:
                    os.unlink(tmp_file_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp file in finally block: {cleanup_error}")
    
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
