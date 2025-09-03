"""
Data models and schemas for the wallet pass converter.
"""

from typing import List, Optional
from dataclasses import dataclass


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


# JSON Schema for LLM output validation
LLM_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["title", "type", "serial", "barcode_message"],
    "properties": {
        "title": {"type": "string"},
        "type": {"type": "string", "enum": ["eventTicket", "boardingPass", "storeCard", "coupon", "generic"]},
        "datetime": {"type": ["string", "null"]},
        "venue": {"type": ["string", "null"]},
        "auditorium": {"type": ["string", "null"]},
        "seat": {"type": ["string", "null"]},
        "reservation": {"type": ["string", "null"]},
        "name": {"type": ["string", "null"]},
        "pnr": {"type": ["string", "null"]},
        "flight": {"type": ["string", "null"]},
        "origin": {"type": ["string", "null"]},
        "destination": {"type": ["string", "null"]},
        "serial": {"type": "string"},
        "barcode_message": {"type": "string"}
    }
}
