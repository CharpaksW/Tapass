# src/utils.py
import os, io, json, colorsys
from PIL import Image, ImageOps

BRAND_MAP = {
    # normalized name fragment -> asset filename
    "cinema city": "cinema_city.png",
    "yes planet": "yes_planet.png",
    "יס פלנט": "yes_planet.png",
    "סינמה סיטי": "cinema_city.png",
    "lev": "lev_cinema.png",
    "לב": "lev_cinema.png",
}

def normalize_name(name: str) -> str:
    return (name or "").strip().lower()

def pick_brand_logo(brand_or_venue: str):
    logos_dir = os.getenv("BRAND_LOGOS_DIR", "./assets/brands")
    n = normalize_name(brand_or_venue)
    for key, fname in BRAND_MAP.items():
        if key in n:
            path = os.path.join(logos_dir, fname)
            if os.path.exists(path):
                return path
    # fallback: try to map by words to any file in dir
    if os.path.isdir(logos_dir):
        for f in os.listdir(logos_dir):
            if f.lower().endswith(".png") and any(w in f.lower() for w in n.split() if w):
                return os.path.join(logos_dir, f)
    return None

def dominant_color_from_image(path: str):
    im = Image.open(path).convert("RGBA")
    # Downsize for speed
    im = ImageOps.contain(im, (64, 64))
    # Ignore transparent/near-white pixels
    pixels = [
        p for p in im.getdata()
        if p[3] > 10 and not (p[0] > 240 and p[1] > 240 and p[2] > 240)
    ]
    if not pixels:
        return (33,150,243)
    # simple histogram for most common
    from collections import Counter
    rgb = [(r,g,b) for (r,g,b,a) in pixels]
    ((r,g,b), _) = Counter(rgb).most_common(1)[0]
    return (int(r), int(g), int(b))

def relative_luminance(rgb):
    # WCAG-ish luminance
    def chan(c):
        c = c/255.0
        return c/12.92 if c <= 0.03928*255 else ((c+0.055)/1.055)**2.4
    r, g, b = rgb
    return 0.2126*chan(r*255/255) + 0.7152*chan(g*255/255) + 0.0722*chan(b*255/255)

def choose_pass_colors(logo_rgb):
    # If logo is bright -> black background, else white background
    r, g, b = logo_rgb
    # Perceived luminance
    lum = (0.2126*r + 0.7152*g + 0.0722*b)/255.0
    if lum >= 0.55:
        background = (0,0,0)
        foreground = (255,255,255)
    else:
        background = (255,255,255)
        foreground = (0,0,0)
    # Label color can track foreground
    return {
        "logoColor": f"rgb({r},{g},{b})",
        "backgroundColor": f"rgb({background[0]},{background[1]},{background[2]})",
        "foregroundColor": f"rgb({foreground[0]},{foreground[1]},{foreground[2]})",
        "labelColor": f"rgb({foreground[0]},{foreground[1]},{foreground[2]})"
    }

def _save_if_not_exists(path, image: Image.Image):
    if not os.path.exists(path):
        image.save(path)

def ensure_images_for_pass(logo_path, colors):
    # Prepare a temp assets dir with icon/logo/background/strip
    import tempfile, shutil
    tmp_assets = tempfile.mkdtemp()
    # icon.png is required; try project assets, else draw a placeholder
    default_icon = os.path.join("./assets", "icon.png")
    if os.path.exists(default_icon):
        shutil.copy(default_icon, os.path.join(tmp_assets, "icon.png"))
    else:
        im = Image.new("RGBA", (256,256), (0,0,0,255))
        im.save(os.path.join(tmp_assets, "icon.png"))

    # logo (optional)
    if logo_path and os.path.exists(logo_path):
        # copy + create @2x
        logo = Image.open(logo_path).convert("RGBA")
        logo_small = ImageOps.contain(logo, (160, 50))
        logo_big   = ImageOps.contain(logo, (320, 100))
        logo_small.save(os.path.join(tmp_assets, "logo.png"))
        logo_big.save(os.path.join(tmp_assets, "logo@2x.png"))

    # background or strip (solid color)
    bg = Image.new("RGB", (1125, 375), _rgb_tuple(colors["backgroundColor"]))
    bg.save(os.path.join(tmp_assets, "background.png"))
    # small strip alternative (deprecated on new styles, but okay for compatibility)
    strip = Image.new("RGB", (624, 246), _rgb_tuple(colors["backgroundColor"]))
    strip.save(os.path.join(tmp_assets, "strip.png"))
    return tmp_assets

def _rgb_tuple(rgb_str: str):
    # parse "rgb(r,g,b)" into tuple
    inside = rgb_str.strip()[4:-1]
    r,g,b = [int(x) for x in inside.split(",")]
    return (r,g,b)

def build_pass_json(fields, colors):
    # Minimal eventTicket pass.json with colors + barcode
    pti = os.getenv("PASS_TYPE_IDENTIFIER", "pass.com.yourcompany.tickets")
    team = os.getenv("TEAM_IDENTIFIER", "ABCD123456")
    org  = os.getenv("ORGANIZATION_NAME", "Your Company")
    barcode = fields.get("barcode") or {}
    bfmt = (barcode.get("format","") or "qr").upper()
    # Map to PassKit enum
    fmt_map = {
        "QR": "PKBarcodeFormatQR",
        "PDF417": "PKBarcodeFormatPDF417",
        "CODE128": "PKBarcodeFormatCode128"
    }
    pass_barcode = {
        "format": fmt_map.get(bfmt, "PKBarcodeFormatQR"),
        "message": barcode.get("message",""),
        "messageEncoding": "iso-8859-1",
        "altText": barcode.get("altText","")
    }

    event = fields.get("event_name","Event")
    venue = fields.get("venue","")
    date  = fields.get("date","")
    hall  = fields.get("hall","")
    row   = fields.get("row","")
    seat  = fields.get("seat","")
    ticket_number = fields.get("ticket_number","")

    pass_json = {
        "formatVersion": 1,
        "passTypeIdentifier": pti,
        "teamIdentifier": team,
        "organizationName": org,
        "description": "Event ticket",
        "serialNumber": ticket_number or "SN",
        "foregroundColor": colors["foregroundColor"],
        "backgroundColor": colors["backgroundColor"],
        "labelColor": colors["labelColor"],
        "eventTicket": {
            "primaryFields": [
                { "key": "event", "label": "Event", "value": event }
            ],
            "secondaryFields": [
                { "key": "venue", "label": "Venue", "value": venue },
                { "key": "date", "label": "Date", "value": date }
            ],
            "auxiliaryFields": [
                { "key": "hall", "label": "Hall", "value": hall },
                { "key": "row",  "label": "Row",  "value": row  },
                { "key": "seat", "label": "Seat", "value": seat }
            ],
            "backFields": [
                { "key": "ticket", "label": "Ticket #", "value": ticket_number }
            ]
        },
        "barcode": pass_barcode
    }
    return pass_json
