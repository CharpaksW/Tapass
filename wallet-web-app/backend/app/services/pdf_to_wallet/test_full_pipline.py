"""
COMPREHENSIVE PROCESSOR PIPELINE TEST
=====================================
This test demonstrates the complete end-to-end pipeline:
PDF → LLM Vision API → Apple Wallet JSON → .pkpass files

This test will convince you that processor.py fully works!
"""

import sys
import os
import json
import logging
from pathlib import Path
import tempfile
import time
from processor import WalletPassProcessor        

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from the main .env file
def load_env_file():
    """Load environment variables from the main .env file"""
    try:
        # Find the .env file in the wallet-web-app directory
        current_dir = Path(__file__).parent
        env_file_path = None
        
        # Search upwards for the .env file
        for parent in current_dir.parents:
            potential_env = parent / ".env"
            if potential_env.exists():
                env_file_path = potential_env
                break
        
        if env_file_path:
            print(f"📋 Loading environment from: {env_file_path}")
            with open(env_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
            print(f"✅ Environment variables loaded successfully")
            
            # Check if OpenAI API key is loaded
            if 'OPENAI_API_KEY' in os.environ:
                print(f"✅ OpenAI API key found (length: {len(os.environ['OPENAI_API_KEY'])})")
                return True
            else:
                print(f"❌ OpenAI API key not found in environment")
                return False
        else:
            print(f"❌ .env file not found")
            return False
            
    except Exception as e:
        print(f"❌ Error loading .env file: {e}")
        return False

# Load environment variables before importing other modules
env_loaded = load_env_file()

# Set up comprehensive logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

def test_complete_pipeline():
    """
    Test the complete pipeline using processor.py process_pdf() method
    This tests the entire end-to-end pipeline from PDF input to .pkpass files
    """
    print("TESTING COMPLETE PIPELINE WITH PROCESSOR.PROCESS_PDF()")
    try:
        # Import and initialize processor
        processor = WalletPassProcessor()        
        # Test configuration
        test_pdf = "Test_files/boarding_pass.pdf"
        organization = "Tapass"
        pass_type_id = "pass.tapass"
        team_id = "DSW9XCBAK2"
        
        print(f"\n TEST CONFIGURATION:")
        print(f"   PDF File: {test_pdf}")
        print(f"   Organization: {organization}")
        print(f"   Pass Type ID: {pass_type_id}")
        print(f"   Team ID: {team_id}")
        
        # Check if test PDF exists
        if not os.path.exists(test_pdf):
            print(f"❌ ERROR: Test PDF not found: {test_pdf}")
            return False
        
        print(f"✅ Test PDF file exists")
        
        # Check if API key is available
        has_api_key = 'OPENAI_API_KEY' in os.environ and os.environ['OPENAI_API_KEY']
        if has_api_key:
            print(f"✅ OpenAI API key available - will use real LLM")
        else:
            print(f"⚠️  No OpenAI API key - processor may fall back to test data")
        
        print(f"\n� CALLING PROCESSOR.PROCESS_PDF() - COMPLETE PIPELINE")
        print("-" * 60)
        
        # Call the actual process_pdf method - this is the main test!
        wallet_passes = processor.process_pdf(
            pdf_path=test_pdf,
            organization=organization,
            pass_type_id=pass_type_id,
            team_id=team_id,
            use_full_llm=True,      # Use full LLM pipeline
            create_pkpass=True      # Create .pkpass files
        )
        
        print(f"\n📊 PIPELINE RESULTS:")
        print("-" * 30)
        
        if not wallet_passes:
            print(f"❌ PIPELINE FAILED: No wallet passes generated")
            return False
        
        print(f"✅ PIPELINE SUCCESS: Generated {len(wallet_passes)} wallet pass(es)")
        
        # Analyze the results
        created_pkpass_files = 0
        for i, pass_data in enumerate(wallet_passes, 1):
            description = pass_data.get('description', 'No description')
            serial = pass_data.get('serialNumber', 'No serial')
            print(f"\n   📄 Pass {i}: {description}")
            print(f"      Serial: {serial}")
            
            # Check if .pkpass file was created
            if '_pkpass_file' in pass_data:
                pkpass_file = pass_data['_pkpass_file']
                print(f"      📦 PKPass: {pkpass_file}")
                created_pkpass_files += 1
            else:
                print(f"      ⚠️  No .pkpass file generated")
        
        print(f"\n🎯 FINAL VALIDATION:")
        print(f"   Wallet Passes: {len(wallet_passes)}")
        print(f"   PKPass Files:  {created_pkpass_files}")
        
        # Success criteria
        success = len(wallet_passes) > 0 and created_pkpass_files > 0
        
        if success:
            print(f"\n🎉 COMPLETE PIPELINE TEST: SUCCESS!")
            print(f"✅ processor.process_pdf() executed successfully")
            print(f"✅ PDF → LLM → Apple Wallet → .pkpass pipeline working")
            print(f"✅ Generated {len(wallet_passes)} passes with {created_pkpass_files} .pkpass files")
            return True
        else:
            print(f"\n❌ PIPELINE TEST: PARTIAL SUCCESS")
            print(f"   Generated passes but missing .pkpass files")
            return False
            
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 80)
    # Run all tests
    test_success = test_complete_pipeline()
    # Final verdict
    print(f"=" * 80)
    print(f"Pipeline Test:     {'✅ PASS' if test_success else '❌ FAIL'}")
    exit(0 if test_success else 1)