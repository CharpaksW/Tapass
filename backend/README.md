# PDF to Apple Wallet Pass Converter

A production-ready CLI tool that converts arbitrary ticket/receipt-like PDFs into Apple Wallet pass.json payloads with deterministic extraction and optional LLM mapping.

## Features

- **Multi-format support**: Converts PDFs to Apple Wallet passes for eventTicket, boardingPass, storeCard, coupon, and generic types
- **Deterministic extraction**: Uses PyMuPDF for text extraction and OpenCV for QR code detection
- **Smart type detection**: Automatically detects pass type based on content keywords
- **LLM enhancement**: Optional Anthropic Claude integration for improved field mapping
- **Multiple passes**: Supports generating multiple passes from single PDF (multiple QR codes)
- **Localization**: Auto-detects Hebrew content and sets appropriate locale
- **Robust parsing**: Handles various date formats, seat numbers, booking codes, and flight information

## Installation

1. **Install Python dependencies**:
   ```bash
   pip install pymupdf opencv-python pillow jsonschema anthropic python-dateutil numpy
   ```

2. **For LLM features (optional)**:
   ```bash
   export ANTHROPIC_API_KEY=sk-***your-api-key***
   ```

## Usage

### Basic Usage

```bash
python pdf_to_wallet_pass.py input.pdf \
    --organization "Your Organization" \
    --pass-type-id "pass.com.yourorg.generic" \
    --team-id "ABCDE12345" \
    --outdir out
```

### With Auto-Detection

```bash
# Let the tool auto-detect pass type
python pdf_to_wallet_pass.py boarding_pass.pdf \
    --organization "Airline Name" \
    --pass-type-id "pass.com.airline.boarding" \
    --team-id "ABCDE12345"
```

### With LLM Enhancement

```bash
export ANTHROPIC_API_KEY=sk-***your-key***
python pdf_to_wallet_pass.py ticket.pdf \
    --organization "Event Organizer" \
    --pass-type-id "pass.com.events.ticket" \
    --team-id "ABCDE12345" \
    --use-llm --provider anthropic --api-key-env ANTHROPIC_API_KEY
```

### Specific Pass Types

```bash
# Event ticket
python pdf_to_wallet_pass.py concert.pdf \
    --type eventTicket \
    --organization "Concert Hall" \
    --pass-type-id "pass.com.venue.event" \
    --team-id "ABCDE12345" \
    --tz "+02:00"

# Boarding pass
python pdf_to_wallet_pass.py flight.pdf \
    --type boardingPass \
    --organization "Airline" \
    --pass-type-id "pass.com.airline.boarding" \
    --team-id "ABCDE12345"

# Store card
python pdf_to_wallet_pass.py loyalty.pdf \
    --type storeCard \
    --organization "Retail Store" \
    --pass-type-id "pass.com.store.loyalty" \
    --team-id "ABCDE12345"
```

## Command Line Options

### Required Arguments
- `pdf_path`: Path to input PDF file
- `--organization`: Organization name for the pass
- `--pass-type-id`: Pass type identifier (e.g., pass.com.yourorg.generic)
- `--team-id`: Apple Developer Team ID

### Optional Arguments
- `--type`: Pass type (eventTicket, boardingPass, storeCard, coupon, generic)
- `--tz`: Timezone offset (default: +00:00)
- `--outdir`: Output directory for pass files (default: out)
- `--use-llm`: Enable LLM field mapping
- `--provider`: LLM provider (default: anthropic)
- `--api-key-env`: Environment variable for API key (default: ANTHROPIC_API_KEY)
- `--debug`: Enable debug logging
- `--self-test`: Run self-tests and exit

## Output

The tool generates:
1. **JSON array to stdout**: All generated passes
2. **Individual files**: `out/pass_<serial>.json` for each pass

### Example Output Structure

```json
[
  {
    "formatVersion": 1,
    "passTypeIdentifier": "pass.com.yourorg.event",
    "teamIdentifier": "ABCDE12345",
    "organizationName": "Event Organizer",
    "description": "Event Ticket",
    "serialNumber": "TICKET_A1B2C3D4",
    "foregroundColor": "rgb(255, 255, 255)",
    "backgroundColor": "rgb(0, 0, 0)",
    "labelColor": "rgb(255, 255, 255)",
    "barcode": {
      "format": "PKBarcodeFormatQR",
      "message": "EXACT_QR_PAYLOAD_FROM_PDF",
      "messageEncoding": "iso-8859-1"
    },
    "eventTicket": {
      "primaryFields": [
        {
          "key": "event",
          "label": "EVENT",
          "value": "Concert Name"
        }
      ],
      "secondaryFields": [
        {
          "key": "venue",
          "label": "VENUE", 
          "value": "Concert Hall"
        },
        {
          "key": "datetime",
          "label": "DATE & TIME",
          "value": "2024-12-25T19:30:00+02:00",
          "dateStyle": "PKDateStyleShort",
          "timeStyle": "PKDateStyleShort"
        }
      ],
      "auxiliaryFields": [
        {
          "key": "seat",
          "label": "SEAT",
          "value": "Row 5 Seat 12A"
        }
      ]
    }
  }
]
```

