"""
Data models and schemas for the wallet pass converter.
"""

from typing import List, Optional
from dataclasses import dataclass

# Todo:: serial number should be unique and not generated from the raw text
@dataclass
class TicketData:
    """Container for extracted ticket information"""
    
    def __init__(self):
        self.raw_text: str = ""
        self.qr_payloads: List[str] = []
        self.dates: List[str] = []
        self.numbers: List[str] = []
        self.codes: List[str] = []
        self.title: Optional[str] = None
        self.type: str = "generic"
        self.datetime: Optional[str] = None
        self.venue: Optional[str] = None
        self.auditorium: Optional[str] = None
        self.seat: Optional[str] = None
        self.reservation: Optional[str] = None
        self.name: Optional[str] = None
        self.pnr: Optional[str] = None
        self.flight: Optional[str] = None
        self.origin: Optional[str] = None
        self.destination: Optional[str] = None
        self.serial: str = ""
        self.barcode_message: str = ""
        self.locale: str = "en-US"


# JSON Schema for LLM output validation - Enhanced for PKPass compatibility
LLM_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["title", "type", "serial", "barcode_message"],
    "properties": {
        # Core PKPass fields
        "title": {
            "type": "string", 
            "minLength": 1,
            "description": "Main event/service name - appears prominently on pass"
        },
        "type": {
            "type": "string", 
            "enum": ["eventTicket", "boardingPass", "storeCard", "coupon", "generic"],
            "description": "PKPass style type for proper wallet display"
        },
        "serial": {
            "type": "string",
            "minLength": 1, 
            "description": "Unique identifier - ticket number, booking reference, etc."
        },
        "barcode_message": {
            "type": "string",
            "description": "Barcode/QR code content for scanning"
        },
        
        # Event-specific fields
        "datetime": {
            "type": ["string", "null"],
            "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}$|^\\d{4}-\\d{2}-\\d{2}$",
            "description": "Event date/time in ISO format (YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD)"
        },
        "venue": {
            "type": ["string", "null"],
            "description": "Location, venue name, airport, or station"
        },
        "auditorium": {
            "type": ["string", "null"],
            "description": "Hall, gate, platform, or specific location within venue"
        },
        "seat": {
            "type": ["string", "null"],
            "description": "Seat number, row, or seating assignment"
        },
        
        # Booking/reservation fields
        "reservation": {
            "type": ["string", "null"],
            "description": "Reservation or confirmation number"
        },
        "name": {
            "type": ["string", "null"],
            "description": "Passenger, attendee, or customer name"
        },
        
        # Transportation-specific fields
        "pnr": {
            "type": ["string", "null"],
            "description": "Passenger Name Record for flights"
        },
        "flight": {
            "type": ["string", "null"],
            "description": "Flight number, train number, or service identifier"
        },
        "origin": {
            "type": ["string", "null"],
            "description": "Departure location for transportation"
        },
        "destination": {
            "type": ["string", "null"],
            "description": "Arrival location for transportation"
        },
        
        # Additional metadata
        "locale": {
            "type": ["string", "null"],
            "default": "en-US",
            "description": "Language/locale for the pass (e.g., 'he-IL' for Hebrew)"
        }
    },
    "additionalProperties": False
}
