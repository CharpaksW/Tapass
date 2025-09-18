"""
Event ticket processor for concerts, movies, sports, etc.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any

from category_processors.base_processor import CategoryProcessor

logger = logging.getLogger(__name__)


class EventTicketProcessor(CategoryProcessor):
    """Processor for event tickets (concerts, movies, sports, etc.)."""
    
    def process_event_tickets(self, tickets: List[Dict[str, Any]], 
                            llm_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert LLM event ticket data to Apple Wallet event ticket passes."""
        passes = []
        
        for ticket in tickets:
            try:
                # Create base pass structure
                title = ticket.get('normalized_title', ticket.get('raw_title', 'Event Ticket'))
                pass_data = self.create_base_pass_structure(ticket, title, 'eventTicket')
                
                # Event ticket specific fields
                event_ticket = pass_data['eventTicket']
                
                # Primary fields (most important info)
                primary_fields = []
                
                # Event name
                if title:
                    primary_fields.append({
                        "key": "event",
                        "label": "Event",
                        "value": title
                    })
                
                # Date and time
                datetime_str = ticket.get('normalized_datetime')
                if datetime_str:
                    try:
                        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                        primary_fields.append({
                            "key": "eventTime",
                            "label": "Date & Time",
                            "value": dt.strftime("%B %d, %Y at %I:%M %p"),
                            "dateStyle": "PKDateStyleMedium",
                            "timeStyle": "PKDateStyleShort"
                        })
                    except ValueError:
                        primary_fields.append({
                            "key": "eventTime",
                            "label": "Date & Time",
                            "value": datetime_str
                        })
                
                event_ticket['primaryFields'] = primary_fields
                
                # Secondary fields (venue, section, etc.)
                secondary_fields = []
                
                venue = ticket.get('normalized_venue', ticket.get('raw_venue'))
                if venue:
                    secondary_fields.append({
                        "key": "venue",
                        "label": "Venue",
                        "value": venue
                    })
                
                event_ticket['secondaryFields'] = secondary_fields
                
                # Auxiliary fields (seat details)
                auxiliary_fields = []
                
                section = ticket.get('section')
                if section:
                    auxiliary_fields.append({
                        "key": "section",
                        "label": "Section",
                        "value": section
                    })
                
                row = ticket.get('row')
                if row:
                    auxiliary_fields.append({
                        "key": "row",
                        "label": "Row",
                        "value": str(row)
                    })
                
                seat = ticket.get('seat')
                if seat:
                    auxiliary_fields.append({
                        "key": "seat",
                        "label": "Seat",
                        "value": str(seat)
                    })
                
                event_ticket['auxiliaryFields'] = auxiliary_fields
                
                # Back fields (additional info)
                back_fields = []
                
                ticket_id = ticket.get('ticket_id')
                if ticket_id:
                    back_fields.append({
                        "key": "ticketId",
                        "label": "Ticket ID",
                        "value": str(ticket_id)
                    })
                
                order_id = ticket.get('order_id')
                if order_id:
                    back_fields.append({
                        "key": "orderId",
                        "label": "Order ID",
                        "value": str(order_id)
                    })
                
                # Price information
                price_data = ticket.get('price', {})
                if price_data and price_data.get('amount'):
                    price_str = f"{price_data['amount']}"
                    if price_data.get('currency'):
                        price_str += f" {price_data['currency']}"
                    back_fields.append({
                        "key": "price",
                        "label": "Price",
                        "value": price_str
                    })
                
                event_ticket['backFields'] = back_fields
                
                # Add barcode if available
                barcodes = self.create_barcode_structure(ticket)
                if barcodes:
                    pass_data['barcodes'] = barcodes
                
                # Add relevant date for sorting/organization
                if datetime_str:
                    try:
                        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                        pass_data['relevantDate'] = dt.isoformat()
                    except ValueError:
                        pass
                
                passes.append(pass_data)
                logger.info(f"✅ Created event ticket pass for: {title}")
                
            except Exception as e:
                logger.error(f"❌ Failed to process event ticket: {e}")
                continue
        
        return passes