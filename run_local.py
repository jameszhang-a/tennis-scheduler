#!/usr/bin/env python3
"""
Local development runner for the Tennis Scheduler API
Run this script to test the API locally without Docker
"""
import os
import sys

# Add the tennis-scheduler directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tennis-scheduler'))

# Set environment variables for local development
os.environ['DB_PATH'] = './data/db.sqlite'
os.environ['SCHEDULES_PATH'] = './data/schedules.json'
os.environ['TOKENS_PATH'] = './data/tokens.json'

# You'll need to set this to a valid Fernet key
# Generate one with: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())
if 'FERNET_KEY' not in os.environ:
    print("WARNING: FERNET_KEY not set. Generating a temporary one for testing.")
    from cryptography.fernet import Fernet
    os.environ['FERNET_KEY'] = Fernet.generate_key().decode()

# Optional: Set tennis API credentials if you have them
# os.environ['TENNIS_AUTH_URL'] = 'https://auth.atriumapp.co/realms/my-tfc/protocol/openid-connect/token'
# os.environ['TENNIS_CLIENT_ID'] = 'my-tfc'

from main import main

if __name__ == "__main__":
    print("Starting Tennis Scheduler with API...")
    print("API will be available at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("\nPress Ctrl+C to stop")
    main()
