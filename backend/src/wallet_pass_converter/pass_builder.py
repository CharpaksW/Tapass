"""
Apple Wallet pass builder for different pass types.
"""

import logging
from typing import Dict
from .models import TicketData

logger = logging.getLogger(__name__)


class PassBuilder:
    """Builds Apple Wallet pass structures for different pass types"""
    
    @staticmethod
    def build_pass(ticket_data: TicketData, organization: str, 
                   pass_type_id: str, team_id: str) -> Dict:
        """Build Apple Wallet pass structure"""
        pass_data = {
            "formatVersion": 1,
            "passTypeIdentifier": pass_type_id,
            "teamIdentifier": team_id,
            "organizationName": organization,
            "description": ticket_data.title or f"{ticket_data.type.title()} Pass",
            "serialNumber": ticket_data.serial,
            "foregroundColor": "rgb(255, 255, 255)",
            "backgroundColor": "rgb(0, 0, 0)",
            "labelColor": "rgb(255, 255, 255)",
            "barcode": {
                "format": "PKBarcodeFormatQR",
                "message": ticket_data.barcode_message,
                "messageEncoding": "iso-8859-1"
            }
        }
        
        # Add locale if Hebrew detected
        if ticket_data.locale != "en-US":
            pass_data["locale"] = ticket_data.locale
        
        # Build subtype-specific structure
        if ticket_data.type == "eventTicket":
            pass_data["eventTicket"] = PassBuilder._build_event_ticket(ticket_data)
        elif ticket_data.type == "boardingPass":
            pass_data["boardingPass"] = PassBuilder._build_boarding_pass(ticket_data)
        elif ticket_data.type == "storeCard":
            pass_data["storeCard"] = PassBuilder._build_store_card(ticket_data)
        elif ticket_data.type == "coupon":
            pass_data["coupon"] = PassBuilder._build_coupon(ticket_data)
        else:  # generic
            pass_data["generic"] = PassBuilder._build_generic(ticket_data)
        
        return pass_data
    
    @staticmethod
    def _build_event_ticket(ticket_data: TicketData) -> Dict:
        """Build event ticket structure"""
        event_ticket = {}
        
        if ticket_data.datetime:
            event_ticket["primaryFields"] = [{
                "key": "event",
                "label": "EVENT",
                "value": ticket_data.title or "Event"
            }]
            
        secondary_fields = []
        if ticket_data.venue:
            secondary_fields.append({
                "key": "venue",
                "label": "VENUE",
                "value": ticket_data.venue
            })
        if ticket_data.datetime:
            secondary_fields.append({
                "key": "datetime",
                "label": "DATE & TIME", 
                "value": ticket_data.datetime,
                "dateStyle": "PKDateStyleShort",
                "timeStyle": "PKDateStyleShort"
            })
            
        if secondary_fields:
            event_ticket["secondaryFields"] = secondary_fields
            
        auxiliary_fields = []
        if ticket_data.seat:
            auxiliary_fields.append({
                "key": "seat",
                "label": "SEAT",
                "value": ticket_data.seat
            })
        if ticket_data.auditorium:
            auxiliary_fields.append({
                "key": "auditorium", 
                "label": "AUDITORIUM",
                "value": ticket_data.auditorium
            })
            
        if auxiliary_fields:
            event_ticket["auxiliaryFields"] = auxiliary_fields
            
        return event_ticket
    
    @staticmethod
    def _build_boarding_pass(ticket_data: TicketData) -> Dict:
        """Build boarding pass structure"""
        boarding_pass = {}
        
        # Transit type (assumed air travel)
        boarding_pass["transitType"] = "PKTransitTypeAir"
        
        primary_fields = []
        if ticket_data.origin and ticket_data.destination:
            primary_fields.append({
                "key": "origin",
                "label": "FROM",
                "value": ticket_data.origin
            })
            primary_fields.append({
                "key": "destination", 
                "label": "TO",
                "value": ticket_data.destination
            })
            
        if primary_fields:
            boarding_pass["primaryFields"] = primary_fields
            
        secondary_fields = []
        if ticket_data.flight:
            secondary_fields.append({
                "key": "flight",
                "label": "FLIGHT",
                "value": ticket_data.flight
            })
        if ticket_data.datetime:
            secondary_fields.append({
                "key": "departure",
                "label": "DEPARTURE",
                "value": ticket_data.datetime,
                "dateStyle": "PKDateStyleShort",
                "timeStyle": "PKDateStyleShort"
            })
            
        if secondary_fields:
            boarding_pass["secondaryFields"] = secondary_fields
            
        auxiliary_fields = []
        if ticket_data.seat:
            auxiliary_fields.append({
                "key": "seat",
                "label": "SEAT", 
                "value": ticket_data.seat
            })
        if ticket_data.pnr:
            auxiliary_fields.append({
                "key": "pnr",
                "label": "PNR",
                "value": ticket_data.pnr
            })
            
        if auxiliary_fields:
            boarding_pass["auxiliaryFields"] = auxiliary_fields
            
        return boarding_pass
    
    @staticmethod
    def _build_store_card(ticket_data: TicketData) -> Dict:
        """Build store card structure"""
        store_card = {}
        
        primary_fields = []
        if ticket_data.title:
            primary_fields.append({
                "key": "balance",
                "label": "BALANCE",
                "value": ticket_data.title
            })
            
        if primary_fields:
            store_card["primaryFields"] = primary_fields
            
        return store_card
    
    @staticmethod
    def _build_coupon(ticket_data: TicketData) -> Dict:
        """Build coupon structure"""
        coupon = {}
        
        primary_fields = []
        if ticket_data.title:
            primary_fields.append({
                "key": "offer",
                "label": "OFFER",
                "value": ticket_data.title
            })
            
        if primary_fields:
            coupon["primaryFields"] = primary_fields
            
        return coupon
    
    @staticmethod
    def _build_generic(ticket_data: TicketData) -> Dict:
        """Build generic pass structure"""
        generic = {}
        
        primary_fields = []
        if ticket_data.title:
            primary_fields.append({
                "key": "title",
                "label": "TITLE",
                "value": ticket_data.title
            })
            
        if primary_fields:
            generic["primaryFields"] = primary_fields
            
        secondary_fields = []
        for key, value in [
            ("reservation", ticket_data.reservation),
            ("name", ticket_data.name),
            ("datetime", ticket_data.datetime)
        ]:
            if value:
                field = {"key": key, "label": key.upper(), "value": value}
                if key == "datetime":
                    field.update({
                        "dateStyle": "PKDateStyleShort",
                        "timeStyle": "PKDateStyleShort"
                    })
                secondary_fields.append(field)
                
        if secondary_fields:
            generic["secondaryFields"] = secondary_fields
            
        return generic
