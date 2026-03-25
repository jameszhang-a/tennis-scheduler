#!/bin/bash
# Setup script for headless browser test

echo "🎭 Playwright Headless Browser Test Setup"
echo "=========================================="
echo ""

# Check if we're in the tennis-scheduler directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: Must be run from tennis-scheduler directory"
    exit 1
fi

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Not in a virtual environment"
    if [ -d "venv" ]; then
        echo "Activating venv..."
        source venv/bin/activate
    else
        echo "❌ venv directory not found. Please create it first:"
        echo "   python3 -m venv venv"
        echo "   source venv/bin/activate"
        exit 1
    fi
fi

# Install from requirements.txt (includes playwright)
echo "📦 Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Install browser binaries
echo "🌐 Installing Chromium browser..."
playwright install chromium

# Check for .env file
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  No .env file found. Creating template..."
    cat > .env << EOF
# TFC Login Credentials for Playwright
TFC_USERNAME=your_username_here
TFC_PASSWORD=your_password_here

# Existing config
FERNET_KEY=your_fernet_key_here
TENNIS_CLIENT_ID=my-tfc
TENNIS_AUTH_URL=https://auth.atriumapp.co/realms/my-tfc/protocol/openid-connect/token
DB_PATH=/app/data/db.sqlite
SCHEDULES_PATH=/app/data/schedules.json
TOKENS_PATH=/app/data/tokens.json
EOF
    echo "✅ Created .env template - PLEASE EDIT IT with your credentials"
else
    echo "✅ .env file exists"
    
    # Check if TFC credentials are in .env
    if ! grep -q "TFC_USERNAME" .env; then
        echo "⚠️  Adding TFC_USERNAME and TFC_PASSWORD to .env..."
        echo "" >> .env
        echo "# TFC Login Credentials for Playwright" >> .env
        echo "TFC_USERNAME=your_username_here" >> .env
        echo "TFC_PASSWORD=your_password_here" >> .env
        echo "✅ Added TFC credentials to .env - PLEASE EDIT THEM"
    fi
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your TFC_USERNAME and TFC_PASSWORD"
echo "  2. Run the headless test: python test_headless_login.py"
echo ""
echo "For Docker deployment:"
echo "  - Ensure TFC_USERNAME and TFC_PASSWORD are in your environment/secrets"
echo "  - The Dockerfile will automatically install Playwright and Chromium"
echo ""

