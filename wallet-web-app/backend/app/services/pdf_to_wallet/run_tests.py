#!/usr/bin/env python3
"""
Simple test runner script for the PDF to Wallet Pass converter.

This script provides an easy way to run tests on the PDF conversion functionality
using the test files in the Test_files folder.
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Look for .env file in the project root (4 levels up from run_tests.py)
    env_path = Path(__file__).parent.parent.parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment variables from: {env_path}")
    else:
        print("⚠️  .env file not found, using system environment variables")
except ImportError:
    print("⚠️  python-dotenv not available, using system environment variables")

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def main():
    """Generate wallet passes from test PDFs"""
    print("🎫 Wallet Pass Generator")
    print("=" * 50)
    
    # Check if test files exist
    test_files_dir = current_dir / "Test_files"
    if not test_files_dir.exists():
        print("❌ Test_files directory not found!")
        return 1
    
    pdf_files = list(test_files_dir.glob("*.pdf"))
    print(f"📄 Found {len(pdf_files)} PDF test files:")
    for pdf_file in pdf_files:
        print(f"  - {pdf_file.name}")
    
    print("\nChoose an option:")
    print("1. Generate passes from all PDFs")
    print("2. Generate with verbose output")
    print("0. Exit")
    
    try:
        choice = input("\nEnter choice (0-2): ").strip()
        
        if choice == "0":
            print("Goodbye!")
            return 0
        
        elif choice == "1":
            print("\n🚀 Generating wallet passes...")
            from test_pdf_to_wallet_pass import run_tests
            success = run_tests()
            
            # Show where files were saved
            output_dir = current_dir / "generated_passes"
            if output_dir.exists():
                print(f"\n📁 Generated JSON files saved to:")
                print(f"   {output_dir.absolute()}")
            
            return 0 if success else 1
        
        elif choice == "2":
            print("\n🔍 Generating wallet passes with verbose output...")
            from test_pdf_to_wallet_pass import run_tests
            success = run_tests(verbose=True)
            
            # Show where files were saved
            output_dir = current_dir / "generated_passes"
            if output_dir.exists():
                print(f"\n📁 Generated JSON files saved to:")
                print(f"   {output_dir.absolute()}")
            
            return 0 if success else 1
        
        else:
            print("❌ Invalid choice!")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
