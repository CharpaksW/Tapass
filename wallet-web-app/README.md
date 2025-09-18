# Wallet App Pipeline - Complete Guide

## Overview

This application converts PDF tickets (boarding passes, event tickets, store cards) into Apple Wallet .pkpass files using AI-powered extraction and processing. It includes both a web interface and programmatic API for ticket processing.

## Complete Pipeline Architecture

```
PDF Input
    ↓
OpenAI Vision API (LLM Processing)
    ↓
Structured JSON Data
    ↓
Category Processing (Apple Wallet Format)
    ↓
Apple Wallet JSON
    ↓
.pkpass File Generation
    ↓
Installable Apple Wallet Pass
```

---

## Key Components

### 1. Frontend Web Application (`app.tsx`)

**Purpose:** Web interface for the wallet application

**What it does:**

- Provides user interface for PDF upload
- Handles file drag-and-drop upload to backend
- Displays processing status and results
- Allows users to download generated .pkpass files
- Manages user interactions and feedback

**Key Features:**

- File drag-and-drop upload
- Real-time processing status updates
- Preview of generated wallet passes
- Download links for .pkpass files
- Error handling and user notifications

### 2. Main Processor (`processor.py`)

**Entry Point:** `WalletPassProcessor.process_pdf()`

**What it does:**

- Orchestrates the complete pipeline
- Routes between LLM and traditional processing
- Handles file creation and output

**Usage:**

```python
processor = WalletPassProcessor()
passes = processor.process_pdf(
    pdf_path="ticket.pdf",
    organization="Tapass",
    pass_type_id="pass.tapass",
    team_id="DSW9XCBAK2"
)
```

### 3. LLM Processor (`llm_processor.py`)

**Purpose:** AI-powered PDF data extraction

**What it does:**

- Converts PDF pages to images
- Sends to OpenAI Vision API (gpt-4o model)
- Extracts structured ticket data
- Returns JSON with categories and ticket details

**Categories Supported:**

- `"Boarding pass"` - Flights, trains, buses
- `"Event ticket"` - Concerts, movies, sports
- `"Store card"` - Loyalty cards, coupons
- `"Generic"` - Fallback for unknown types

### 4. Response JSON to PKPass JSON (`response_json_to_pkpass_json.py`)

**Purpose:** Convert LLM data to Apple Wallet format

**What it does:**

- Takes raw LLM JSON response
- Routes to appropriate category processor
- Converts to Apple Wallet pass structure
- Handles multiple tickets automatically

**Main Function:**

```python
process_llm_data_to_wallet_passes(llm_data, organization, pass_type_id, team_id)
```

### 5. Category Processors (`category_processors/`)

**Purpose:** Format-specific Apple Wallet conversion

**Files:**

- `boarding_pass_processor.py` - Flight/transport passes
- `event_ticket_processor.py` - Entertainment tickets
- `store_card_processor.py` - Loyalty/store cards
- `generic_ticket_processor.py` - Fallback processor

**What they do:**

- Map LLM fields to Apple Wallet fields
- Create proper field layouts (primary, secondary, auxiliary, back)
- Generate barcodes and serial numbers
- Format dates and times appropriately

### 6. PKPass Creator (`pkpass_creator.py`)

**Purpose:** Generate final .pkpass files

**What it does:**

- Takes Apple Wallet JSON
- Creates .pkpass archive with certificates
- Signs with Apple certificates
- Outputs installable .pkpass file

---

## How to Test the Pipeline

### Quick Test - Complete Pipeline

```bash
cd backend/app/services/pdf_to_wallet
python test_processor_convince_me.py
```

**What this tests:**

- Complete PDF to .pkpass pipeline
- Real OpenAI API usage
- Multiple ticket handling
- File creation and validation

### Individual Component Tests

#### Test LLM to Apple Wallet JSON Conversion:

```bash
python test_category_processor.py
```

#### Test PKPass Creation Only:

```bash
python pkpass_creator.py generated_passes/1/pass.json --output test.pkpass
```

#### Test with Specific PDF:

```python
from processor import WalletPassProcessor

processor = WalletPassProcessor()
passes = processor.process_pdf("path/to/your/ticket.pdf", "Tapass", "pass.tapass", "DSW9XCBAK2")
print(f"Created {len(passes)} passes")
```

