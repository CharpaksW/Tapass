"""
A processing pipeline that uses regex with LLM m.

"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List

from models import TicketData
from pdf_processor import PDFProcessor
from qr_detector import QRDetector
from field_parser import FieldParser
from pass_builder import PassBuilder
from llm_mapper import LLMMapper
from llm_processor import LLMProcessor
from response_json_to_pkpass_json import process_llm_data_to_wallet_passes

logger = logging.getLogger(__name__)


class WalletPassProcessor:
    """Main processor that orchestrates the entire pipeline"""
    
    def __init__(self):
        self.pdf_processor = PDFProcessor()
        self.qr_detector = QRDetector()
        self.field_parser = FieldParser()
        self.pass_builder = PassBuilder()
        self.llm_mapper = LLMMapper()
        self.llm_processor = LLMProcessor()
    
    def _extract_with_full_llm(self, pdf_path: str, organization: str, 
                              pass_type_id: str, team_id: str,
                              api_key_env: str = "OPENAI_API_KEY") -> Dict:
        """
        Extract structured data using Vision API
        
        Args:
            pdf_path: Path to PDF file
            organization: Organization name for the pass
            pass_type_id: Apple Wallet pass type identifier
            team_id: Apple Developer team ID
            api_key_env: Environment variable name for OpenAI API key
            
        Returns:
            Dictionary containing extracted LLM data or None if failed
        """
        if not self.llm_processor.is_available():
            logger.error("LLM processor not available - check API key configuration")
            return None
        
        try:
            # Extract structured data using Vision API
            llm_result = asyncio.run(
                self.llm_processor.process_pdf_with_vision(
                    pdf_path, organization, pass_type_id, team_id
                )
            )
            
            if llm_result:
                logger.info("✅ Vision API extraction successful")
                return llm_result
            else:
                logger.error("❌ Vision API extraction returned no results")
                return None
                
        except Exception as e:
            logger.error(f"❌ Vision API extraction failed: {e}")
            return None

    def _create_pkpass_files(self, wallet_passes: List[Dict]) -> List[str]:
        """
        Create .pkpass files from Apple Wallet JSON data
        
        Args:
            wallet_passes: List of Apple Wallet pass dictionaries
            
        Returns:
            List of created .pkpass file paths
        """
        created_files = []
        
        try:
            import json
            import tempfile
            
            for i, pass_data in enumerate(wallet_passes, 1):
                try:
                    # Create temporary JSON file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                        json.dump(pass_data, temp_file, indent=2)
                        temp_json_path = temp_file.name
                    
                    # Run pkpass_creator on the JSON file
                    logger.info(f"🔧 Creating .pkpass file {i}/{len(wallet_passes)}...")
                    
                    # Get the current directory for pkpass_creator.py
                    current_dir = Path(__file__).parent
                    pkpass_creator_path = current_dir / "pkpass_creator.py"
                    
                    if not pkpass_creator_path.exists():
                        logger.error(f"pkpass_creator.py not found at {pkpass_creator_path}")
                        continue
                    
                    # Run pkpass_creator as subprocess
                    result = subprocess.run(
                        ["python", str(pkpass_creator_path), temp_json_path],
                        cwd=str(current_dir),
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        # Parse the output to find the created .pkpass file path
                        output_lines = result.stdout.split('\n')
                        pkpass_file = None
                        
                        for line in output_lines:
                            if line.strip().endswith('.pkpass'):
                                pkpass_file = line.strip()
                                break
                        
                        if pkpass_file:
                            created_files.append(pkpass_file)
                            logger.info(f"✅ Created: {pkpass_file}")
                        else:
                            logger.warning(f"⚠️ .pkpass file created but path not found in output")
                    else:
                        logger.error(f"❌ pkpass_creator failed for pass {i}: {result.stderr}")
                    
                    # Clean up temporary file
                    try:
                        os.unlink(temp_json_path)
                    except:
                        pass
                        
                except Exception as e:
                    logger.error(f"❌ Failed to create .pkpass file for pass {i}: {e}")
                    continue
            
            return created_files
            
        except Exception as e:
            logger.error(f"❌ Failed to create .pkpass files: {e}")
            return []

    def process_pdf_traditional(self, pdf_path: str, organization: str, pass_type_id: str, 
                               team_id: str, pass_type: str = None, timezone: str = "+00:00",
                               use_llm: bool = True, api_key_env: str = "OPENAI_API_KEY") -> List[Dict]:
        """
        Traditional processing pipeline using regex + optional LLM enhancement
        
        Args:
            pdf_path: Path to PDF file
            organization: Organization name for the pass
            pass_type_id: Apple Wallet pass type identifier
            team_id: Apple Developer team ID
            pass_type: Specific pass type or auto-detect if None
            timezone: Timezone offset for datetime fields
            use_llm: Whether to use LLM for enhanced field mapping
            api_key_env: Environment variable name for OpenAI API key
            
        Returns:
            List of Apple Wallet pass dictionaries
        """
        logger.info(f" Processing PDF with traditional pipeline: {pdf_path}")
        
        # Extract text from PDF
        pdf_text = self.pdf_processor.extract_text(pdf_path)
        if not pdf_text:
            logger.error("No text extracted from PDF")
            return []
        
        # Initialize ticket data
        ticket_data = TicketData()
        ticket_data.raw_text = pdf_text
        print(ticket_data.raw_text) 
        
        # Detect locale
        ticket_data.locale = self.field_parser.detect_locale(ticket_data.raw_text)
        
        # Render pages and decode QR codes
        images = self.pdf_processor.render_pages(pdf_path)
        if images:
            # Enable debug image saving if debug logging is on
            debug_save = logger.getEffectiveLevel() == logging.DEBUG
            ticket_data.qr_payloads = self.qr_detector.decode_from_images(images, debug_save_images=debug_save)
        
        # Check if we have any content
        if not ticket_data.raw_text and not ticket_data.qr_payloads:
            logger.error("No text or QR codes found in PDF")
            return []
        
        # Parse deterministic fields
        ticket_data.dates, ticket_data.numbers, ticket_data.codes = self.field_parser.parse_candidates(ticket_data.raw_text)
        specific_fields = self.field_parser.extract_specific_fields(ticket_data.raw_text)
        
        # Apply specific fields
        for key, value in specific_fields.items():
            if value:
                setattr(ticket_data, key, value)
        
        # Detect pass type
        if pass_type:
            ticket_data.type = pass_type
        else:
            ticket_data.type = self.field_parser.detect_pass_type(ticket_data.raw_text, ticket_data.qr_payloads)
        
        # Set barcode message (prefer QR payload)
        if ticket_data.qr_payloads:
            ticket_data.barcode_message = ticket_data.qr_payloads[0]
        elif ticket_data.reservation:
            ticket_data.barcode_message = ticket_data.reservation
        else:
            ticket_data.barcode_message = self.field_parser.generate_serial_number(ticket_data.raw_text[:100])
        
        # Generate serial number
        ticket_data.serial = self.field_parser.generate_serial_number(ticket_data.barcode_message)
        
        # Set title if not set
        if not ticket_data.title:
            ticket_data.title = f"{ticket_data.type.title()} Pass"
        
        # Normalize datetime (pass full text to capture both date and time)
        if ticket_data.dates:
            # Pass the full raw text to capture time that might be separate from date
            ticket_data.datetime = self.field_parser.normalize_datetime(ticket_data.raw_text, timezone)
        
        # Optional LLM mapping
        if use_llm:
            logger.info("Attempting LLM field mapping...")
            self.llm_mapper = LLMMapper()
            llm_result = asyncio.run(self.llm_mapper.map_fields(ticket_data, api_key_env))
            
            if llm_result:
                self.llm_mapper.apply_llm_results(ticket_data, llm_result)
                logger.info("Applied LLM field mapping")
            else:
                logger.info("Using deterministic extraction (LLM mapping failed)")
        
        # Handle multiple passes (if multiple QRs or seats)
        passes = []
        
        # For now, create one pass per QR payload if multiple exist
        if len(ticket_data.qr_payloads) > 1:
            for i, qr_payload in enumerate(ticket_data.qr_payloads):
                ticket_copy = TicketData()
                # Copy all attributes
                for attr in dir(ticket_data):
                    if not attr.startswith('_'):
                        setattr(ticket_copy, attr, getattr(ticket_data, attr))
                
                # Customize for this specific ticket
                ticket_copy.barcode_message = qr_payload
                ticket_copy.serial = self.field_parser.generate_serial_number(qr_payload, i)
                
                passes.append(self.pass_builder.build_pass(ticket_copy, organization, pass_type_id, team_id))
        else:
            passes.append(self.pass_builder.build_pass(ticket_data, organization, pass_type_id, team_id))
        
        logger.info(f"Generated {len(passes)} pass(es)")
        return passes

    def process_pdf(self, pdf_path: str, organization: str, pass_type_id: str, 
                   team_id: str, use_full_llm: bool = True, create_pkpass: bool = True, **kwargs) -> List[Dict]:
        """
        Main entry point - complete processing pipeline from PDF to .pkpass files
        
        Args:
            pdf_path: Path to PDF file
            organization: Organization name for the pass
            pass_type_id: Apple Wallet pass type identifier
            team_id: Apple Developer team ID
            use_full_llm: If True, use full LLM pipeline; if False, use traditional pipeline
            create_pkpass: Whether to create .pkpass files or just return JSON
            **kwargs: Additional arguments passed to the chosen pipeline
            
        Returns:
            List of Apple Wallet pass dictionaries with optional .pkpass file paths
        """
        logger.info(f"🔄 Processing PDF: {pdf_path}")
        
        # Step 1: Extract data using the chosen pipeline
        if use_full_llm:
            logger.info("🤖 Using full LLM pipeline for extraction")
            llm_data = self._extract_with_full_llm(
                pdf_path, organization, pass_type_id, team_id,
                api_key_env=kwargs.get('api_key_env', 'OPENAI_API_KEY')
            )
        else:
            logger.info("🔧 Using traditional pipeline for extraction")
            # For traditional pipeline, we'd need to return structured data
            # For now, traditional pipeline returns passes directly
            return self.process_pdf_traditional(
                pdf_path, organization, pass_type_id, team_id, **kwargs
            )
        
        if not llm_data:
            logger.error("❌ Data extraction failed")
            return []
        
        # Step 2: Convert to Apple Wallet JSON format
        logger.info("🔄 Converting to Apple Wallet JSON format...")
        wallet_passes = process_llm_data_to_wallet_passes(
            llm_data, organization, pass_type_id, team_id
        )
        
        if not wallet_passes:
            logger.error("❌ Failed to convert data to wallet passes")
            return []
        
        logger.info(f"✅ Generated {len(wallet_passes)} Apple Wallet JSON(s)")
        
        # Step 3: Create .pkpass files if requested
        if create_pkpass:
            logger.info("🔄 Creating .pkpass files...")
            created_files = self._create_pkpass_files(wallet_passes)
            logger.info(f"✅ Created {len(created_files)} .pkpass file(s)")
            
            # Add created file paths to the return data
            for i, pass_data in enumerate(wallet_passes):
                if i < len(created_files):
                    pass_data['_pkpass_file'] = created_files[i]
        
        logger.info("🎉 Processing completed successfully!")
        return wallet_passes
