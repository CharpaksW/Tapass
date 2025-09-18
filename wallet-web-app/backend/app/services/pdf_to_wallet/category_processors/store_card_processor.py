"""
Store card processor for loyalty cards, coupons, etc.
"""

import logging
from typing import Dict, List, Any

from category_processors.base_processor import CategoryProcessor

logger = logging.getLogger(__name__)


class StoreCardProcessor(CategoryProcessor):
    """Processor for store cards, loyalty cards, and coupons."""
    
    def process_store_cards(self, tickets: List[Dict[str, Any]], 
                          llm_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert LLM store card data to Apple Wallet store cards."""
        passes = []
        
        for ticket in tickets:
            try:
                # Create base pass structure
                title = ticket.get('normalized_title', ticket.get('raw_title', 'Store Card'))
                pass_data = self.create_base_pass_structure(ticket, title, 'storeCard')
                
                # Store card specific fields
                store_card = pass_data['storeCard']
                
                # Primary fields
                primary_fields = []
                
                if title:
                    primary_fields.append({
                        "key": "store",
                        "label": "Store",
                        "value": title
                    })
                
                store_card['primaryFields'] = primary_fields
                
                # Secondary fields
                secondary_fields = []
                
                # Card number or ID
                card_id = ticket.get('ticket_id') or ticket.get('order_id')
                if card_id:
                    secondary_fields.append({
                        "key": "cardNumber",
                        "label": "Card Number",
                        "value": str(card_id)
                    })
                
                store_card['secondaryFields'] = secondary_fields
                
                # Back fields
                back_fields = []
                
                venue = ticket.get('normalized_venue', ticket.get('raw_venue'))
                if venue:
                    back_fields.append({
                        "key": "location",
                        "label": "Location",
                        "value": venue
                    })
                
                store_card['backFields'] = back_fields
                
                # Add barcode
                barcodes = self.create_barcode_structure(ticket)
                if barcodes:
                    pass_data['barcodes'] = barcodes
                
                passes.append(pass_data)
                logger.info(f"✅ Created store card pass for: {title}")
                
            except Exception as e:
                logger.error(f"❌ Failed to process store card: {e}")
                continue
        
        return passes