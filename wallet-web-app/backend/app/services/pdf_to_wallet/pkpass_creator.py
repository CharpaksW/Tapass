#!/usr/bin/env python3
"""
PKPass Creator - End-to-end .pkpass file generation

This script creates signed .pkpass files from JSON pass data using OpenSSL
and certificate information from environment variables.

Usage:
    python pkpasscreator.py input.json [output_directory]
    
Environment Variables Required:
    - PKPASS_CERTIFICATE_PATH: Path to the P12 certificate file
    - PKPASS_CERTIFICATE_PASSWORD: Password for the P12 certificate  
    - APPLE_WWDR_CERT_PATH: Path to Apple WWDR certificate (PEM format)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from zipfile import ZipFile, ZIP_DEFLATED

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

REQ_JSON_KEYS = [
    "formatVersion", "passTypeIdentifier", "teamIdentifier",
    "serialNumber", "organizationName", "description"
]

def run(cmd, cwd=None, check=True):
    """Run external command with clean output and unified display."""
    print("$", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and proc.returncode != 0:
        print(proc.stdout)
        raise SystemExit(f"Command failed: {' '.join(cmd)}")
    return proc.stdout

def assert_exists(path: Path, label: str):
    """Check if file exists, raise error if not."""
    if not path.is_file():
        raise SystemExit(f" Missing file {label}: {path}")

def load_pass_json(path: Path):
    """Load and validate pass.json file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f" Invalid pass.json or not UTF-8: {e}")
    missing = [k for k in REQ_JSON_KEYS if k not in data]
    if missing:
        raise SystemExit(f" Missing required keys in pass.json: {', '.join(missing)}")
    return data

def extract_uid_ou_from_p12(p12_path: Path, cert_password: str):
    """Extract UID and OU from P12 certificate."""
    out = run(["openssl", "pkcs12", "-in", str(p12_path), "-info", "-nokeys", "-passin", f"pass:{cert_password}"], check=True)
    # Example lines: "subject=UID = pass.com.x, CN = Pass Type ID: pass.com.x, OU = ABCDE12345, ..."
    uid = None
    ou  = None
    for line in out.splitlines():
        if "subject=" in line:
            m_uid = re.search(r"UID\s*=\s*([^,]+)", line)
            m_ou  = re.search(r"OU\s*=\s*([^,]+)", line)
            if m_uid: uid = m_uid.group(1).strip()
            if m_ou:  ou  = m_ou.group(1).strip()
    if not uid or not ou:
        print(" Could not extract UID/OU from P12; continuing anyway, verify match manually.")
    else:
        print(f"Detected from P12 → UID={uid}  OU={ou}")
    return uid, ou

def copy_inputs_to_build(build_dir: Path, assets_dir: Path = None):
    """Copy asset files that will be included in the pass to build directory."""
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Required image assets (pass.json is handled separately)
    must = ["icon.png", "icon@2x.png"]
    optional = [
        "logo.png", "logo@2x.png",
        "background.png", "background@2x.png",
        "strip.png", "strip@2x.png",
        "thumbnail.png", "thumbnail@2x.png",
    ]
    
    # If assets_dir is provided, copy from there, otherwise from current directory
    base_dir = assets_dir if assets_dir else Path(".")
    
    for name in must:
        src = base_dir / name
        assert_exists(src, name)
        shutil.copy2(src, build_dir / name)
        print(f"📎 Added required asset: {name}")
        
    for name in optional:
        src = base_dir / name
        if src.is_file():
            shutil.copy2(src, build_dir / name)
            print(f"📎 Added optional asset: {name}")
    
    # Localization directories *.lproj (if any)
    for item in Path(".").glob("*.lproj"):
        if item.is_dir():
            shutil.copytree(item, build_dir / item.name, dirs_exist_ok=True)
    
    # Clean up .DS_Store files if copied
    for ds in build_dir.rglob(".DS_Store"):
        try: ds.unlink()
        except: pass

def build_manifest(build_dir: Path):
    """Create manifest.json for all files in the pass (root and *.lproj), excluding manifest/signature/hidden files."""
    manifest = {}
    for base, dirs, files in os.walk(build_dir):
        rel_base = Path(base).relative_to(build_dir)
        # Include root or *.lproj only
        if str(rel_base) != "." and not str(rel_base).endswith(".lproj"):
            continue
        # Don't access hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".") and (d.endswith(".lproj") or str(rel_base) == ".")]
        for fn in files:
            if fn in ("manifest.json", "signature") or fn.startswith("."):
                continue
            path = Path(base) / fn
            rel  = path.relative_to(build_dir).as_posix()
            # Calculate SHA-1
            with open(path, "rb") as f:
                digest = hashlib.sha1(f.read()).hexdigest()
            manifest[rel] = digest
    if not manifest:
        raise SystemExit(" manifest.json is empty — check that pass.json and icon.png exist in the project directory.")
    out_path = build_dir / "manifest.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest.json created ({len(manifest)} items)")
    return out_path

