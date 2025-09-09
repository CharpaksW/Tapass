#!/usr/bin/env python3
"""
PDF to Apple Wallet Pass Converter - Modular Version

A production-ready CLI tool that converts arbitrary ticket/receipt-like PDFs 
into Apple Wallet pass.json payloads with deterministic extraction and optional LLM mapping.

Usage:
    python pdf_to_wallet_pass_modular.py input.pdf \
        --organization "Your Org" \
        --pass-type-id "pass.com.yourorg.generic" \
        --team-id "ABCDE12345" \
        --type generic \
        --tz "+03:00" \
        --outdir out

    # With LLM assistance:
    export OPENAI_API_KEY=sk-***yourkey***
    python pdf_to_wallet_pass_modular.py input.pdf --use-llm --api-key-env OPENAI_API_KEY

Requirements:
    pip install pymupdf opencv-python pillow jsonschema openai python-dateutil numpy

Limitations:
    - Requires clear text and/or QR codes in PDF
    - LLM mapping is optional and falls back to deterministic extraction
    - Supports common date/time formats but may need timezone specification
    - QR payload is used exactly as decoded, not regenerated
"""

import argparse
import json
import logging
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our modular components
try:
    from wallet_pass_converter.processor import WalletPassProcessor
    from wallet_pass_converter.utils import FileUtils, TestRunner
except ImportError as e:
    print(f"Failed to import wallet_pass_converter modules: {e}")
    print("Make sure you're running from the correct directory with the wallet_pass_converter package")
    sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Convert PDF tickets to Apple Wallet passes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument("pdf_path", nargs='?', help="Path to input PDF file")
    parser.add_argument("--organization", default="Test Organization", 
                       help="Organization name for the pass (default: Test Organization)")
    parser.add_argument("--pass-type-id", default="pass.com.testorg.generic", 
                       help="Pass type identifier (default: pass.com.testorg.generic)")
    parser.add_argument("--team-id", default="TEST123456", 
                       help="Apple Developer Team ID (default: TEST123456)")
    parser.add_argument("--type", choices=["eventTicket", "boardingPass", "storeCard", "coupon", "generic"],
                       help="Pass type (auto-detected if not specified)")
    parser.add_argument("--tz", default="+00:00", help="Timezone offset (e.g., +03:00)")
    parser.add_argument("--outdir", default="out", help="Output directory for pass files")
    
    # LLM options
    parser.add_argument("--use-llm", action="store_true", help="Use LLM for field mapping")
    # Note: Only OpenAI provider is supported
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable for API key")
    
    # Utility options
    parser.add_argument("--self-test", action="store_true", help="Run self-tests and exit")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run self-test if requested
    if args.self_test:
        try:
            TestRunner.run_self_tests()
            print("All self-tests passed!")
            return 0
        except Exception as e:
            print(f"Self-test failed: {e}")
            return 1
    
    # Validate required arguments for normal operation
    if not args.pdf_path:
        logger.error("PDF file path is required")
        return 1
    
    # Validate PDF file exists
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF file not found: {args.pdf_path}")
        return 1
    
    # Check LLM requirements
    if args.use_llm:
        if not os.getenv(args.api_key_env):
            logger.error(f"API key not found in environment variable: {args.api_key_env}")
            return 1
    
    try:
        # Create processor and process PDF
        processor = WalletPassProcessor()
        passes = processor.process_pdf(
            pdf_path=args.pdf_path,
            organization=args.organization,
            pass_type_id=args.pass_type_id,
            team_id=args.team_id,
            pass_type=args.type,
            timezone=args.tz,
            use_llm=args.use_llm,
            api_key_env=args.api_key_env
        )
        
        if not passes:
            logger.error("No passes generated")
            return 1
        
        # Output to stdout
        print(json.dumps(passes, indent=2))
        
        # Save to files
        FileUtils.save_passes(passes, args.outdir)
        
        logger.info(f"Successfully processed {args.pdf_path} -> {len(passes)} pass(es)")
        return 0
        
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
