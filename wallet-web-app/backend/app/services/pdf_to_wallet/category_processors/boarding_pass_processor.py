"""
Boarding pass processor for flights, trains, buses, etc.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any

from category_processors.base_processor import CategoryProcessor

logger = logging.getLogger(__name__)


class BoardingPassProcessor(CategoryProcessor):
    """Processor for boarding passes (flights, trains, buses)."""
    
    def process_boarding_passes(self, tickets: List[Dict[str, Any]], 
                              llm_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert LLM boarding pass data to Apple Wallet boarding passes."""
        passes = []
        
        for ticket in tickets:
            try:
                # Get boarding pass specific data
                boarding_data = ticket.get('category_specific', {}).get('boarding_pass', {})
                
                # Create base pass structure - use flight number or carrier as title
                flight_number = boarding_data.get('flight_number')
                carrier = boarding_data.get('carrier')
                
                if flight_number and carrier:
                    title = f"{carrier} {flight_number}"
                elif flight_number:
                    title = flight_number
                elif carrier:
                    title = carrier
                else:
                    title = ticket.get('normalized_title', ticket.get('raw_title', 'Boarding Pass'))
                
                pass_data = self.create_base_pass_structure(ticket, title, 'boardingPass')
                
                # Boarding pass specific fields
                boarding_pass = pass_data['boardingPass']
                boarding_pass['transitType'] = 'PKTransitTypeAir'  # Default to air, could be train/bus based on data
                
                # Primary fields (most prominent)
                primary_fields = []
                
                # Route/Journey information
                origin = boarding_data.get('origin')
                destination = boarding_data.get('destination')
                if origin and destination:
                    primary_fields.append({
                        "key": "route",
                        "label": "Route",
                        "value": f"{origin} → {destination}"
                    })
                elif boarding_data.get('flight_number'):
                    primary_fields.append({
                        "key": "journey",
                        "label": "Journey", 
                        "value": boarding_data['flight_number']
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
                
                # Secondary fields (gates, terminals, boarding info)
                secondary_fields = []
                
                gate = boarding_data.get('gate') or ticket.get('gate')
                if gate:
                    secondary_fields.append({
                        "key": "gate",
                        "label": "Gate",
                        "value": str(gate)
                    })
                
                # Boarding time if different from departure
                boarding_time = boarding_data.get('boarding_time')
                if boarding_time:
                    secondary_fields.append({
                        "key": "boardingTime",
                        "label": "Boarding",
                        "value": boarding_time
                    })
                
                # Terminal/venue information
                venue = ticket.get('normalized_venue', ticket.get('raw_venue'))
                if venue and not origin:  # Only show if we don't already have origin
                    secondary_fields.append({
                        "key": "terminal",
                        "label": "Terminal",
                        "value": venue
                    })
                
                boarding_pass['secondaryFields'] = secondary_fields
                
                # Auxiliary fields (seat, class, etc.)
                auxiliary_fields = []
                
                seat = boarding_data.get('seat') or ticket.get('seat')
                if seat:
                    auxiliary_fields.append({
                        "key": "seat",
                        "label": "Seat",
                        "value": str(seat)
                    })
                
                travel_class = boarding_data.get('class')
                if travel_class:
                    auxiliary_fields.append({
                        "key": "class",
                        "label": "Class",
                        "value": travel_class
                    })
                
                zone = ticket.get('zone')
                if zone:
                    auxiliary_fields.append({
                        "key": "zone",
                        "label": "Zone",
                        "value": str(zone)
                    })
                
                boarding_pass['auxiliaryFields'] = auxiliary_fields
                
                # Back fields (passenger info, confirmation codes, etc.)
                back_fields = []
                
                # Passenger name
                passenger_name = boarding_data.get('passenger_name') or ticket.get('purchaser_name')
                if passenger_name:
                    back_fields.append({
                        "key": "passengerName",
                        "label": "Passenger",
                        "value": passenger_name
                    })
                
                # Confirmation/reservation code
                pnr = boarding_data.get('pnr') or ticket.get('reservation_code')
                if pnr:
                    back_fields.append({
                        "key": "confirmationCode",
                        "label": "Confirmation",
                        "value": str(pnr)
                    })
                
                # Ticket number
                ticket_id = ticket.get('ticket_id')
                if ticket_id:
                    back_fields.append({
                        "key": "ticketNumber",
                        "label": "Ticket Number",
                        "value": str(ticket_id)
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
                
                boarding_pass['backFields'] = back_fields
                
                # Add barcode - prefer PNR/reservation code over ticket ID
                barcode_message = pnr or ticket_id
                if barcode_message:
                    pass_data['barcodes'] = [{
                        "format": "PKBarcodeFormatQR",
                        "message": str(barcode_message),
                        "messageEncoding": "utf-8",
                        "altText": str(barcode_message)
                    }]
                
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