"""
LLM Prompt templates for PDF processing.

This module contains the prompt templates used by the LLM processor
for extracting structured data from PDF documents.
"""

def get_vision_extraction_prompt(timezone: str = "+00:00", fallback_locale: str = "en-US") -> str:
    """
    Get the vision-based extraction prompt for LLM processing.
    
    Args:
        timezone: Timezone offset (e.g., "+03:00")
        fallback_locale: Fallback locale (e.g., "he-IL" or "en-US")
        
    Returns:
        Formatted prompt string for vision processing
    """
    prompt = f"""# Wallet Pass Extractor — Classification + Structured Fields (NO Wallet JSON)

You are an expert ticket/pass parser.
You will receive PDF page images (and optionally plain OCR text).
Your job is to **classify**, **count tickets**, and **extract fields** only.
**Do NOT** output Apple Wallet fields (no primaryFields, colors, or barcodes[] construction). I will build the final pass JSON myself.

ALLOWED CATEGORIES (choose exactly one):
["Boarding pass","Coupon","Event ticket","Store card","Generic"]

INPUTS I PROVIDE AT RUNTIME
- timezone: {timezone}                 # e.g., +03:00
- fallback_locale: {fallback_locale}   # e.g., he-IL or en-US
- Visual input: the PDF page images I attach (and/or the original PDF). Use visual layout, text, and graphics. If the PDF text layer is readable, use it; otherwise rely on OCR text.

GLOBAL RULES
1) No hallucination. If a value is unknown → null.
2) Return both raw strings (original language/script) and normalized values where applicable.
3) Datetime normalization: convert to ISO 8601 "YYYY-MM-DDTHH:MM:SS±HH:MM".
   - If the source lacks a timezone, apply {timezone}.
4) Currency normalization:
   - If certain: put numeric price.amount and ISO currency (e.g., ILS, USD) in price.currency.
   - Always include price.raw (original text) if present; if unsure of currency, leave currency null.
5) Multiple tickets:
   - If the document shows multiple distinct tickets (e.g., different seat numbers, repeated blocks), output one object per ticket in tickets[].
   - tickets_found MUST equal tickets.length.
6) If category is uncertain, choose "Generic" and add a short reason in sanity_warnings.
7) Provide confidences in [0.0, 1.0] and short evidence snippets (text spans/keywords used).
8) If a barcode/QR is visible but unreadable, set barcode_message = null and add a warning.
9) Use fallback_locale only when you cannot detect a locale; otherwise output the detected BCP-47 tag.

OUTPUT FORMAT — RETURN ONE JSON OBJECT ONLY (STRICT)
Do not include any extra text, markdown, or comments. Just raw JSON matching this shape:

{{
  "category": "Boarding pass | Coupon | Event ticket | Store card | Generic",
  "category_confidence": 0.0,
  "tickets_found": 0,
  "locale_detected": "BCP47-or-null",
  "sanity_warnings": ["string"],

  "tickets": [
    {{
      "raw_title": "string|null",
      "normalized_title": "string|null",

      "raw_datetime": "string|null",
      "normalized_datetime": "YYYY-MM-DDTHH:MM:SS±HH:MM|null",

      "raw_venue": "string|null",
      "normalized_venue": "string|null",
      "address": "string|null",

      "section": "string|null",
      "row": "string|null",
      "seat": "string|null",
      "zone": "string|null",
      "gate": "string|null",
      "entrance": "string|null",
      "door": "string|null",

      "ticket_id": "string|null",
      "order_id": "string|null",
      "reservation_code": "string|null",

      "purchaser_name": "string|null",

      "price": {{
        "amount": "number|null",
        "currency": "string|null",
        "raw": "string|null"
      }},

      "barcode_message": "string|null",

      "category_specific": {{
        "boarding_pass": {{
          "passenger_name": "string|null",
          "carrier": "string|null",
          "flight_number": "string|null",
          "origin": "string|null",
          "destination": "string|null",
          "gate": "string|null",
          "boarding_time": "YYYY-MM-DDTHH:MM:SS±HH:MM|null",
          "seat": "string|null",
          "class": "string|null",
          "pnr": "string|null"
        }},
        "coupon": {{
          "merchant": "string|null",
          "discount_type": "string|null",
          "discount_value": "string|null",
          "code": "string|null",
          "expiration": "YYYY-MM-DDTHH:MM:SS±HH:MM|null",
          "terms": "string|null"
        }},
        "event_ticket": {{
          "performer": "string|null",
          "home_team": "string|null",
          "away_team": "string|null",
          "league_or_competition": "string|null",
          "doors_open_time": "YYYY-MM-DDTHH:MM:SS±HH:MM|null",
          "gate": "string|null",
          "entrance": "string|null",
          "door": "string|null",
          "section": "string|null",
          "row": "string|null",
          "seat": "string|null",
          "zone": "string|null",
          "ticket_type": "string|null",
          "ticket_number": "string|null",
          "order_id": "string|null",
          "terms": "string|null"
        }},
        "store_card": {{
          "program_name": "string|null",
          "merchant": "string|null",
          "card_number": "string|null",
          "balance_amount": "number|null",
          "balance_currency": "string|null",
          "points": "number|null",
          "tier": "string|null",
          "expiration": "YYYY-MM-DDTHH:MM:SS±HH:MM|null"
        }},
        "generic": {{
          "entity": "string|null",
          "subtitle": "string|null",
          "notes": "string|null",
          "reference_numbers": ["string"],
          "valid_from": "YYYY-MM-DDTHH:MM:SS±HH:MM|null",
          "valid_to": "YYYY-MM-DDTHH:MM:SS±HH:MM|null",
          "location": "string|null",
          "contact_phone": "string|null",
          "website": "string|null"
        }}
      }},

      "evidence": {{
        "title": "string|null",
        "datetime": "string|null",
        "seat_block": "string|null",
        "price": "string|null",
        "ticket_or_order": "string|null"
      }},

      "confidence": {{
        "record": 0.0,
        "fields": {{
          "normalized_datetime": 0.0,
          "row": 0.0,
          "seat": 0.0,
          "price.amount": 0.0,
          "barcode_message": 0.0
        }}
      }},

      "page_hint": {{
        "page_index": "number|null",
        "notes": "string|null"
      }}
    }}
  ]
}}

EXTRACTION CUES
- Event ticket: performer/team, venue, section/row/seat, show date/time, ticket/order IDs, price.
- Boarding pass: airline, flight no., origin/destination, gate, boarding time, seat, PNR.
- Coupon: merchant, discount type/value, code, expiration, terms.
- Store card: program/merchant, member/card ID, balance/points, tier, expiration.
- Generic: if none match; still extract title, date/time, references, price if present.

VALIDATION REQUIREMENTS
- tickets_found MUST equal tickets.length.
- If any normalized_* is present, also include its raw_* counterpart if visible.
- If locale can't be detected, set locale_detected = null (then I will apply {fallback_locale} downstream).

FINAL REQUIREMENT
Output **only** the JSON object described above. No extra text."""

    return prompt
