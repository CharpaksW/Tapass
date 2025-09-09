#!/usr/bin/env python3
"""
Simple OpenAI API diagnostic test to identify 429 error causes.
Run this to diagnose your OpenAI API connection issues.
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file (same as run_tests.py)
try:
    from dotenv import load_dotenv
    # Look for .env file in the project root (5 levels up from test_openai_connection.py)
    env_path = Path(__file__).parent.parent.parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded environment variables from: {env_path}")
    else:
        print("⚠️  .env file not found, using system environment variables")
except ImportError:
    print("⚠️  python-dotenv not available, using system environment variables")

# Add the parent directory to sys.path so we can import openai
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    import openai
    print("✅ OpenAI library imported successfully")
except ImportError as e:
    print(f"❌ Failed to import OpenAI library: {e}")
    print("Install with: pip install openai")
    sys.exit(1)

def test_api_connection():
    """Test basic OpenAI API connection and diagnose issues"""
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not found")
        print("Set it with: export OPENAI_API_KEY=sk-your-key-here")
        return False
    
    # Validate API key format
    if not api_key.startswith('sk-'):
        print(f"❌ Invalid API key format. Should start with 'sk-', got: {api_key[:10]}...")
        return False
    
    # Safe preview of API key
    key_preview = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 11 else "***"
    print(f"✅ API key found: {key_preview} (length: {len(api_key)})")
    
    # Test the connection
    print("\n🔍 Testing OpenAI API connection...")
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # Try a minimal request with the most basic model first
        models_to_try = ["gpt-3.5-turbo", "gpt-4o-mini"]
        
        for model in models_to_try:
            print(f"🔍 Trying model: {model}")
            try:
                response = client.chat.completions.create(
                    model=model,
                    max_tokens=5,
                    messages=[
                        {"role": "user", "content": "Say 'test'"}
                    ]
                )
                print(f"✅ {model} works!")
                print(f"Response: {response.choices[0].message.content}")
                return True
            except Exception as model_error:
                print(f"❌ {model} failed: {model_error}")
                continue
        
        print("❌ All models failed")
        return False
        
    except Exception as e:
        error_str = str(e)
        print(f"❌ API Error: {error_str}")
        
        # Detailed diagnosis
        if "429" in error_str:
            print("\n🚨 DIAGNOSIS: 429 Too Many Requests Error")
            if "quota" in error_str.lower() or "billing" in error_str.lower():
                print("💳 CAUSE: Account quota/billing issue")
                print("👉 SOLUTION: Check https://platform.openai.com/account/billing")
                print("   - Verify your account has credits")
                print("   - Check if payment method is valid")
                print("   - Look for negative balance")
            elif "rate" in error_str.lower():
                print("⏱️  CAUSE: Rate limit exceeded")
                print("👉 SOLUTION: You may be on free tier with very low limits")
                print("   - Free tier: 3 requests/minute")
                print("   - Consider upgrading to paid tier")
            else:
                print("❓ CAUSE: Unknown 429 error")
                print("👉 SOLUTION: May be IP-related or account issue")
                
        elif "401" in error_str:
            print("\n🚨 DIAGNOSIS: 401 Unauthorized")
            print("🔑 CAUSE: Invalid API key")
            print("👉 SOLUTION: Check https://platform.openai.com/api-keys")
            
        elif "403" in error_str:
            print("\n🚨 DIAGNOSIS: 403 Forbidden")
            print("🚫 CAUSE: API key lacks access to GPT-4o-mini")
            print("👉 SOLUTION: Check your OpenAI plan and model access")
            
        else:
            print(f"\n🚨 DIAGNOSIS: Unexpected error")
            print("❓ CAUSE: Unknown issue")
            
        return False

def main():
    """Main diagnostic function"""
    print("🔧 OpenAI API Diagnostic Tool")
    print("=" * 40)
    
    success = test_api_connection()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 Your OpenAI API is working correctly!")
        print("The 429 error in your main app may be due to:")
        print("- Multiple concurrent requests")
        print("- Larger payloads using more tokens")
        print("- Different request patterns")
    else:
        print("❌ OpenAI API connection failed")
        print("Fix the issues above and try again")

if __name__ == "__main__":
    main()
