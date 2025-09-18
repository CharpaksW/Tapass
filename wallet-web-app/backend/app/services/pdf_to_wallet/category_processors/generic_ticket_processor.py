"""
Generic ticket processor for unknown categories and fallback handling.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any

from category_processors.base_processor import CategoryProcessor

logger = logging.getLogger(__name__)


class GenericTicketProcessor(CategoryProcessor):
    """Processor for generic tickets and unknown categories."""
    
    def process_generic_tickets(self, tickets: List[Dict[str, Any]], 
                              llm_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert LLM generic ticket data to Apple Wallet generic passes."""
        passes = []
        
        for ticket in tickets:
            try:
                # Create base pass structure - use generic for unknown categories
                title = ticket.get('normalized_title', ticket.get('raw_title', 'Ticket'))
                pass_data = self.create_base_pass_structure(ticket, title, 'generic')
                
                # Generic pass fields
                generic = pass_data['generic']
                
                # Primary fields
                primary_fields = []
                
                if title:
                    primary_fields.append({
                        "key": "title",
                        "label": "Title",
                        "value": title
                    })
                
                # Date and time
                datetime_str = ticket.get('normalized_datetime')
                if datetime_str:
                    try:
                        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                        primary_fields.append({
                            "key": "datetime",
                            "label": "Date & Time",
                            "value": dt.strftime("%B %d, %Y at %I:%M %p"),
                            "dateStyle": "PKDateStyleMedium",
                            "timeStyle": "PKDateStyleShort"
                        })
                    except ValueError:
                        primary_fields.append({
                            "key": "datetime",
                            "label": "Date & Time",
                            "value": datetime_str
                        })
                
                generic['primaryFields'] = primary_fields
                
                # Secondary fields
                secondary_fields = []
                
                venue = ticket.get('normalized_venue', ticket.get('raw_venue'))
                if venue:
                    secondary_fields.append({
                        "key": "venue",
                        "label": "Location",
                        "value": venue
                    })
                
                generic['secondaryFields'] = secondary_fields
                
                # Auxiliary fields
                auxiliary_fields = []
                
                ticket_id = ticket.get('ticket_id')
                if ticket_id:
                    auxiliary_fields.append({
                        "key": "ticketId",
                        "label": "Ticket ID",
                        "value": str(ticket_id)
                    })
                
                generic['auxiliaryFields'] = auxiliary_fields
                
                # Back fields
                back_fields = []
                
                order_id = ticket.get('order_id')
                if order_id:
                    back_fields.append({
                        "key": "orderId",
                        "label": "Order ID",
                        "value": str(order_id)
                    })
                
                generic['backFields'] = back_fields
                
                # Add barcode
                barcodes = self.create_barcode_structure(ticket)
                if barcodes:
                    pass_data['barcodes'] = barcodes
                
                # Add relevant date
                if datetime_str:
                    try:
                        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                        pass_data['relevantDate'] = dt.isoformat()
                    except ValueError:
                        pass
                
                passes.append(pass_data)
                logger.info(f"✅ Created generic pass for: {title}")
                
            except Exception as e:
                logger.error(f"❌ Failed to process generic ticket: {e}")
                continue
        
        return passes