def sign_manifest(build_dir: Path, signer_cert_pem: Path, signer_key_pem: Path, wwdr_pem: Path):
    """Sign the manifest.json file."""
    sig_path = build_dir / "signature"
    run([
        "openssl", "smime", "-binary", "-sign",
        "-signer", str(signer_cert_pem),
        "-inkey", str(signer_key_pem),
        "-certfile", str(wwdr_pem),
        "-in", str(build_dir / "manifest.json"),
        "-out", str(sig_path),
        "-outform", "DER"
    ], check=True)
    # Verification
    verify = subprocess.run([
        "openssl", "smime", "-verify",
        "-in", str(sig_path), "-inform", "DER",
        "-content", str(build_dir / "manifest.json"),
        "-certfile", str(wwdr_pem), "-noverify", "-out", "/dev/null" if os.name != 'nt' else "NUL"
    ])
    if verify.returncode != 0:
        raise SystemExit("❌ Signature verification failed")
    print("Signature OK")
    return sig_path

def zip_pkpass(build_dir: Path, out_path: Path):
    """Create the final .pkpass ZIP file."""
    if out_path.exists():
        out_path.unlink()
    # Ensure there are no metadata files
    for junk in build_dir.rglob("__MACOSX"):
        shutil.rmtree(junk, ignore_errors=True)
    for ds in build_dir.rglob(".DS_Store"):
        try: ds.unlink()
        except: pass
    # Create ZIP as .pkpass with relative file paths
    with ZipFile(out_path, "w", ZIP_DEFLATED) as zf:
        for p in sorted(build_dir.rglob("*")):
            if p.is_dir(): continue
            rel = p.relative_to(build_dir)
            # Don't include hidden files that aren't required
            if rel.name.startswith("."): continue
            zf.write(p, arcname=str(rel))
    print(f"Created file: {out_path}")
    # Print contents
    with ZipFile(out_path, "r") as zf:
        print("pkpass contents:")
        for zi in zf.infolist():
            print("  ", zi.filename)


