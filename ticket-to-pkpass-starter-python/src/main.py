# src/main.py
import os, sys, json, tempfile, shutil, click
from pathlib import Path

from .email_ingest import fetch_first_pdf
from .ocr_extract import extract_text_and_images, try_decode_barcodes
from .llm_extract import extract_fields
from .pkpass_builder import build_and_sign_pkpass
from .utils import pick_brand_logo, dominant_color_from_image, choose_pass_colors, ensure_images_for_pass

def process_pdf(pdf_path: str, out_path: str):
    # 1) OCR / text extraction
    text, page_images = extract_text_and_images(pdf_path)
    # 2) Try barcode
    barcode = try_decode_barcodes(page_images)
    # 3) Collect hints for LLM/regex
    hints = {}
    if barcode:
        hints["barcode"] = barcode
    # 4) Extract fields (regex + optional LLM)
    fields = extract_fields(text, hints=hints)
    # 5) Determine logo + colors
    brand_name = fields.get("brand") or fields.get("venue") or ""
    logo_path = pick_brand_logo(brand_name)
    dom = dominant_color_from_image(logo_path) if logo_path else (33,150,243)  # default blue
    colors = choose_pass_colors(dom)
    # 6) Ensure Wallet images for this pass (icon, logo, background/strip)
    assets_dir = ensure_images_for_pass(logo_path, colors)
    # 7) Build pass.json + sign -> .pkpass
    out_pkpass = build_and_sign_pkpass(fields, colors, assets_dir, out_path)
    return out_pkpass, fields, colors

@click.command()
@click.option("--pdf", "pdf_path", type=click.Path(exists=True), help="Path to a local PDF ticket.")
@click.option("--imap", is_flag=True, help="Fetch first PDF attachment via IMAP and process it.")
@click.option("--imap-host", default=None, help="IMAP host")
@click.option("--imap-user", default=None, help="IMAP username/email")
@click.option("--imap-pass", default=None, help="IMAP password/app-password")
@click.option("--out", "out_path", default="out_pass.pkpass", help="Output .pkpass path")
def main(pdf_path, imap, imap_host, imap_user, imap_pass, out_path):
    if not pdf_path and not imap:
        click.echo("Provide --pdf <path> or --imap options.", err=True)
        sys.exit(1)

    if imap:
        if not (imap_host and imap_user and imap_pass):
            click.echo("--imap-host, --imap-user, --imap-pass are required with --imap", err=True)
            sys.exit(1)
        tmp_pdf = fetch_first_pdf(imap_host, imap_user, imap_pass)
        if not tmp_pdf:
            click.echo("No PDF attachment found.", err=True)
            sys.exit(2)
        pdf_path = tmp_pdf

    out_pkpass, fields, colors = process_pdf(pdf_path, out_path)
    click.echo(f"✅ Created: {out_pkpass}")
    click.echo("Extracted fields:")
    click.echo(json.dumps(fields, ensure_ascii=False, indent=2))
    click.echo("Colors:")
    click.echo(json.dumps(colors, indent=2))

if __name__ == "__main__":
    main()
