# PDF to Wallet Web App

A production-ready web application that converts PDF tickets to Apple Wallet passes via a clean drag-and-drop interface.

## Features

- 🎯 **Simple UX**: Drag-and-drop PDF upload with email delivery
- 🔒 **Secure**: Rate limiting, file validation, CORS protection
- 📱 **Responsive**: Mobile-friendly design with accessibility features
- 🚀 **Production Ready**: Docker containerized with health checks
- 📧 **Email Integration**: SendGrid powered email delivery
- ⚡ **Fast**: React + TypeScript frontend, FastAPI backend
- 🤖 **AI Enhanced**: Optional LLM processing with Anthropic Claude
- 📄 **Advanced PDF Processing**: QR code detection, text extraction, field parsing
- 🎫 **Multi-format Support**: Event tickets, boarding passes, store cards, coupons

## Architecture

- **Frontend**: React + TypeScript + Vite + TailwindCSS
- **Backend**: FastAPI + Python with async email processing
- **Email**: SendGrid API integration
- **Deployment**: Docker Compose with multi-stage builds

## Quick Start

1. **Clone and setup**:
   ```bash
   cd wallet-web-app
   cp env.example .env
   ```

2. **Configure SendGrid**:
   - Sign up at [SendGrid](https://sendgrid.com/)
   - Create an API key with Mail Send permissions
   - Add your API key to `.env`:
     ```
     SENDGRID_API_KEY=your_actual_api_key_here
     ```

3. **Run with Docker**:
   ```bash
   docker-compose up --build
   ```

4. **Access the app**:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Development

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### Backend Development
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

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

**Error Response**:
```json
{
  "ok": false,
  "error": "Error message"
}
```

## Security Features

- ✅ File type validation (PDF only)
- ✅ File size limits (10MB max)
- ✅ Email format validation
- ✅ Rate limiting (5 requests per 5 minutes per IP)
- ✅ CORS protection
- ✅ Input sanitization
- ✅ No file persistence (memory-only processing)
- ✅ Secure headers (nginx)

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `SENDGRID_API_KEY` | SendGrid API key | Yes | - |
| `SENDER_EMAIL` | Verified sender email | No | noreply@walletapp.com |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key (for LLM) | No | - |
| `WALLET_ORGANIZATION` | Organization name for passes | No | Wallet App |
| `WALLET_PASS_TYPE_ID` | Apple Pass Type ID | No | pass.com.walletapp.generic |
| `WALLET_TEAM_ID` | Apple Developer Team ID | No | DEMO123456 |

### Rate Limiting

- **Default**: 5 requests per 5 minutes per IP
- **Configurable**: Edit `RateLimiter` parameters in `backend/app/main.py`

### File Limits

- **Max Size**: 10MB
- **Allowed Types**: PDF only (`application/pdf`)

## PDF Processing

The app uses advanced PDF processing capabilities:

### Deterministic Extraction
- **Text Extraction**: PyMuPDF for reliable text parsing
- **QR Code Detection**: OpenCV with multiple preprocessing methods
- **Field Parsing**: Regex-based extraction of dates, seats, venues, etc.
- **Type Detection**: Auto-detects pass types (event, boarding, store card, coupon)

### AI Enhancement (Optional)
- **LLM Processing**: Anthropic Claude for intelligent field mapping
- **Multi-language Support**: Hebrew and English text processing
- **Fallback**: Always falls back to deterministic extraction if LLM fails

### Supported Pass Types
- 🎫 **Event Tickets**: Concerts, movies, sports (seat, venue, datetime)
- ✈️ **Boarding Passes**: Flights (origin, destination, flight number, PNR)
- 🛍️ **Store Cards**: Loyalty cards, memberships (balance, member info)
- 🎟️ **Coupons**: Discounts, promotions (offer details, expiration)
- 📋 **Generic**: General tickets and receipts

## Email Template

The app sends a professional email with:
- HTML formatted message
- JSON attachment named `wallet.json`
- Clear instructions for the recipient

## Error Handling

The app provides user-friendly error messages for:
- Invalid file types
- File size exceeded
- Invalid email format
- Rate limit exceeded
- Processing failures
- Network errors

## Monitoring

### Health Checks
- **API**: `GET /api/health`
- **Docker**: Built-in container health checks
- **Frontend**: Nginx status monitoring

### Logging
- Request/response logging
- Error tracking
- Performance metrics
- Security event logging

## Production Deployment

1. **Set up SendGrid**:
   - Verify your sender domain
   - Configure authentication
   - Set up dedicated IP (optional)

2. **Configure environment**:
   ```bash
   cp env.example .env
   # Edit .env with production values
   ```

3. **Deploy**:
   ```bash
   docker-compose -f docker-compose.yml up -d
   ```

4. **Set up reverse proxy** (recommended):
   - Use nginx/Apache for SSL termination
   - Configure domain routing
   - Set up monitoring/logging

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
1. Check the [Issues](../../issues) page
2. Review the API documentation at `/docs`
3. Check container logs: `docker-compose logs`
