# Playwright Setup for Tennis Scheduler

This document explains how Playwright is integrated into the tennis scheduler for automated authentication.

## Overview

Instead of managing refresh tokens manually, the system uses Playwright to:

1. Automate browser login ~4 minutes before each booking
2. Capture OAuth access tokens from the network
3. Use fresh tokens for booking requests
4. Eliminate refresh token complexity

## Local Development Setup

### 1. Install Dependencies

```bash
# From tennis-scheduler directory
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Install Browser

```bash
playwright install chromium
```

### 3. Configure Environment Variables

Add to your `.env` file:

```bash
# TFC Login Credentials for Playwright
TFC_USERNAME=your_username_here
TFC_PASSWORD=your_password_here
```

### 4. Test Headless Browser Compatibility

Run the test script to verify headless browsers work with TFC:

```bash
python test_headless_login.py
```

This will:

- Test both headful (visible) and headless (invisible) browser modes
- Capture screenshots at each step
- Verify login form elements are detectable
- Attempt login with your credentials
- Report if headless mode is blocked

**Expected Output:**

- ✅ PASSED: Both modes work → Use `headless=True` in production
- ⚠️ PARTIAL: Only headful works → Use `headless=False` or implement stealth mode
- ❌ FAILED: Neither works → Check credentials, captcha, or 2FA issues

## Docker Deployment

The Dockerfile is already configured with:

1. **System Dependencies**: All required libraries for Chromium
2. **Playwright Installation**: Automatically installed via `requirements.txt`
3. **Browser Installation**: Chromium installed during image build

### Build Image

```bash
docker build -t tennis-scheduler .
```

### Run Container

```bash
docker run -d \
  -e TFC_USERNAME=your_username \
  -e TFC_PASSWORD=your_password \
  -e FERNET_KEY=your_key \
  -v $(pwd)/data:/app/data \
  -p 8000:8000 \
  tennis-scheduler
```

### Environment Variables Required

| Variable           | Description               | Required                  |
| ------------------ | ------------------------- | ------------------------- |
| `TFC_USERNAME`     | TFC account username      | Yes                       |
| `TFC_PASSWORD`     | TFC account password      | Yes                       |
| `FERNET_KEY`       | Encryption key for tokens | Yes                       |
| `TENNIS_CLIENT_ID` | OAuth client ID           | No (defaults to "my-tfc") |
| `TENNIS_AUTH_URL`  | OAuth token endpoint      | No (has default)          |

## Architecture Changes

### Before (Refresh Token Flow)

```
Startup → Load refresh token → Periodic token refresh → Booking (use access token)
Problem: Refresh tokens expire, require manual updates
```

### After (Playwright Flow)

```
Startup → No tokens needed → Pre-booking (4 min before) → Playwright Login → Extract Token → Booking
Benefit: No manual token management, always fresh tokens
```

### Key Files

- `playwright_auth.py` - Browser automation for login (to be created)
- `test_headless_login.py` - Test script for headless detection
- `test_headless_setup.sh` - Setup script for local testing
- `Dockerfile` - Configured with Playwright dependencies

## Troubleshooting

### Headless Mode Blocked

If the site blocks headless browsers:

**Option 1: Use Headful Mode (Recommended)**

```python
browser = p.chromium.launch(headless=False)
```

Browser runs in background but is technically "visible"

**Option 2: Stealth Mode**

```bash
pip install playwright-stealth
```

**Option 3: Try Firefox**

```python
browser = p.firefox.launch(headless=True)
```

### Login Fails in Docker

1. **Check logs**: Look for Playwright errors
2. **Verify credentials**: Ensure env vars are set correctly
3. **Network issues**: Ensure container can reach `https://my.tfc.com`
4. **Captcha**: If captcha appears, you may need to solve it manually or use captcha-solving service

### Browser Not Found

```bash
# Local
playwright install chromium

# Docker - rebuild image
docker build --no-cache -t tennis-scheduler .
```

### Screenshots for Debugging

The test script creates screenshots:

- `login_page_headless_true.png` - What headless browser sees
- `login_page_headless_false.png` - What headful browser sees
- `before_submit_headless_*.png` - Before clicking login
- `after_submit_headless_*.png` - After login attempt

## Security Considerations

1. **Credentials Storage**: Store in secure secrets management (Kubernetes secrets, AWS Secrets Manager, etc.)
2. **Token Encryption**: Access tokens are still encrypted with Fernet
3. **Network Security**: Browser traffic should go through secure network
4. **2FA**: Not compatible with 2FA - disable or use app-specific passwords

## Performance

- **Browser Launch**: ~2-5 seconds
- **Login Flow**: ~3-8 seconds total
- **Buffer Time**: 4 minutes before booking (plenty of margin)
- **Container Size**: +200MB (Chromium)
- **Memory**: +100-150MB when browser running

## Testing Checklist

- [ ] Local test passes with headless=True
- [ ] Docker image builds successfully
- [ ] Container can login and capture tokens
- [ ] Booking works with Playwright-obtained tokens
- [ ] Monitor logs for any browser crashes
- [ ] Verify memory usage is acceptable

## Future Improvements

1. Retry logic for failed logins
2. Token caching between bookings
3. Support for alternative auth methods
4. Automated captcha solving
5. Multi-user support
