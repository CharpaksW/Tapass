"""
Utility functions for file operations and testing.
"""

import json
import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)


class FileUtils:
    """File operation utilities"""
    
    @staticmethod
    def save_passes(passes: List[Dict], output_dir: str) -> None:
        """Save passes to individual JSON files"""
        os.makedirs(output_dir, exist_ok=True)
        
        for i, pass_data in enumerate(passes):
            serial = pass_data.get('serialNumber', f'UNKNOWN_{i}')
            filename = f"pass_{serial}.json"
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(pass_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved pass to: {filepath}")


class TestRunner:
    """Self-test functionality"""
    
    @staticmethod
    def run_self_tests() -> bool:
        """Run basic self-tests"""
        logger.info("Running self-tests...")
        
        from .field_parser import FieldParser
        
        # Test date parsing
        test_text = "Event on 25/12/2024 at 19:30. Seat 12A, Row 5. Booking: ABC123"
        dates, numbers, codes = FieldParser.parse_candidates(test_text)
        
        assert len(dates) >= 1, "Should find at least one date"
        assert len(numbers) >= 1, "Should find numbers"
        assert len(codes) >= 1, "Should find booking code"
        
        # Test pass type detection
        boarding_text = "Flight AA123 from JFK to LAX. Gate A12. Boarding pass."
        pass_type = FieldParser.detect_pass_type(boarding_text, [])
        assert pass_type == "boardingPass", f"Expected boardingPass, got {pass_type}"
        
        event_text = "Concert ticket. Seat 12A, Row 5. Venue: Madison Square Garden"
        pass_type = FieldParser.detect_pass_type(event_text, [])
        assert pass_type == "eventTicket", f"Expected eventTicket, got {pass_type}"
        
        # Test serial generation
        serial = FieldParser.generate_serial_number("test content")
        assert serial.startswith("TICKET_"), "Serial should start with TICKET_"
        
        logger.info("Self-tests passed!")
        return True
