#!/bin/bash
# Convenience script to start the Tennis Scheduler API with virtual environment

# Change to the script's directory
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
    echo "Installing requirements..."
    source venv/bin/activate
    pip install -r requirements.txt
else
    # Activate virtual environment
    source venv/bin/activate
fi

# Run the API
echo "Starting Tennis Scheduler API..."
python run_local.py