#### Test Frontend Application:

```bash
cd wallet-web-app
npm install
npm start
```

#### Test Web App Complete Flow:

1. **Start the full application**:
   ```bash
   docker-compose up --build
   ```
2. **Access**: http://localhost:3000
3. **Upload PDF** through drag-and-drop interface
4. **Verify** backend processing and file download

---

## File Structure

```
wallet-web-app/
├── app.tsx                               # Frontend React application
├── frontend/                             # Frontend source code
├── backend/                              # Backend API
│   └── app/services/pdf_to_wallet/
│       ├── processor.py                  # Main pipeline orchestrator
│       ├── llm_processor.py              # OpenAI Vision API integration
│       ├── response_json_to_pkpass_json.py # LLM to Apple Wallet converter
│       ├── pkpass_creator.py             # .pkpass file generator
│       ├── category_processors/          # Format-specific processors
│       │   ├── boarding_pass_processor.py
│       │   ├── event_ticket_processor.py
│       │   ├── store_card_processor.py
│       │   └── generic_ticket_processor.py
│       ├── Test_files/                   # Test data
│       │   ├── Jsons/                    # LLM response examples
│       │   └── boarding pass.pdf         # Sample PDF
│       ├── generated_passes/             # Output directory
│       │   ├── 1/pass.json               # Generated Apple Wallet JSON
│       │   └── 2/pass.json
│       └── test_*.py                     # Test files
├── docker-compose.yml                    # Docker configuration
└── README.md                             # This file
```

---

## Setup Requirements

### Environment Variables (`.env`)

```bash
# OpenAI API for LLM processing
OPENAI_API_KEY=your_openai_api_key_here

# Apple Wallet Certificates
PKPASS_CERTIFICATE_PATH=C:\certificates\wallet-app\Certificates.p12
PKPASS_CERTIFICATE_PASSWORD=your_cert_password
APPLE_WWDR_CERT_PATH=C:\certificates\wallet-app\AppleWWDRCA.pem

# SendGrid for email delivery
SENDGRID_API_KEY=your_sendgrid_api_key_here
SENDER_EMAIL=noreply@walletapp.com

# Wallet Pass Configuration
WALLET_ORGANIZATION=Tapass
WALLET_PASS_TYPE_ID=pass.tapass
WALLET_TEAM_ID=DSW9XCBAK2
```

### Dependencies

**Backend:**

```bash
pip install -r requirements.txt
```

**Frontend:**

```bash
npm install
```

**Docker (Recommended):**

```bash
docker-compose up --build
```

---

## Testing Scenarios

### 1. Test New PDF (Backend Only)

1. Place PDF in `Test_files/`
2. Run: `python test_processor_convince_me.py`
3. Check `generated_passes/` for output

### 2. Test Category Processing

1. Create LLM JSON in `Test_files/Jsons/`
2. Run: `python test_category_processor.py`
3. Verify Apple Wallet JSON output

### 3. Test .pkpass Creation

1. Ensure certificates are configured
2. Run: `python pkpass_creator.py generated_passes/1/pass.json`
3. Install .pkpass on iPhone

### 4. Test Web Application

1. Start full app: `docker-compose up --build`
2. Open: http://localhost:3000
3. Upload PDF through web interface
4. Check email for .pkpass files

### 5. Test API Directly

```bash
curl -X POST "http://localhost:8000/api/process" \
  -F "file=@ticket.pdf" \
  -F "email=test@example.com"
```

### 6. Production Test

```python
# Complete end-to-end test
processor = WalletPassProcessor()
passes = processor.process_pdf("real_ticket.pdf", "Tapass", "pass.tapass", "DSW9XCBAK2")

# Each pass will have:
# - Complete Apple Wallet JSON structure
# - '_pkpass_file' field with path to installable file
```

---

## Features

### Web Application

- **Simple UX**: Drag-and-drop PDF upload with email delivery
- **Secure**: Rate limiting, file validation, CORS protection
- **Responsive**: Mobile-friendly design with accessibility features
- **Production Ready**: Docker containerized with health checks
- **Email Integration**: SendGrid powered email delivery
- **Fast**: React + TypeScript frontend, FastAPI backend

### PDF Processing

