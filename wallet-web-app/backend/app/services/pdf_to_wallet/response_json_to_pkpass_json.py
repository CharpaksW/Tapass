"""
Category-specific processors for converting LLM extracted data to Apple Wallet pass JSON.

Each category has a dedicated processor function that takes the LLM's structured JSON
and converts it into the final Apple Wallet pass format.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

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
    
    def process_tickets(self, llm_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process all tickets from LLM data and return list of Apple Wallet passes."""
        category = llm_data.get('category', '').lower()
        tickets = llm_data.get('tickets', [])
        
        if not tickets:
            logger.warning("No tickets found in LLM data")
            return []
        
        # Route to appropriate processor based on category
        if 'event' in category or 'ticket' in category:
            return self.process_event_tickets(tickets, llm_data)
        elif 'boarding' in category or 'flight' in category:
            return self.process_boarding_passes(tickets, llm_data)
        elif 'store' in category or 'loyalty' in category or 'coupon' in category:
            return self.process_store_cards(tickets, llm_data)
        else:
            # Generic ticket processor
            return self.process_generic_tickets(tickets, llm_data)


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


class BoardingPassProcessor(CategoryProcessor):
    """Processor for boarding passes (flights, trains, buses)."""
    
    def process_boarding_passes(self, tickets: List[Dict[str, Any]], 
                              llm_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert LLM boarding pass data to Apple Wallet boarding passes."""
        passes = []
        
        for ticket in tickets:
            try:
                # Create base pass structure
                title = ticket.get('normalized_title', ticket.get('raw_title', 'Boarding Pass'))
                pass_data = self.create_base_pass_structure(ticket, title, 'boardingPass')
                
                # Boarding pass specific fields
                boarding_pass = pass_data['boardingPass']
                boarding_pass['transitType'] = 'PKTransitTypeAir'  # Default to air, could be train/bus
                
                # Primary fields
                primary_fields = []
                
                # Flight/route number
                if title:
                    primary_fields.append({
                        "key": "flight",
                        "label": "Flight",
                        "value": title
                    })
                
                # Departure time
                datetime_str = ticket.get('normalized_datetime')
                if datetime_str:
                    try:
                        dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                        primary_fields.append({
                            "key": "departureTime",
                            "label": "Departure",
                            "value": dt.strftime("%I:%M %p"),
                            "dateStyle": "PKDateStyleNone",
                            "timeStyle": "PKDateStyleShort"
                        })
                    except ValueError:
                        primary_fields.append({
                            "key": "departureTime",
                            "label": "Departure",
                            "value": datetime_str
                        })
                
                boarding_pass['primaryFields'] = primary_fields
                
                # Secondary fields (gates, terminals)
                secondary_fields = []
                
                gate = ticket.get('gate')
                if gate:
                    secondary_fields.append({
                        "key": "gate",
                        "label": "Gate",
                        "value": str(gate)
                    })
                
                boarding_pass['secondaryFields'] = secondary_fields
                
                # Auxiliary fields (seat, zone)
                auxiliary_fields = []
                
                seat = ticket.get('seat')
                if seat:
                    auxiliary_fields.append({
                        "key": "seat",
                        "label": "Seat",
                        "value": str(seat)
                    })
                
                zone = ticket.get('zone')
                if zone:
                    auxiliary_fields.append({
                        "key": "zone",
                        "label": "Zone",
                        "value": str(zone)
                    })
                
                boarding_pass['auxiliaryFields'] = auxiliary_fields
                
                # Back fields
                back_fields = []
                
                ticket_id = ticket.get('ticket_id')
                if ticket_id:
                    back_fields.append({
                        "key": "confirmationCode",
                        "label": "Confirmation",
                        "value": str(ticket_id)
                    })
                
                boarding_pass['backFields'] = back_fields
                
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
                logger.info(f"✅ Created boarding pass for: {title}")
                
            except Exception as e:
                logger.error(f"❌ Failed to process boarding pass: {e}")
                continue
        
        return passes


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


def process_llm_data_to_wallet_passes(llm_data: Dict[str, Any], organization: str, 
                                    pass_type_id: str, team_id: str, 
                                    output_dir: str = "generated_passes") -> List[Dict[str, Any]]:
    """
    Main function to process LLM extracted data and convert to Apple Wallet passes.
    Automatically saves each ticket as a separate JSON file when multiple tickets are found.
    
    Args:
        llm_data: The structured JSON data from the LLM
        organization: Organization name for the pass
        pass_type_id: Apple Wallet pass type identifier
        team_id: Apple Developer team identifier
        output_dir: Directory to save individual pass files when multiple tickets found
    
    Returns:
        List of Apple Wallet pass JSON objects
    """
    import os
    from pathlib import Path
    
    logger.info(f"🔄 Processing LLM data with category: {llm_data.get('category', 'Unknown')}")
    
    # Create the appropriate processor
    processor = CategoryProcessor(organization, pass_type_id, team_id)
    
    # Mix in the specific processor methods
    event_processor = EventTicketProcessor(organization, pass_type_id, team_id)
    boarding_processor = BoardingPassProcessor(organization, pass_type_id, team_id)
    store_processor = StoreCardProcessor(organization, pass_type_id, team_id)
    generic_processor = GenericTicketProcessor(organization, pass_type_id, team_id)
    
    # Add all processor methods to the main processor
    processor.process_event_tickets = event_processor.process_event_tickets
    processor.process_boarding_passes = boarding_processor.process_boarding_passes
    processor.process_store_cards = store_processor.process_store_cards
    processor.process_generic_tickets = generic_processor.process_generic_tickets
    
    # Process the tickets
    passes = processor.process_tickets(llm_data)
    
    logger.info(f"✅ Generated {len(passes)} Apple Wallet pass(es)")
    
    # Always save each ticket as separate file when multiple tickets found
    if len(passes) > 1:
        logger.info(f"🔄 Multiple tickets detected ({len(passes)}), saving each as separate JSON file...")
        
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        saved_files = []
        for i, pass_data in enumerate(passes, 1):
            try:
                # Create a subdirectory for each pass
                pass_dir = output_path / str(i)
                pass_dir.mkdir(exist_ok=True)
                
                # Save the pass as a single JSON object (not array)
                pass_file = pass_dir / "pass.json"
                
                with open(pass_file, 'w', encoding='utf-8') as f:
                    json.dump(pass_data, f, indent=2, ensure_ascii=False)
                
                saved_files.append(str(pass_file))
                
                # Log details about the saved pass
                description = pass_data.get('description', 'Unknown')
                serial = pass_data.get('serialNumber', 'N/A')
                logger.info(f"💾 Pass {i}/{len(passes)}: {description} → {pass_file}")
                logger.info(f"   Serial: {serial}")
                
            except Exception as e:
                logger.error(f"❌ Failed to save pass {i}: {e}")
                continue
        
        logger.info(f"✅ Successfully saved {len(saved_files)} separate pass file(s) to {output_path.absolute()}")
    
    return passes
