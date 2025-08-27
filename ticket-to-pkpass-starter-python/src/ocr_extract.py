# src/ocr_extract.py
import io, pdfplumber, pytesseract
from PIL import Image
import re

def extract_text_and_images(pdf_path: str):
    text_parts = []
    page_images = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            # Rasterize page at decent resolution for OCR/barcode
            pil = page.to_image(resolution=300).original.convert("RGB")
            # OCR (Hebrew + English if available)
            try:
                t_ocr = pytesseract.image_to_string(pil, lang="heb+eng")
            except:
                t_ocr = pytesseract.image_to_string(pil)
            # Merge
            full = "\n".join([t, t_ocr]).strip()
            text_parts.append(full)
            page_images.append(pil)
    return "\n\n".join(text_parts), page_images

def try_decode_barcodes(images):
    try:
        from pyzbar.pyzbar import decode
    except Exception:
        return None
    for im in images:
        results = decode(im)
        if results:
            # Return first barcode payload as string
            msg = results[0].data.decode("utf-8", errors="ignore")
            fmt = str(results[0].type or "").lower()
            return {"format": fmt, "message": msg}
    return None