class PKPassCreator:
    """Creates PKPass files from JSON data using OpenSSL and environment variables."""
    
    def __init__(self):
        """Initialize with certificate paths from environment variables."""
        self.cert_path = os.getenv("PKPASS_CERTIFICATE_PATH")
        self.cert_password = os.getenv("PKPASS_CERTIFICATE_PASSWORD") 
        self.wwdr_cert_path = os.getenv("APPLE_WWDR_CERT_PATH")
        
        if not self.cert_path:
            raise ValueError(" PKPASS_CERTIFICATE_PATH environment variable not set")
        if not self.cert_password:
            raise ValueError(" PKPASS_CERTIFICATE_PASSWORD environment variable not set")
        if not self.wwdr_cert_path:
            raise ValueError(" APPLE_WWDR_CERT_PATH environment variable not set")
        
        # Verify files exist
        if not Path(self.cert_path).exists():
            raise ValueError(f" Certificate file not found: {self.cert_path}")
        if not Path(self.wwdr_cert_path).exists():
            raise ValueError(f" WWDR certificate file not found: {self.wwdr_cert_path}")
        
        print(f" Certificate: {self.cert_path}")
        print(f" WWDR Certificate: {self.wwdr_cert_path}")
    
    def generate_pkpass(self, json_file: str, output_dir: Optional[str] = None, assets_dir: Optional[str] = None) -> str:
        """Generate a .pkpass file from JSON input.
        
        Args:
            json_file: Path to JSON file containing pass data
            output_dir: Directory to save the .pkpass file (optional)
            assets_dir: Directory containing icon and other assets (optional)
        
        Returns:
            Path to the generated .pkpass file
        """
        json_path = Path(json_file)
        if not json_path.exists():
            raise ValueError(f"JSON file not found: {json_file}")
        
        # Load and validate pass data
        pass_data = load_pass_json(json_path)
        
        # Determine output path
        if output_dir is None:
            output_dir = json_path.parent
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate output filename
        serial_number = pass_data.get('serialNumber', 'UNKNOWN')
        output_file = output_dir / f"{serial_number}.pkpass"
        
        print(f" Generating PKPass: {output_file}")
        
        # Determine assets directory
        if assets_dir:
            assets_path = Path(assets_dir)
        else:
            # Default to app/assets directory
            assets_path = Path(__file__).parent.parent.parent / 'assets'
        
        # Check if required assets exist
        required_assets = ['icon.png', 'icon@2x.png']
        for asset in required_assets:
            if not (assets_path / asset).exists():
                raise ValueError(f"Required asset missing: {asset} in {assets_path}")
        
        # Create build directory
        with tempfile.TemporaryDirectory() as temp_dir:
            build_dir = Path(temp_dir) / "build_pkpass"
            build_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy pass.json to build directory
            shutil.copy2(json_path, build_dir / 'pass.json')
            
            # Copy assets to build directory
            copy_inputs_to_build(build_dir, assets_path)
            
            # Extract PEMs from P12 in temp directory
            signer_cert_pem = Path(temp_dir) / "signerCert.pem"
            signer_key_pem = Path(temp_dir) / "signerKey.pem"
            
            # Extract certificate (public key) - try without -legacy first, then with if needed
            cert_cmd = ["openssl", "pkcs12", "-passin", f"pass:{self.cert_password}", 
                       "-in", str(self.cert_path), "-clcerts", "-nokeys", "-out", str(signer_cert_pem)]
            
            try:
                run(cert_cmd)
            except SystemExit:
                # If command failed, try with -legacy flag for OpenSSL 3.x compatibility
                print(" OpenSSL command failed, retrying with -legacy flag...")
                cert_cmd_legacy = ["openssl", "pkcs12", "-legacy", "-passin", f"pass:{self.cert_password}",
                                  "-in", str(self.cert_path), "-clcerts", "-nokeys", "-out", str(signer_cert_pem)]
                run(cert_cmd_legacy)
            
            # Extract private key (without password protection) - try without -legacy first, then with if needed
            key_cmd = ["openssl", "pkcs12", "-passin", f"pass:{self.cert_password}",
                      "-in", str(self.cert_path), "-nocerts", "-nodes", "-out", str(signer_key_pem)]
            
            try:
                run(key_cmd)
            except SystemExit:
                # If command failed, try with -legacy flag for OpenSSL 3.x compatibility
                print(" OpenSSL command failed, retrying with -legacy flag...")
                key_cmd_legacy = ["openssl", "pkcs12", "-legacy", "-passin", f"pass:{self.cert_password}",
                                 "-in", str(self.cert_path), "-nocerts", "-nodes", "-out", str(signer_key_pem)]
                run(key_cmd_legacy)
            
            # Create manifest
            build_manifest(build_dir)

            # Sign manifest
            sign_manifest(build_dir, signer_cert_pem, signer_key_pem, Path(self.wwdr_cert_path))
            
            # Create final .pkpass file
            zip_pkpass(build_dir, output_file)
            
            print(f" PKPass created successfully: {output_file}")
            print(f" File size: {output_file.stat().st_size} bytes")
            
            return str(output_file)


def main():
    """Main entry point - supports both environment variables and command line arguments."""
    ap = argparse.ArgumentParser(description="Build .pkpass file from pass.json + images + certificates")
    ap.add_argument("json_file", nargs="?", default="pass.json", help="Path to pass.json file")
    ap.add_argument("--output", "-o", help="Output .pkpass file path")
    ap.add_argument("--assets-dir", help="Directory containing icon and other assets")
    args = ap.parse_args()
    
    # Check for pass.json in current directory first
    json_file = args.json_file
    if not Path(json_file).exists():
        print(f" Error: JSON file not found: {json_file}")
        print("\nUsage: python pkpasscreator.py [pass.json] [--output output.pkpass] [--assets-dir /path/to/assets]")
        print("\nEnvironment Variables Required:")
        print("  - PKPASS_CERTIFICATE_PATH: Path to the P12 certificate file")
        print("  - PKPASS_CERTIFICATE_PASSWORD: Password for the P12 certificate")
        print("  - APPLE_WWDR_CERT_PATH: Path to Apple WWDR certificate (PEM format)")
        sys.exit(1)
    
    try:
        print(" Initializing PKPass creator...")
        creator = PKPassCreator()
        
        print(" Generating PKPass...")
        output_path = creator.generate_pkpass(
            json_file=json_file,
            output_dir=Path(args.output).parent if args.output else None,
            assets_dir=args.assets_dir
        )
        
        print(f"\n Success! PKPass file created:")
        print(f"    {output_path}")
        print(f"\n You can now:")
        print(f"   - Email this file to test on iPhone/Apple Watch")
        print(f"   - Open it in Apple Configurator for testing")
        print(f"   - Deploy it to your app/website with Content-Type: application/vnd.apple.pkpass")
        
        return 0
        
    except ValueError as e:
        print(f" Validation Error: {e}")
        return 2
    except FileNotFoundError as e:
        print(f" File Error: {e}")
        return 3
    except Exception as e:
        print(f" Unexpected Error: {e}")
        return 1

if __name__ == "__main__":
    main()