- **AI Enhanced**: OpenAI Vision API processing
- **Advanced PDF Processing**: QR code detection, text extraction, field parsing
- **Multi-format Support**: Event tickets, boarding passes, store cards, coupons
- **Multi-language**: Hebrew and English text processing
- **Fallback Processing**: Deterministic extraction if AI fails

### Supported Pass Types

- **Event Tickets**: Concerts, movies, sports (seat, venue, datetime)
- **Boarding Passes**: Flights (origin, destination, flight number, PNR)
- **Store Cards**: Loyalty cards, memberships (balance, member info)
- **Coupons**: Discounts, promotions (offer details, expiration)
- **Generic**: General tickets and receipts

---

## API Endpoints

### POST /api/process

Convert PDF to wallet pass and email result.

**Request**:

- `file`: PDF file (max 10MB)
- `email`: Email address

**Response**:

```json
{
  "ok": true
}
```

### GET /api/health

Health check endpoint.

**Response**:

```json
{
  "status": "healthy"
}
```

---

## Debugging Tips

### Common Issues:

- **LLM not working:** Check `OPENAI_API_KEY` in `.env`
- **PKPass creation fails:** Verify certificate paths and passwords
- **Import errors:** Run tests from `pdf_to_wallet` directory
- **No tickets found:** Check PDF quality and content
- **Frontend connection issues:** Verify backend API endpoints
- **Email not sending:** Check SendGrid API key and sender verification

### Useful Logs:

- **LLM responses:** Check console output for JSON structure
- **PKPass creation:** Look for `pkpass_creator.py` subprocess output
- **File locations:** Generated files logged with full paths
- **Frontend errors:** Check browser console and network tab
- **Docker logs:** `docker-compose logs backend` or `docker-compose logs frontend`

### Debug Commands:

```bash
# Check backend logs
docker-compose logs backend

# Check frontend logs
docker-compose logs frontend

# Test backend health
curl http://localhost:8000/api/health

# Run backend tests
cd backend/app/services/pdf_to_wallet
python test_processor_convince_me.py
```

---

## Expected Results

**Input:** PDF with boarding pass
**Output:**

- 2 Apple Wallet JSON files in `generated_passes/1/` and `generated_passes/2/`
- 2 installable .pkpass files
- Complete ticket details extracted and formatted
- Ready for iPhone Wallet installation

**Example Output Structure:**

```json
{
  "formatVersion": 1,
  "passTypeIdentifier": "pass.tapass",
  "teamIdentifier": "DSW9XCBAK2",
  "organizationName": "Tapass",
  "description": "EL AL LY5107",
  "serialNumber": "TICKET_1142489970334",
  "boardingPass": {
    "transitType": "PKTransitTypeAir",
    "primaryFields": [
      { "key": "flight", "label": "Flight", "value": "EL AL LY5107" }
    ],
    "secondaryFields": [
      { "key": "departureTime", "label": "Departure", "value": "05:35 AM" }
    ],
    "auxiliaryFields": [{ "key": "seat", "label": "Seat", "value": "14B" }],
    "backFields": [
      { "key": "confirmationCode", "label": "Confirmation", "value": "K9D2RR" }
    ]
  },
  "barcodes": [{ "format": "PKBarcodeFormatQR", "message": "K9D2RR" }],
  "relevantDate": "2025-03-24T05:35:00+00:00"
}
```

---

## Quick Start for Testing

1. **Clone and setup**:

   ```bash
   cd wallet-web-app
   cp env.example .env
   # Edit .env with your API keys
   ```

2. **Test backend pipeline only**:

   ```bash
   cd backend/app/services/pdf_to_wallet
   python test_processor_convince_me.py
   ```

3. **Test full web application**:

   ```bash
   docker-compose up --build
   # Open http://localhost:3000
   ```

4. **Access the application**:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

The pipeline transforms any ticket PDF into production-ready Apple Wallet passes automatically through both programmatic API and web interface!

---

## Architecture Summary

- **Frontend**: React + TypeScript + Vite + TailwindCSS
- **Backend**: FastAPI + Python with async email processing
- **AI Processing**: OpenAI Vision API (gpt-4o)
- **Email**: SendGrid API integration
- **Deployment**: Docker Compose with multi-stage builds
- **Security**: Rate limiting, file validation, CORS protection

This application provides a complete solution for converting PDF tickets to Apple Wallet passes with both web interface and programmatic access.
