# src/llm_extract.py
import os, re, json
from jsonschema import validate, ValidationError

SCHEMA = {
  "type": "object",
  "required": ["event_name","venue","date","barcode"],
  "properties": {
    "event_name": {"type":"string"},
    "brand": {"type":"string"},
    "venue": {"type":"string"},
    "date": {"type":"string"},  # ISO-8601 preferred
    "row": {"type":"string"},
    "seat": {"type":"string"},
    "section": {"type":"string"},
    "hall": {"type":"string"},
    "door": {"type":"string"},
    "ticket_number": {"type":"string"},
    "barcode": {
      "type":"object",
      "required":["format","message"],
      "properties": {
        "format": {"type":"string"},
        "message": {"type":"string"},
        "altText": {"type":"string"}
      }
    }
  }
}

def regex_extract(text: str, hints=None):
    hints = hints or {}
    # Very naive multilingual regexes (Heb/Eng)
    def search(pattern):
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else ""

    event = search(r"(?:Film|Movie|סרט)\s*[:\-]\s*(.+)") or search(r"(?:Event|אירוע)\s*[:\-]\s*(.+)")
    venue = search(r"(?:Venue|מקום|קולנוע)\s*[:\-]\s*(.+)")
    hall  = search(r"(?:Hall|Screen|אולם)\s*[:\-]?\s*([A-Za-z0-9]+)")
    row   = search(r"(?:Row|שורה)\s*[:\-]?\s*([A-Za-z0-9]+)")
    seat  = search(r"(?:Seat|מושב|מקום)\s*[:\-]?\s*([A-Za-z0-9]+)")
    section = search(r"(?:Section|אזור|יציע)\s*[:\-]?\s*([A-Za-z0-9]+)")
    brand = search(r"(?:Cinema City|Yes Planet|Lev|יס פלנט|סינמה סיטי|לב(?:\s*סרטים)?)")
    ticket_no = search(r"(?:Ticket(?:\s*#| Number)?|מספר\s*כרטיס)\s*[:\-]?\s*([A-Za-z0-9\-]+)")
    # Simple date/time capture; leave to user to normalize or use LLM if needed
    date = search(r"(?:Date|תאריך)\s*[:\-]?\s*([0-9:/\-\s\.]+(?:AM|PM)?)")

    barcode = hints.get("barcode") or {}
    bfmt = barcode.get("format", "")
    bmsg = barcode.get("message", "")

    return {
        "event_name": event or "Event",
        "brand": brand or "",
        "venue": venue or "",
        "date": date or "",
        "row": row or "",
        "seat": seat or "",
        "section": section or "",
        "hall": hall or "",
        "door": "",
        "ticket_number": ticket_no or "",
        "barcode": {"format": bfmt or "qr", "message": bmsg or ticket_no or ""}
    }

def llm_json_extract(text: str, hints=None):
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not api_key:
        return None  # LLM disabled
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        system = "You extract fields from tickets. Return ONLY JSON matching the provided schema. No extra text."
        user = f"Text:\n{text}\n\nHints:\n{json.dumps(hints or {}, ensure_ascii=False)}"
        # Ask model for JSON only
        completion = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type":"json_object"},
            messages=[
                {"role":"system","content":system},
                {"role":"user","content":user}
            ]
        )
        raw = completion.choices[0].message.content
        data = json.loads(raw)
        return data
    except Exception:
        return None

def extract_fields(text: str, hints=None):
    # Try LLM first (if configured), then fallback to regex
    data = llm_json_extract(text, hints=hints)
    if not data:
        data = regex_extract(text, hints=hints)
    # Validate / coerce minimal schema
    try:
        validate(instance=data, schema=SCHEMA)
    except ValidationError:
        # ensure minimal required
        data.setdefault("event_name", data.get("event_name") or "Event")
        data.setdefault("venue", data.get("venue") or "")
        data.setdefault("date", data.get("date") or "")
        data.setdefault("barcode", data.get("barcode") or {"format":"qr","message":""})
    return data
