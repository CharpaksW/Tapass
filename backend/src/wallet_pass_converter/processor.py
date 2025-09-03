"""
Main processing pipeline that orchestrates all components.
"""

import asyncio
import logging
from typing import Dict, List

from .models import TicketData
from .pdf_processor import PDFProcessor
from .qr_detector import QRDetector
from .field_parser import FieldParser
from .pass_builder import PassBuilder
from .llm_mapper import LLMMapper

logger = logging.getLogger(__name__)


class WalletPassProcessor:
    """Main processor that orchestrates the entire pipeline"""
    
    def __init__(self):
        self.pdf_processor = PDFProcessor()
        self.qr_detector = QRDetector()
        self.field_parser = FieldParser()
        self.pass_builder = PassBuilder()
        self.llm_mapper = LLMMapper()
    
    def process_pdf(self, pdf_path: str, organization: str, pass_type_id: str, 
                   team_id: str, pass_type: str = None, timezone: str = "+00:00",
                   use_llm: bool = False, llm_provider: str = "anthropic", 
                   api_key_env: str = "ANTHROPIC_API_KEY") -> List[Dict]:
        """Main processing pipeline"""
        logger.info(f"Processing PDF: {pdf_path}")
        
        # Initialize ticket data
        ticket_data = TicketData()
        
        # Extract text
        ticket_data.raw_text = self.pdf_processor.extract_text(pdf_path)
        if not ticket_data.raw_text:
            logger.error("No text extracted from PDF")
            return []
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
            self.llm_mapper = LLMMapper(llm_provider)
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
