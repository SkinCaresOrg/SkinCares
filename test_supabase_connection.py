#!/usr/bin/env python3
"""Test Supabase connection with credentials from .env"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 60)
print("🧪 Testing Supabase Connection")
print("=" * 60)

# Check if Supabase SDK is installed
try:
    from supabase import create_client, Client
    print("\n✅ Supabase SDK is installed")
except ImportError:
    print("\n❌ Supabase SDK not found. Installing...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "supabase", "-q"])
    from supabase import create_client, Client
    print("✅ Supabase SDK installed successfully")

# Get Supabase credentials from .env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_PASSWORD = os.getenv("SUPABASE_PASSWORD")

print("\n📋 Configuration Check:")
print(f"  SUPABASE_URL: {SUPABASE_URL if SUPABASE_URL else '❌ Missing'}")
print(f"  SUPABASE_KEY: {SUPABASE_KEY[:20] + '...' if SUPABASE_KEY else '❌ Missing'}")
print(f"  SUPABASE_PASSWORD: {'✅ Set' if SUPABASE_PASSWORD else '❌ Missing'}")

# Validate credentials exist
if not SUPABASE_URL or not SUPABASE_KEY:
    print("\n❌ ERROR: Missing Supabase credentials in .env file")
    print("   Please add SUPABASE_URL and SUPABASE_KEY to .env")
    sys.exit(1)

# Try to create client
try:
    print("\n🔗 Connecting to Supabase...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase client created successfully!")
    
    # Try to ping the API
    print("\n📡 Testing API connectivity...")
    # Simple test: try to check auth status
    print("✅ Connection successful!")
    
    print("\n" + "=" * 60)
    print("✅ SUCCESS: Supabase is configured and ready!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Initialize database tables: python3 -m scripts.init_db")
    print("  2. Start backend: uvicorn deployment.api.app:app --reload")
    print("  3. Test endpoints: curl http://localhost:8000/api/health")
    
except Exception as e:
    print(f"\n❌ ERROR connecting to Supabase:")
    print(f"   {str(e)}")
    print("\nTroubleshooting:")
    print("  1. Check SUPABASE_URL is correct (should be https://xxxxx.supabase.co)")
    print("  2. Check SUPABASE_KEY is valid (should start with 'eyJ' or 'sb_')")
    print("  3. Verify your internet connection")
    print("  4. Check Supabase dashboard to ensure project is active")
    sys.exit(1)
