"""
Field parsing and extraction utilities for ticket data.
"""

import logging
import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FieldParser:
    """Handles deterministic field parsing from text using regex patterns"""
    
    @staticmethod
    def detect_locale(text: str) -> str:
        """Detect locale based on Hebrew characters"""
        hebrew_pattern = r'[\u0590-\u05FF]'
        if re.search(hebrew_pattern, text):
            return "he-IL"
        return "en-US"
    
    @staticmethod
    def parse_candidates(text: str) -> Tuple[List[str], List[str], List[str]]:
        """Parse dates, numbers, and codes using regex patterns"""
        dates = []
        numbers = []
        codes = []
        
        # Date patterns (various formats including Hebrew)
        date_patterns = [
            r'\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b',  # DD/MM/YYYY or MM/DD/YYYY
            r'\b\d{4}[/.-]\d{1,2}[/.-]\d{1,2}\b',    # YYYY-MM-DD
            r'\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b',
            r'\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s+\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b',
            # Hebrew date patterns
            r'\b\d{1,2}\s+(ינואר|פברואר|מרץ|אפריל|מאי|יוני|יולי|אוגוסט|ספטמבר|אוקטובר|נובמבר|דצמבר)\s+\d{2,4}\b',
            r'\b(יום ראשון|יום שני|יום שלישי|יום רביעי|יום חמישי|יום שישי|יום שבת)\s+\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b',
            r'תאריך[:]\s*\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}',  # Hebrew "date:"
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
    
    @staticmethod
    def extract_specific_fields(text: str) -> Dict[str, Optional[str]]:
        """Extract specific fields using targeted regex patterns with Hebrew support"""
        fields = {}
        
        # Venue/location patterns (English + Hebrew)
        venue_patterns = [
            r'(?:venue|location|theatre|theater|cinema|auditorium)[:]\s*([^\n\r]+)',
            r'(?:at|@)\s+([A-Z][^,\n\r]{10,50})',
            # Hebrew venue patterns (enhanced)
            r'(?:מקום|אולם|בית קולנוע|תיאטרון|אודיטוריום|מרכז|היכל)[:]\s*([^\n\r]+)',
            r'(?:ב|אצל)[\u0590-\u05FF\s]{2,}',  # Hebrew "at" + Hebrew text
            r'[:]\s*קולנוע\s*([^\n\r]*)',  # ": קולנוע" pattern
            r'קולנוע\s+([\u0590-\u05FF\s\w]+)',  # "קולנוע" + venue name
            r'([\u0590-\u05FF\s]+)\s+קולנוע',  # venue name + "קולנוע"
        ]
        
        for pattern in venue_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not fields.get('venue'):
                fields['venue'] = match.group(1).strip()
        
        # Seat patterns (English + Hebrew)
        # Based on debug output, seat numbers appear as single digits (8, 9, 10) on separate lines
        seat_patterns = [
            r'(?:seat|row|section)[:]\s*([A-Z0-9\-\s]+)',
            r'\b(?:Row|R)\s*(\d+)\s*(?:Seat|S)\s*([A-Z0-9]+)\b',
            r'\b(\d+[A-Z])\b',  # Simple seat like 12A
            # Hebrew seat patterns (enhanced)
            r'(?:מושב|שורה|מקום|כיסא)[:]\s*([א-ת0-9\-\s]+)',
            r'(?:שורה|ש)\s*(\d+)\s*(?:מושב|מ)\s*([א-ת0-9]+)',
            r'מקום\s*(\d+)',  # Hebrew "seat" + number
            r'^\s*(\d{1,2})\s*$',  # Single/double digit numbers on their own line (seat numbers)
        ]
        
        # Look for seat numbers - single digits that appear after venue info
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            # Look for single digit seat numbers (8, 9, 10, etc.)
            if line.isdigit() and 1 <= len(line) <= 2 and int(line) <= 50:
                # Make sure it's not a date or other number by checking context
                if i > 0 and not any(date_word in lines[i-1] for date_word in ['/', ':', 'תאריך']):
                    if not fields.get('seat'):
                        fields['seat'] = line
                        break
        
        # Fallback to regex patterns if no seat found
        if not fields.get('seat'):
            for pattern in seat_patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match and not fields.get('seat'):
                    if len(match.groups()) > 1:
                        fields['seat'] = f"Row {match.group(1)} Seat {match.group(2)}"
                    else:
                        seat_val = match.group(1).strip()
                        # Avoid using dates as seat numbers
                        if not ('/' in seat_val or len(seat_val) > 4):
                            fields['seat'] = seat_val
        
        # Auditorium patterns (English + Hebrew)
        auditorium_patterns = [
            r'(?:auditorium|hall|screen|room)[:]\s*([A-Z0-9\-\s]+)',
            r'(?:אולם|מסך|חדר)[:]\s*([א-ת0-9\-\s]+)',
            r'(\d+)\s+אולם',  # number + "אולם"
            r'אולם\s+(\d+)',  # "אולם" + number
        ]
        
        for pattern in auditorium_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not fields.get('auditorium'):
                fields['auditorium'] = match.group(1).strip()
        
        # Movie title patterns (look for specific patterns in Hebrew tickets)
        # From the debug output, we can see the movie title "פורמולה1" appears consistently
        title_patterns = [
            r'\s([\u0590-\u05FF]+\d+)\s',  # Hebrew text with numbers (like פורמולה1)
            r'^\s*([\u0590-\u05FF]+\d+)$',  # Hebrew text with numbers on its own line
            r'([A-Z][a-zA-Z0-9\s]{3,30})',  # English movie titles
        ]
        
        for pattern in title_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for match in matches:
                if match and len(match.strip()) > 3 and not fields.get('title'):
                    # Skip common Hebrew words that aren't titles
                    skip_words = ['תאריך', 'ושעה', 'קולנוע', 'אולם', 'מושב', 'שורה', 'פלאנט', 'ראשלצ']
                    if not any(word in match for word in skip_words):
                        fields['title'] = match.strip()
                        break
        
        # Name patterns (English + Hebrew)
        name_patterns = [
            r'(?:passenger|guest|name)[:]\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b',  # Simple first last name
            # Hebrew name patterns
            r'(?:נוסע|אורח|שם)[:]\s*([\u0590-\u05FF\s]+)',
            r'(?:שם מלא|שם הנוסע)[:]\s*([\u0590-\u05FF\s]+)',
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
        
        # Reservation/booking patterns (English + Hebrew)
        reservation_patterns = [
            r'(?:booking|reservation|order|confirmation)[:]\s*([A-Z0-9]+)',
            r'(?:ref|reference)[:]\s*([A-Z0-9]+)',
            # Hebrew reservation patterns
            r'(?:הזמנה|רזרבציה|אישור|הזמנת כרטיס)[:]\s*([A-Z0-9]+)',
            r'(?:מספר הזמנה|קוד הזמנה|מספר אישור)[:]\s*([A-Z0-9]+)',
        ]
        
        for pattern in reservation_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and not fields.get('reservation'):
                fields['reservation'] = match.group(1).strip()
        
        return fields
    
    @staticmethod
    def _normalize_hebrew_text(text: str) -> str:
        """Normalize Hebrew text to handle RTL/LTR reading order issues"""
        import unicodedata
        
        # Normalize Unicode to handle different Hebrew encodings
        normalized = unicodedata.normalize('NFKC', text)
        
        # Add common Hebrew movie/cinema keywords that might be missed due to text order
        hebrew_cinema_indicators = [
            'קולנוע', 'סרט', 'הקרנה', 'כרטיס קולנוע', 'בית קולנוע',
            'אולם', 'מושב', 'שורה', 'מסך', 'הצגה'
        ]
        
        # Check for Hebrew keywords and add them to a searchable format
        found_keywords = []
        for keyword in hebrew_cinema_indicators:
            if keyword in normalized:
                found_keywords.append(keyword)
        
        # Return original text plus found keywords for better matching
        return normalized + " " + " ".join(found_keywords)
    
    @staticmethod
    def detect_pass_type(text: str, qr_payloads: List[str]) -> str:
        """Auto-detect pass type based on content"""
        text_lower = text.lower()
        
        # Handle Hebrew text order issues by normalizing
        normalized_text = FieldParser._normalize_hebrew_text(text_lower)
        all_content = normalized_text + " ".join(qr_payloads).lower()
        
        # Boarding pass indicators (English + Hebrew)
        boarding_keywords = [
            'flight', 'boarding', 'gate', 'terminal', 'pnr', 'airline',
            'departure', 'arrival', 'aircraft', 'seat assignment',
            # Hebrew boarding pass keywords
            'טיסה', 'עלייה למטוס', 'שער', 'טרמינל', 'חברת תעופה',
            'המראה', 'נחיתה', 'מטוס', 'הקצאת מושב', 'כרטיס טיסה'
        ]
        
        # Event ticket indicators (English + Hebrew)
        event_keywords = [
            'seat', 'row', 'auditorium', 'screen', 'section', 'event',
            'ticket', 'venue', 'show', 'concert', 'theater', 'cinema',
            # Hebrew event keywords (expanded for better detection)
            'מושב', 'שורה', 'אולם', 'מסך', 'קטע', 'אירוע',
            'כרטיס', 'מקום', 'הופעה', 'קונצרט', 'תיאטרון', 'בית קולנוע',
            'קולנוע', 'סרט', 'הקרנה', 'כרטיס קולנוע', 'הצגה',
            'כרטיסים', 'מושבים', 'כיסא', 'כיסאות', 'מקומות'
        ]
        
        # Coupon indicators (English + Hebrew)
        coupon_keywords = [
            'coupon', 'discount', 'promo', 'offer', 'deal', 'save',
            'percent off', '% off', 'expires',
            # Hebrew coupon keywords
            'קופון', 'הנחה', 'פרומו', 'הצעה', 'עסקה', 'חיסכון',
            'אחוז הנחה', 'פג תוקף', 'בתוקף עד'
        ]
        
        # Store card indicators (English + Hebrew)
        store_keywords = [
            'loyalty', 'member', 'points', 'balance', 'club', 'rewards',
            'card number', 'member since',
            # Hebrew store card keywords
            'נאמנות', 'חבר', 'נקודות', 'יתרה', 'מועדון', 'תגמולים',
            'מספר כרטיס', 'חבר מאז', 'כרטיס חבר'
        ]
        
        # Count keyword matches
        boarding_score = sum(1 for kw in boarding_keywords if kw in all_content)
        event_score = sum(1 for kw in event_keywords if kw in all_content)
        coupon_score = sum(1 for kw in coupon_keywords if kw in all_content)
        store_score = sum(1 for kw in store_keywords if kw in all_content)
        
        # Debug logging for Hebrew text issues
        logger.debug(f"Pass type detection scores: boarding={boarding_score}, event={event_score}, coupon={coupon_score}, store={store_score}")
        if 'hebrew' in text_lower or any(ord(c) >= 0x0590 and ord(c) <= 0x05FF for c in text):
            logger.debug(f"Hebrew text detected. Sample content: {all_content[:200]}...")
        
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
    
    @staticmethod
    def generate_serial_number(content: str, index: int = 0) -> str:
        """Generate stable serial number from content"""
        # Create hash from content + index for stability
        content_hash = hashlib.md5(f"{content}_{index}".encode()).hexdigest()[:8]
        return f"TICKET_{content_hash.upper()}"
    
    @staticmethod
    def normalize_datetime(date_str: str, timezone: str = "+00:00") -> Optional[str]:
        """Normalize datetime string to ISO8601 format with Hebrew support"""
        if not date_str:
            return None
        
        # Common date patterns and their formats
        patterns = [
            (r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s+(\d{1,2}):(\d{2})', '%d/%m/%Y %H:%M'),
            (r'\b(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})\s+(\d{1,2}):(\d{2})', '%Y-%m-%d %H:%M'),
            (r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2})\s+(\d{1,2}):(\d{2})', '%d/%m/%y %H:%M'),
            # Hebrew datetime patterns (date and time might be on separate lines)
            (r'(\d{2})/(\d{2})/(\d{4})', '%d/%m/%Y'),  # Just date
            (r'(\d{1,2}):(\d{2})', '%H:%M'),  # Just time
        ]
        
        date_part = None
        time_part = None
        
        # Try to extract date and time separately for Hebrew tickets
        date_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', date_str)
        time_match = re.search(r'(\d{1,2}):(\d{2})', date_str)
        
        if date_match and time_match:
            try:
                date_str_combined = f"{date_match.group(0)} {time_match.group(0)}"
                dt = datetime.strptime(date_str_combined, '%d/%m/%Y %H:%M')
                return dt.strftime('%Y-%m-%dT%H:%M:%S') + timezone
            except ValueError:
                pass
        
        # If only date found, try to find time in the broader text
        if date_match:
            time_match = re.search(r'(\d{1,2}):(\d{2})', date_str)
            if time_match:
                try:
                    date_str_combined = f"{date_match.group(0)} {time_match.group(0)}"
                    dt = datetime.strptime(date_str_combined, '%d/%m/%Y %H:%M')
                    return dt.strftime('%Y-%m-%dT%H:%M:%S') + timezone
                except ValueError:
                    pass
        
        # Try standard patterns
        for pattern, fmt in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    dt = datetime.strptime(match.group(0), fmt)
                    return dt.strftime('%Y-%m-%dT%H:%M:%S') + timezone
                except ValueError:
                    continue
        
        return None
