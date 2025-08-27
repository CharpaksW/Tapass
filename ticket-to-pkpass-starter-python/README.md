# Ticket → Apple Wallet (.pkpass) — Python Starter

This starter lets you:
- Parse a **PDF ticket** (local or via **IMAP email**),
- Run **OCR** (Hebrew+English),
- Extract **seat/row/hall/venue/movie/barcode** via regex + optional LLM,
- Pick **brand colors from a logo** and apply **contrast rules** (e.g. orange → black bg, blue → white bg),
- Build and **sign** an **Apple Wallet** `eventTicket` **.pkpass**.

> ⚠️ To sign a `.pkpass`, you need an **Apple Pass Type ID certificate** (P12), its password, and the **Apple WWDR** certificate. Place them locally and point to them via environment variables (see below).

## Quick start

1. **Install system deps** (examples for macOS; adapt for Linux):
   ```bash
   # Tesseract OCR (Hebrew + English)
   brew install tesseract
   brew install tesseract-lang  # or install heb+eng language packs
   # ZBar for barcode decoding (pyzbar needs this)
   brew install zbar
   # Ghostscript is useful; Poppler is helpful for PDF rasterization
   brew install ghostscript poppler
   ```

2. **Create a venv & install Python deps**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Put brand logos** (optional) in `assets/brands/` as PNGs (e.g., `cinema_city.png`, `yes_planet.png`, `lev_cinema.png`).  
   The app tries to map brand names to filenames. If none found, it will still create a pass with default colors.

4. **Configure environment** (copy `.env.example` → `.env` and edit):
   ```bash
   cp .env.example .env
   ```

5. **Process a local PDF**:
   ```bash
   python -m src.main --pdf examples/sample_ticket.pdf --out out_pass.pkpass
   ```

6. **Fetch from email (IMAP)**: (downloads first PDF attachment and processes it)
   ```bash
   python -m src.main --imap --imap-host imap.example.com --imap-user you@example.com --imap-pass 'app-password' --out out_pass.pkpass
   ```

## Notes

- **Signing**: The code uses OpenSSL to sign `manifest.json`. Your **P12** must contain the Pass certificate + private key. The Apple WWDR certificate is needed as `WWDR_CERT_PATH`.
- **LLM** (optional): If `OPENAI_API_KEY` is set, the extractor can call an LLM for robust field extraction. Otherwise, regex-based parsing is used.
- **Colors**: We compute the **dominant color** from the brand logo, then select a contrasting **background**:
  - If the logo is **bright** (high luminance), we choose a **black** background.
  - If the logo is **dark**, we choose a **white** background.
  - These rules match the examples you gave (orange → black bg, blue → white bg).

## Files
- `src/main.py` — CLI & orchestration
- `src/email_ingest.py` — minimal IMAP fetch for PDF attachments
- `src/ocr_extract.py` — PDF → text/images (OCR with Tesseract), barcode decode with pyzbar
- `src/llm_extract.py` — optional LLM JSON extraction (schema enforced), fallback to regex
- `src/pkpass_builder.py` — builds & signs the `.pkpass`
- `src/utils.py` — color utils, brand mapping, helpers
- `assets/icon.png` — mandatory Wallet icon (placeholder)
- `assets/brands/` — put your brand logos here
- `examples/sample_ticket.pdf` — (add your own test PDF)

Good luck! 🚀
