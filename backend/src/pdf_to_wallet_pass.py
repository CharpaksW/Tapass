#!/usr/bin/env python3
"""
PDF to Apple Wallet Pass Converter

A production-ready CLI tool that converts arbitrary ticket/receipt-like PDFs 
into Apple Wallet pass.json payloads with deterministic extraction and optional LLM mapping.

Usage:
    python pdf_to_wallet_pass.py input.pdf \
        --organization "Your Org" \
        --pass-type-id "pass.com.yourorg.generic" \
        --team-id "ABCDE12345" \
        --type generic \
        --tz "+03:00" \
        --outdir out

    # With LLM assistance:
    export ANTHROPIC_API_KEY=sk-***yourkey***
    python pdf_to_wallet_pass.py input.pdf --use-llm --provider anthropic --api-key-env ANTHROPIC_API_KEY

Requirements:
    pip install pymupdf opencv-python pillow pydantic jsonschema anthropic

Limitations:
    - Requires clear text and/or QR codes in PDF
    - LLM mapping is optional and falls back to deterministic extraction
    - Supports common date/time formats but may need timezone specification
    - QR payload is used exactly as decoded, not regenerated
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import uuid
import hashlib

# Core dependencies
try:
    import fitz  # PyMuPDF
    import cv2
    import numpy as np
    from PIL import Image
    import jsonschema
except ImportError as e:
    print(f"Missing required dependency: {e}")
    print("Install with: pip install pymupdf opencv-python pillow jsonschema")
    sys.exit(1)

# Optional LLM dependency
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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


def extract_pdf_text(pdf_path: str) -> str:
    """Extract raw text from PDF using PyMuPDF"""
    try:
        doc = fitz.open(pdf_path)
        text_parts = []
        page_count = len(doc)
        
        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text()
            text_parts.append(text)
            
        doc.close()
        raw_text = "\n".join(text_parts)
        logger.info(f"Extracted {len(raw_text)} characters from {page_count} pages")
        return raw_text
        
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        return ""


def render_pdf_pages(pdf_path: str) -> List[np.ndarray]:
    """Render PDF pages to images at 300 DPI"""
    try:
        doc = fitz.open(pdf_path)
        images = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render at 300 DPI (matrix scale factor 4.17 ≈ 300/72)
            mat = fitz.Matrix(4.17, 4.17)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            # Convert to OpenCV format
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            images.append(img)
            
        doc.close()
        logger.info(f"Rendered {len(images)} pages to images")
        return images
        
    except Exception as e:
        logger.error(f"Failed to render PDF pages: {e}")
        return []


def decode_qr_codes(images: List[np.ndarray], debug_save_images: bool = False) -> List[str]:
    """Decode QR codes from images using OpenCV with enhanced detection"""
    qr_detector = cv2.QRCodeDetector()
    qr_payloads = []
    
    for i, img in enumerate(images):
        page_qr_count = 0
        try:
            # Convert to grayscale for better QR detection
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Try multiple preprocessing approaches for better detection
            preprocessed_images = [
                gray,  # Original grayscale
                cv2.GaussianBlur(gray, (3, 3), 0),  # Slight blur to reduce noise
                cv2.GaussianBlur(gray, (5, 5), 0),  # More blur
                cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2),  # Adaptive threshold
                cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2),  # Different adaptive threshold
                cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],  # Otsu thresholding
                cv2.equalizeHist(gray),  # Histogram equalization for better contrast
                cv2.morphologyEx(gray, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))),  # Morphological closing
                cv2.bilateralFilter(gray, 9, 75, 75)  # Bilateral filter to reduce noise while keeping edges
            ]
            
            # Also try different scales
            height, width = gray.shape
            for scale in [0.5, 1.5, 2.0]:
                if scale != 1.0:
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    scaled = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
                    preprocessed_images.append(scaled)
            
            found_qrs = set()  # Use set to avoid duplicates
            
            for j, processed_img in enumerate(preprocessed_images):
                try:
                    # Try multi-QR detection first
                    retval, decoded_info, points, _ = qr_detector.detectAndDecodeMulti(processed_img)
                    
                    if retval and decoded_info:
                        for decoded in decoded_info:
                            if decoded and decoded.strip():
                                qr_text = decoded.strip()
                                if qr_text not in found_qrs:
                                    found_qrs.add(qr_text)
                                    qr_payloads.append(qr_text)
                                    page_qr_count += 1
                                    logger.debug(f"Found QR on page {i+1} (multi-method {j+1}): {qr_text[:50]}...")
                    
                    # Also try single QR detection as fallback
                    try:
                        decoded_single, points_single, _ = qr_detector.detectAndDecode(processed_img)
                        if decoded_single and decoded_single.strip():
                            qr_text = decoded_single.strip()
                            if qr_text not in found_qrs:
                                found_qrs.add(qr_text)
                                qr_payloads.append(qr_text)
                                page_qr_count += 1
                                logger.debug(f"Found QR on page {i+1} (single-method {j+1}): {qr_text[:50]}...")
                    except Exception as single_e:
                        logger.debug(f"Single QR detection method {j+1} failed on page {i+1}: {single_e}")
                                    
                except Exception as method_e:
                    logger.debug(f"QR detection method {j+1} failed on page {i+1}: {method_e}")
                    
            if page_qr_count > 0:
                logger.info(f"Page {i+1}: Found {page_qr_count} QR code(s)")
            else:
                logger.warning(f"Page {i+1}: No QR codes found despite trying {len(preprocessed_images)} different methods")
                
            # Save debug images if requested
            if debug_save_images:
                import os
                os.makedirs("debug_qr", exist_ok=True)
                cv2.imwrite(f"debug_qr/page_{i+1}_original.png", img)
                cv2.imwrite(f"debug_qr/page_{i+1}_gray.png", gray)
                for j, processed in enumerate(preprocessed_images[:5]):  # Save first 5 methods only
                    cv2.imwrite(f"debug_qr/page_{i+1}_method_{j+1}.png", processed)
                        
        except Exception as e:
            logger.warning(f"QR detection failed on page {i+1}: {e}")
            
    logger.info(f"Total decoded: {len(qr_payloads)} QR codes")
    return qr_payloads


def detect_locale(text: str) -> str:
    """Detect locale based on Hebrew characters"""
    hebrew_pattern = r'[\u0590-\u05FF]'
    if re.search(hebrew_pattern, text):
        return "he-IL"
    return "en-US"


def parse_deterministic_fields(text: str) -> Tuple[List[str], List[str], List[str]]:
    """Parse dates, numbers, and codes using regex patterns"""
    dates = []
    numbers = []
    codes = []
    
    # Date patterns (various formats)
    date_patterns = [
        r'\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b',  # DD/MM/YYYY or MM/DD/YYYY
        r'\b\d{4}[/.-]\d{1,2}[/.-]\d{1,2}\b',    # YYYY-MM-DD
        r'\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b',
        r'\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s+\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b'
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        dates.extend(matches)
    
    # Time patterns
    time_patterns = [
        r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AP]M)?\b',
        r'\b\d{1,2}\.\d{2}\b'  # European time format
    ]
    
    for pattern in time_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        dates.extend(matches)
    
    # Number patterns (potential seat numbers, amounts, etc.)
    number_patterns = [
        r'\b\d{3,}\b',  # 3+ digit numbers
        r'\$\d+(?:\.\d{2})?\b',  # Currency amounts
        r'\b\d+[A-Z]\b',  # Seat numbers like 12A
        r'\b[A-Z]\d+\b'   # Gate numbers like A12
    ]
    
    for pattern in number_patterns:
        matches = re.findall(pattern, text)
        numbers.extend(matches)
    
    # Code patterns (booking refs, PNRs, etc.)
    code_patterns = [
        r'\b[A-Z0-9]{6,}\b',  # General alphanumeric codes
        r'\b[A-Z]{2}\d{3,4}\b',  # Flight numbers
        r'\bPNR:?\s*([A-Z0-9]+)\b',  # PNR codes
        r'\bRef:?\s*([A-Z0-9]+)\b',  # Reference codes
        r'\bBooking:?\s*([A-Z0-9]+)\b'  # Booking codes
    ]
    
    for pattern in code_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if isinstance(matches[0] if matches else None, tuple):
            codes.extend([m[0] if isinstance(m, tuple) else m for m in matches])
        else:
            codes.extend(matches)
    
    logger.debug(f"Parsed {len(dates)} dates, {len(numbers)} numbers, {len(codes)} codes")
    return dates, numbers, codes


def extract_specific_fields(text: str) -> Dict[str, Optional[str]]:
    """Extract specific fields using targeted regex patterns"""
    fields = {}
    
    # Venue/location patterns
    venue_patterns = [
        r'(?:venue|location|theatre|theater|cinema|auditorium)[:]\s*([^\n\r]+)',
        r'(?:at|@)\s+([A-Z][^,\n\r]{10,50})',
    ]
    
    for pattern in venue_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and not fields.get('venue'):
            fields['venue'] = match.group(1).strip()
    
    # Seat patterns
    seat_patterns = [
        r'(?:seat|row|section)[:]\s*([A-Z0-9\-\s]+)',
        r'\b(?:Row|R)\s*(\d+)\s*(?:Seat|S)\s*([A-Z0-9]+)\b',
        r'\b(\d+[A-Z])\b'  # Simple seat like 12A
    ]
    
    for pattern in seat_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and not fields.get('seat'):
            if len(match.groups()) > 1:
                fields['seat'] = f"Row {match.group(1)} Seat {match.group(2)}"
            else:
                fields['seat'] = match.group(1).strip()
    
    # Name patterns
    name_patterns = [
        r'(?:passenger|guest|name)[:]\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
        r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b'  # Simple first last name
    ]
    
    for pattern in name_patterns:
        matches = re.findall(pattern, text)
        if matches and not fields.get('name'):
            # Take the first reasonable name match
            for name in matches:
                if len(name) > 5 and ' ' in name:
                    fields['name'] = name.strip()
                    break
    
    # Flight-specific patterns
    flight_patterns = [
        r'(?:flight|flt)[:]\s*([A-Z]{2}\d{3,4})',
        r'\b([A-Z]{2}\s*\d{3,4})\b'
    ]
    
    for pattern in flight_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and not fields.get('flight'):
            fields['flight'] = match.group(1).strip()
    
    # Airport codes
    airport_pattern = r'\b([A-Z]{3})\s*(?:to|→|-)\s*([A-Z]{3})\b'
    match = re.search(airport_pattern, text)
    if match:
        fields['origin'] = match.group(1)
        fields['destination'] = match.group(2)
    
    # PNR pattern
    pnr_pattern = r'(?:PNR|Confirmation)[:]\s*([A-Z0-9]{6,})'
    match = re.search(pnr_pattern, text, re.IGNORECASE)
    if match:
        fields['pnr'] = match.group(1)
    
    # Reservation/booking patterns
    reservation_patterns = [
        r'(?:booking|reservation|order|confirmation)[:]\s*([A-Z0-9]+)',
        r'(?:ref|reference)[:]\s*([A-Z0-9]+)'
    ]
    
    for pattern in reservation_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and not fields.get('reservation'):
            fields['reservation'] = match.group(1).strip()
    
    return fields


def detect_pass_type(text: str, qr_payloads: List[str]) -> str:
    """Auto-detect pass type based on content"""
    text_lower = text.lower()
    all_content = text_lower + " ".join(qr_payloads).lower()
    
    # Boarding pass indicators
    boarding_keywords = [
        'flight', 'boarding', 'gate', 'terminal', 'pnr', 'airline',
        'departure', 'arrival', 'aircraft', 'seat assignment'
    ]
    
    # Event ticket indicators
    event_keywords = [
        'seat', 'row', 'auditorium', 'screen', 'section', 'event',
        'ticket', 'venue', 'show', 'concert', 'theater', 'cinema'
    ]
    
    # Coupon indicators
    coupon_keywords = [
        'coupon', 'discount', 'promo', 'offer', 'deal', 'save',
        'percent off', '% off', 'expires'
    ]
    
    # Store card indicators
    store_keywords = [
        'loyalty', 'member', 'points', 'balance', 'club', 'rewards',
        'card number', 'member since'
    ]
    
    # Count keyword matches
    boarding_score = sum(1 for kw in boarding_keywords if kw in all_content)
    event_score = sum(1 for kw in event_keywords if kw in all_content)
    coupon_score = sum(1 for kw in coupon_keywords if kw in all_content)
    store_score = sum(1 for kw in store_keywords if kw in all_content)
    
    scores = {
        'boardingPass': boarding_score,
        'eventTicket': event_score,
        'coupon': coupon_score,
        'storeCard': store_score
    }
    
    # Return type with highest score, or generic if tie/no clear winner
    max_score = max(scores.values())
    if max_score >= 2:  # Require at least 2 keyword matches
        return max(scores, key=scores.get)
    
    return 'generic'


def generate_serial_number(content: str, index: int = 0) -> str:
    """Generate stable serial number from content"""
    # Create hash from content + index for stability
    content_hash = hashlib.md5(f"{content}_{index}".encode()).hexdigest()[:8]
    return f"TICKET_{content_hash.upper()}"


def normalize_datetime(date_str: str, timezone: str = "+00:00") -> Optional[str]:
    """Normalize datetime string to ISO8601 format"""
    if not date_str:
        return None
    
    # Common date patterns and their formats
    patterns = [
        (r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s+(\d{1,2}):(\d{2})', '%d/%m/%Y %H:%M'),
        (r'\b(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})\s+(\d{1,2}):(\d{2})', '%Y-%m-%d %H:%M'),
        (r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})\s+(\d{1,2}):(\d{2})', '%d/%m/%y %H:%M'),
    ]
    
    for pattern, fmt in patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                dt = datetime.strptime(match.group(0), fmt)
                return dt.strftime('%Y-%m-%dT%H:%M:%S') + timezone
            except ValueError:
                continue
    
    return None


async def llm_map_fields(ticket_data: TicketData, provider: str, api_key_env: str) -> Optional[Dict]:
    """Use LLM to normalize and map fields"""
    if not HAS_ANTHROPIC or provider != 'anthropic':
        logger.warning("Anthropic not available or unsupported provider")
        return None
    
    api_key = os.getenv(api_key_env)
    if not api_key:
        logger.warning(f"API key not found in environment variable {api_key_env}")
        return None
    
    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        # Prepare input data (truncate if too long)
        raw_text = ticket_data.raw_text[:16000] if len(ticket_data.raw_text) > 16000 else ticket_data.raw_text
        
        system_message = (
            "You map structured facts from a ticket-like PDF into a strict schema. "
            "Never invent values. Prefer QR payload for barcode_message. "
            "Only use information that is clearly present in the provided text."
        )
        
        user_content = {
            "raw_text": raw_text,
            "qr_payloads": ticket_data.qr_payloads,
            "candidates": {
                "dates": ticket_data.dates,
                "numbers": ticket_data.numbers,
                "codes": ticket_data.codes
            }
        }
        
        message = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            system=system_message,
            messages=[{
                "role": "user",
                "content": f"Map this ticket data to the schema: {json.dumps(user_content)}"
            }]
        )
        
        # Parse response
        response_text = message.content[0].text
        try:
            llm_result = json.loads(response_text)
            
            # Validate against schema
            jsonschema.validate(llm_result, LLM_OUTPUT_SCHEMA)
            logger.info("LLM mapping successful and validated")
            return llm_result
            
        except (json.JSONDecodeError, jsonschema.ValidationError) as e:
            logger.warning(f"LLM response validation failed: {e}")
            return None
            
    except Exception as e:
        logger.warning(f"LLM mapping failed: {e}")
        return None


def build_apple_wallet_pass(ticket_data: TicketData, args) -> Dict:
    """Build Apple Wallet pass structure"""
    pass_data = {
        "formatVersion": 1,
        "passTypeIdentifier": args.pass_type_id,
        "teamIdentifier": args.team_id,
        "organizationName": args.organization,
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
            
        pass_data["eventTicket"] = event_ticket
        
    elif ticket_data.type == "boardingPass":
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
            
        pass_data["boardingPass"] = boarding_pass
        
    elif ticket_data.type == "storeCard":
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
            
        pass_data["storeCard"] = store_card
        
    elif ticket_data.type == "coupon":
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
            
        pass_data["coupon"] = coupon
        
    else:  # generic
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
            
        pass_data["generic"] = generic
    
    return pass_data


def process_pdf(pdf_path: str, args) -> List[Dict]:
    """Main processing pipeline"""
    logger.info(f"Processing PDF: {pdf_path}")
    
    # Initialize ticket data
    ticket_data = TicketData()
    
    # Extract text
    ticket_data.raw_text = extract_pdf_text(pdf_path)
    if not ticket_data.raw_text:
        logger.error("No text extracted from PDF")
        return []
    
    # Detect locale
    ticket_data.locale = detect_locale(ticket_data.raw_text)
    
    # Render pages and decode QR codes
    images = render_pdf_pages(pdf_path)
    if images:
        # Enable debug image saving if debug logging is on
        debug_save = logger.getEffectiveLevel() == logging.DEBUG
        ticket_data.qr_payloads = decode_qr_codes(images, debug_save_images=debug_save)
    
    # Check if we have any content
    if not ticket_data.raw_text and not ticket_data.qr_payloads:
        logger.error("No text or QR codes found in PDF")
        return []
    
    # Parse deterministic fields
    ticket_data.dates, ticket_data.numbers, ticket_data.codes = parse_deterministic_fields(ticket_data.raw_text)
    specific_fields = extract_specific_fields(ticket_data.raw_text)
    
    # Apply specific fields
    for key, value in specific_fields.items():
        if value:
            setattr(ticket_data, key, value)
    
    # Detect pass type
    if args.type:
        ticket_data.type = args.type
    else:
        ticket_data.type = detect_pass_type(ticket_data.raw_text, ticket_data.qr_payloads)
    
    # Set barcode message (prefer QR payload)
    if ticket_data.qr_payloads:
        ticket_data.barcode_message = ticket_data.qr_payloads[0]
    elif ticket_data.reservation:
        ticket_data.barcode_message = ticket_data.reservation
    else:
        ticket_data.barcode_message = generate_serial_number(ticket_data.raw_text[:100])
    
    # Generate serial number
    ticket_data.serial = generate_serial_number(ticket_data.barcode_message)
    
    # Set title if not set
    if not ticket_data.title:
        ticket_data.title = f"{ticket_data.type.title()} Pass"
    
    # Normalize datetime
    if ticket_data.dates:
        ticket_data.datetime = normalize_datetime(ticket_data.dates[0], args.tz)
    
    # Optional LLM mapping
    if args.use_llm:
        logger.info("Attempting LLM field mapping...")
        import asyncio
        llm_result = asyncio.run(llm_map_fields(ticket_data, args.provider, args.api_key_env))
        
        if llm_result:
            # Apply LLM results
            for key, value in llm_result.items():
                if value is not None:
                    setattr(ticket_data, key, value)
            logger.info("Applied LLM field mapping")
        else:
            logger.info("Using deterministic extraction (LLM mapping failed)")
    
    # Handle multiple passes (if multiple QRs or seats)
    passes = []
    
    # For now, create one pass per QR payload if multiple exist
    if len(ticket_data.qr_payloads) > 1:
        for i, qr_payload in enumerate(ticket_data.qr_payloads):
            ticket_copy = TicketData()
            # Copy all attributes
            for attr in dir(ticket_data):
                if not attr.startswith('_'):
                    setattr(ticket_copy, attr, getattr(ticket_data, attr))
            
            # Customize for this specific ticket
            ticket_copy.barcode_message = qr_payload
            ticket_copy.serial = generate_serial_number(qr_payload, i)
            
            passes.append(build_apple_wallet_pass(ticket_copy, args))
    else:
        passes.append(build_apple_wallet_pass(ticket_data, args))
    
    logger.info(f"Generated {len(passes)} pass(es)")
    return passes


def save_passes(passes: List[Dict], output_dir: str) -> None:
    """Save passes to individual JSON files"""
    os.makedirs(output_dir, exist_ok=True)
    
    for i, pass_data in enumerate(passes):
        serial = pass_data.get('serialNumber', f'UNKNOWN_{i}')
        filename = f"pass_{serial}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(pass_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved pass to: {filepath}")


def run_self_test() -> bool:
    """Run basic self-tests"""
    logger.info("Running self-tests...")
    
    # Test date parsing
    test_text = "Event on 25/12/2024 at 19:30. Seat 12A, Row 5. Booking: ABC123"
    dates, numbers, codes = parse_deterministic_fields(test_text)
    
    assert len(dates) >= 1, "Should find at least one date"
    assert len(numbers) >= 1, "Should find numbers"
    assert len(codes) >= 1, "Should find booking code"
    
    # Test pass type detection
    boarding_text = "Flight AA123 from JFK to LAX. Gate A12. Boarding pass."
    pass_type = detect_pass_type(boarding_text, [])
    assert pass_type == "boardingPass", f"Expected boardingPass, got {pass_type}"
    
    event_text = "Concert ticket. Seat 12A, Row 5. Venue: Madison Square Garden"
    pass_type = detect_pass_type(event_text, [])
    assert pass_type == "eventTicket", f"Expected eventTicket, got {pass_type}"
    
    # Test serial generation
    serial = generate_serial_number("test content")
    assert serial.startswith("TICKET_"), "Serial should start with TICKET_"
    
    logger.info("Self-tests passed!")
    return True


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Convert PDF tickets to Apple Wallet passes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument("pdf_path", nargs='?', help="Path to input PDF file")
    parser.add_argument("--organization", default="Test Organization", help="Organization name for the pass (default: Test Organization)")
    parser.add_argument("--pass-type-id", default="pass.com.testorg.generic", help="Pass type identifier (default: pass.com.testorg.generic)")
    parser.add_argument("--team-id", default="TEST123456", help="Apple Developer Team ID (default: TEST123456)")
    parser.add_argument("--type", choices=["eventTicket", "boardingPass", "storeCard", "coupon", "generic"],
                       help="Pass type (auto-detected if not specified)")
    parser.add_argument("--tz", default="+00:00", help="Timezone offset (e.g., +03:00)")
    parser.add_argument("--outdir", default="out", help="Output directory for pass files")
    
    # LLM options
    parser.add_argument("--use-llm", action="store_true", help="Use LLM for field mapping")
    parser.add_argument("--provider", default="anthropic", choices=["anthropic"], help="LLM provider")
    parser.add_argument("--api-key-env", default="ANTHROPIC_API_KEY", help="Environment variable for API key")
    
    # Utility options
    parser.add_argument("--self-test", action="store_true", help="Run self-tests and exit")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run self-test if requested
    if args.self_test:
        try:
            run_self_test()
            print("All self-tests passed!")
            return 0
        except Exception as e:
            print(f"Self-test failed: {e}")
            return 1
    
    # Validate required arguments for normal operation
    if not args.pdf_path:
        logger.error("PDF file path is required")
        return 1
    
    # Validate PDF file exists
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF file not found: {args.pdf_path}")
        return 1
    
    # Check LLM requirements
    if args.use_llm:
        if not HAS_ANTHROPIC:
            logger.error("Anthropic library required for LLM mode. Install with: pip install anthropic")
            return 1
        
        if not os.getenv(args.api_key_env):
            logger.error(f"API key not found in environment variable: {args.api_key_env}")
            return 1
    
    try:
        # Process PDF
        passes = process_pdf(args.pdf_path, args)
        
        if not passes:
            logger.error("No passes generated")
            return 1
        
        # Output to stdout
        print(json.dumps(passes, indent=2))
        
        # Save to files
        save_passes(passes, args.outdir)
        
        logger.info(f"Successfully processed {args.pdf_path} -> {len(passes)} pass(es)")
        return 0
        
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