## Supported Pass Types

### Event Ticket (`eventTicket`)
- **Detects**: seat, row, auditorium, screen, section, event, ticket, venue
- **Fields**: venue, datetime, seat, auditorium
- **Use case**: Concerts, movies, sports events

### Boarding Pass (`boardingPass`) 
- **Detects**: flight, boarding, gate, terminal, pnr, airline, departure
- **Fields**: origin, destination, flight, datetime, seat, pnr
- **Use case**: Airline tickets

### Store Card (`storeCard`)
- **Detects**: loyalty, member, points, balance, club, rewards
- **Fields**: balance, member info
- **Use case**: Loyalty cards, membership cards

### Coupon (`coupon`)
- **Detects**: coupon, discount, promo, offer, deal, save
- **Fields**: offer details, expiration
- **Use case**: Discount coupons, promotional offers

### Generic (`generic`)
- **Default**: When no specific type is detected
- **Fields**: title, reservation, name, datetime
- **Use case**: General tickets and receipts

## Field Extraction

### Deterministic Extraction
The tool uses regex patterns to extract:
- **Dates**: Various formats (DD/MM/YYYY, YYYY-MM-DD, etc.)
- **Times**: 24-hour and 12-hour formats with AM/PM
- **Seat numbers**: Row/seat combinations (e.g., "Row 5 Seat 12A")
- **Booking codes**: PNR, reservation, confirmation numbers
- **Flight info**: Flight numbers, airport codes (JFK→LAX)
- **Venue info**: Theater names, auditorium numbers

### LLM Enhancement
When `--use-llm` is enabled:
- Sends extracted text and QR payloads to Anthropic Claude
- Uses strict JSON schema validation
- Falls back to deterministic extraction if LLM fails
- Never invents data - only maps/normalizes existing information

## QR Code Handling

- **Exact payload preservation**: Uses the exact decoded QR string as barcode message
- **Multiple QR support**: Generates separate passes for multiple QR codes
- **Fallback**: Uses booking/reservation codes if no QR found
- **OpenCV detection**: Robust QR detection across different image qualities

## Localization

- **Hebrew detection**: Auto-detects Hebrew characters (U+0590-U+05FF)
- **Locale setting**: Sets "he-IL" for Hebrew content, "en-US" otherwise
- **UTF-8 support**: Handles international characters properly

## Error Handling

- **Graceful degradation**: Continues processing even if some steps fail
- **Comprehensive logging**: INFO level for progress, DEBUG for details
- **Exit codes**: Non-zero on fatal errors (missing file, no content)
- **Safe fallbacks**: Omits fields rather than inventing data

## Self-Testing

Run built-in tests to verify functionality:

```bash
python pdf_to_wallet_pass.py --self-test
```

Tests include:
- Date/time parsing
- Pass type detection
- Serial number generation
- Field extraction patterns

## Limitations

- Requires clear text or QR codes in PDF
- Date parsing may need timezone specification for accuracy
- LLM mapping requires API key and internet connection
- Pass signing requires separate Apple Developer certificates

## Requirements

- Python 3.10+
- PyMuPDF (PDF processing)
- OpenCV (QR code detection)
- Pillow (image handling)
- jsonschema (validation)
- anthropic (optional, for LLM features)

## Apple Wallet Integration

The generated pass.json files are compatible with Apple Wallet and include:
- All required Apple Wallet fields
- Proper barcode formatting
- Color schemes for readability
- Localization support
- Type-specific field layouts

To create actual .pkpass files, you'll need to:
1. Add required Apple Wallet assets (icon.png, etc.)
2. Sign with Apple Developer certificates
3. Package as ZIP with .pkpass extension

## Contributing

The tool is designed to be extensible:
- Add new pass types by extending the builder functions
- Improve field extraction by adding regex patterns
- Enhance LLM prompts for better mapping accuracy
- Add support for additional barcode formats
