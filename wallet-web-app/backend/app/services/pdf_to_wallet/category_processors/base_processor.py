"""
Base processor class for all category-specific processors.
"""

import uuid
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class CategoryProcessor:
    """Base class for category-specific processors."""
    
    def __init__(self, organization: str, pass_type_id: str, team_id: str):
        self.organization = organization
        self.pass_type_id = pass_type_id
        self.team_id = team_id
    
    def generate_serial_number(self, ticket_data: Dict[str, Any]) -> str:
        """Generate a unique serial number for the pass."""
        # Use ticket ID if available, otherwise generate UUID
        ticket_id = ticket_data.get('ticket_id')
        order_id = ticket_data.get('order_id')
        
        if ticket_id:
            return f"TICKET_{ticket_id}"
        elif order_id:
            return f"ORDER_{order_id}"
        else:
            return f"PASS_{uuid.uuid4().hex[:8].upper()}"
    
    def create_base_pass_structure(self, ticket_data: Dict[str, Any], 
                                  description: str, pass_type: str) -> Dict[str, Any]:
        """Create the base Apple Wallet pass structure."""
        # TODO:: colors should be set by the llm response 
        return {
            "formatVersion": 1,
            "passTypeIdentifier": self.pass_type_id,
            "teamIdentifier": self.team_id,
            "organizationName": self.organization,
            "description": description,
            "serialNumber": self.generate_serial_number(ticket_data),
            "backgroundColor": "rgb(0, 0, 0)",
            "foregroundColor": "rgb(255, 255, 255)",
            "labelColor": "rgb(255, 255, 255)",
            f"{pass_type}": {}
        }
    
    def create_barcode_structure(self, ticket_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Create barcode structure if barcode message exists."""
        barcode_message = ticket_data.get('barcode_message')
        if not barcode_message:
            # Try to use ticket_id or order_id as fallback
            barcode_message = ticket_data.get('ticket_id') or ticket_data.get('order_id')
        
        if barcode_message:
            return [{
                "format": "PKBarcodeFormatQR",
                "message": str(barcode_message),
                "messageEncoding": "utf-8",
                "altText": str(barcode_message)
            }]
        return None