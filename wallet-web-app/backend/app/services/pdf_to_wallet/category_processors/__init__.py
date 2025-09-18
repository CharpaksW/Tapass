"""
Category processors for converting LLM extracted data to Apple Wallet pass JSON.

Each category has a dedicated processor that takes the LLM's structured JSON
and converts it into the final Apple Wallet pass format.
"""

from .base_processor import CategoryProcessor
from .event_ticket_processor import EventTicketProcessor
from .boarding_pass_processor import BoardingPassProcessor
from .store_card_processor import StoreCardProcessor
from .generic_ticket_processor import GenericTicketProcessor

__all__ = [
    'CategoryProcessor',
    'EventTicketProcessor', 
    'BoardingPassProcessor',
    'StoreCardProcessor',
    'GenericTicketProcessor'
]