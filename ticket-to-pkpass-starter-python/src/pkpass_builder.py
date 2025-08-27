# src/pkpass_builder.py
import os, json, hashlib, subprocess, tempfile, shutil
from pathlib import Path
from .utils import build_pass_json

def _sha1_of(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()

def _write_manifest(tmpdir):
    manifest = {}
    for fname in os.listdir(tmpdir):
        fpath = os.path.join(tmpdir, fname)
        if os.path.isfile(fpath) and fname != "signature":  # signature is created after manifest
            manifest[fname] = _sha1_of(fpath)
    mpath = os.path.join(tmpdir, "manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2)
    return mpath

def _sign_manifest(manifest_path, tmpdir):
    p12_path = os.getenv("PASS_CERT_P12_PATH")
    p12_pass = os.getenv("PASS_CERT_P12_PASSWORD", "")
    wwdr_path = os.getenv("WWDR_CERT_PATH")
    if not (p12_path and wwdr_path and os.path.exists(p12_path) and os.path.exists(wwdr_path)):
        raise RuntimeError("Missing PASS_CERT_P12_PATH / PASS_CERT_P12_PASSWORD / WWDR_CERT_PATH or files not found.")

    cert_pem = os.path.join(tmpdir, "cert.pem")
    key_pem  = os.path.join(tmpdir, "key.pem")
    # Extract cert and key from P12
    subprocess.check_call(["openssl","pkcs12","-in",p12_path,"-clcerts","-nokeys","-out",cert_pem,"-passin",f"pass:{p12_pass}"])
    subprocess.check_call(["openssl","pkcs12","-in",p12_path,"-nocerts","-out",key_pem,"-passin",f"pass:{p12_pass}","-passout","pass:tmp"])

    sig_path = os.path.join(tmpdir, "signature")
    subprocess.check_call([
        "openssl","smime","-binary","-sign",
        "-signer",cert_pem,
        "-inkey",key_pem,
        "-certfile",wwdr_path,
        "-in",manifest_path,
        "-out",sig_path,
        "-outform","DER",
        "-passin","pass:tmp"
    ])
    return sig_path

def build_and_sign_pkpass(fields, colors, assets_dir, out_path):
    tmpdir = tempfile.mkdtemp()
    try:
        # 1) Write pass.json
        pass_json = build_pass_json(fields, colors)
        with open(os.path.join(tmpdir, "pass.json"), "w", encoding="utf-8") as f:
            json.dump(pass_json, f, ensure_ascii=False, indent=2)

        # 2) Copy images (icon/logo/background/strip if exist)
        for name in ["icon.png","icon@2x.png","logo.png","logo@2x.png","background.png","strip.png"]:
            src = os.path.join(assets_dir, name)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(tmpdir, name))

        # 3) manifest.json
        mpath = _write_manifest(tmpdir)
        # 4) signature
        _sign_manifest(mpath, tmpdir)
        # 5) Zip -> .pkpass
        out_path = os.path.abspath(out_path)
        with open(out_path, "wb") as outf:
            import zipfile
            with zipfile.ZipFile(outf, "w", zipfile.ZIP_DEFLATED) as z:
                for fname in os.listdir(tmpdir):
                    z.write(os.path.join(tmpdir, fname), arcname=fname)
        return out_path
    finally:
        # keep tmp for debugging? For now we clean
        import shutil as _shutil
        _shutil.rmtree(tmpdir, ignore_errors=True)
