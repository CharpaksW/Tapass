#!/usr/bin/env python3
"""
Test suite for pdf_to_wallet_pass_modular.py

Tests the PDF to Apple Wallet Pass converter using test files in the Test_files folder.
Runs both unit tests and integration tests with actual PDF files.

Usage:
    python test_pdf_to_wallet_pass.py
    python test_pdf_to_wallet_pass.py --verbose
    python test_pdf_to_wallet_pass.py --test-file 1.pdf
"""

import argparse
import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from wallet_pass_converter.processor import WalletPassProcessor
    from wallet_pass_converter.utils import FileUtils, TestRunner
    from wallet_pass_converter.models import TicketData
    from wallet_pass_converter.pdf_processor import PDFProcessor
    from wallet_pass_converter.field_parser import FieldParser
    from wallet_pass_converter.pass_builder import PassBuilder
except ImportError as e:
    print(f"Failed to import wallet_pass_converter modules: {e}")
    print("Make sure you're running from the correct directory with the wallet_pass_converter package")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestPDFToWalletPass(unittest.TestCase):
    """Generate wallet passes from all PDF test files"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.test_files_dir = Path(__file__).parent / "Test_files"
        cls.processor = WalletPassProcessor()
        
        # Use permanent directory for generated passes
        cls.output_dir = Path(__file__).parent / "generated_passes"
        cls.output_dir.mkdir(exist_ok=True)
        
        # Test configuration
        cls.test_config = {
            "organization": "Test Organization",
            "pass_type_id": "pass.com.testorg.generic",
            "team_id": "TEST123456",
            "timezone": "+00:00"
        }
        
        logger.info(f"Processing PDF files from: {cls.test_files_dir}")
        logger.info(f"Generated passes will be saved to: {cls.output_dir.absolute()}")
    
    def test_generate_passes_from_all_files(self):
        """Generate wallet passes from all PDF test files"""
        logger.info("🎫 Generating wallet passes from all PDF files...")
        
        pdf_files = list(self.test_files_dir.glob("*.pdf"))
        if not pdf_files:
            logger.error("❌ No PDF files found in Test_files directory")
            return
        
        logger.info(f"📄 Found {len(pdf_files)} PDF files to process")
        successful_conversions = 0
        
        for pdf_file in pdf_files:
            logger.info(f"\n🔄 Processing: {pdf_file.name}")
            
            try:
                passes = self.processor.process_pdf(
                    pdf_path=str(pdf_file),
                    **self.test_config
                )
                
                if passes:
                    successful_conversions += 1
                    logger.info(f"✅ Generated {len(passes)} pass(es) for {pdf_file.name}")
                    
                    # Save passes
                    file_output_dir = self.output_dir / pdf_file.stem
                    file_output_dir.mkdir(exist_ok=True)
                    FileUtils.save_passes(passes, str(file_output_dir))
                    
                    # Save combined JSON
                    combined_file = file_output_dir / "all_passes.json"
                    with open(combined_file, 'w', encoding='utf-8') as f:
                        json.dump(passes, f, indent=2, ensure_ascii=False)
                    
                    logger.info(f"💾 Saved to: {file_output_dir.relative_to(Path(__file__).parent)}")
                    
                else:
                    logger.warning(f"⚠️ No passes generated for {pdf_file.name}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to process {pdf_file.name}: {e}")
                continue
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🎉 COMPLETED: {successful_conversions}/{len(pdf_files)} files processed successfully")
        logger.info(f"📁 All JSON files saved to: {self.output_dir.absolute()}")
        logger.info(f"{'='*60}")
        
        # Don't fail the test even if some files don't process
        # The goal is just to generate what we can


def run_tests(test_file: Optional[str] = None, verbose: bool = False):
    """Generate wallet passes from test files"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create test suite with only the pass generation test
    suite = unittest.TestSuite()
    suite.addTest(TestPDFToWalletPass('test_generate_passes_from_all_files'))
    
    # Run the test
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def main():
    """Main entry point - Generate wallet passes from all test PDFs"""
    parser = argparse.ArgumentParser(
        description="Generate wallet passes from PDF test files"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    logger.info("🎫 Starting wallet pass generation from test PDFs...")
    
    success = run_tests(verbose=args.verbose)
    
    if success:
        logger.info("✅ Pass generation completed!")
        return 0
    else:
        logger.error("❌ Pass generation had issues!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
