# Playwright Quick Start Guide

## 🚀 Verify Headless Browser Support (5 minutes)

### Step 1: Ensure you're in the right directory

```bash
cd /Users/james/code/project/tennis-scheduler
source venv/bin/activate
```

### Step 2: Add credentials to .env

```bash
# Edit .env and add:
TFC_USERNAME=your_username
TFC_PASSWORD=your_password
```

### Step 3: Run the test

```bash
python test_headless_login.py
```

### Step 4: Interpret results

**✅ BEST CASE - Both modes pass:**

```
✅ PASSED: Both headful and headless modes work!
   → Playwright automation with headless=True is viable
```

→ **Action**: Proceed with Playwright implementation using `headless=True`

**⚠️ PARTIAL - Only headful works:**

```
⚠️ PARTIAL: Headful works, but headless fails
   → Site may detect/block headless browsers
```

→ **Action**: Use `headless=False` in playwright_auth.py (browser runs hidden but visible)

**❌ WORST CASE - Both fail:**

```
❌ FAILED: Neither mode worked
   → Possible issues: Wrong credentials, Captcha, 2FA
```

→ **Action**: Check error messages, review screenshots, verify credentials

## 📸 Review Screenshots

After the test, check these files:

- `login_page_headless_true.png` - What headless sees
- `login_page_headless_false.png` - What headful sees
- `before_submit_headless_*.png` - Form filled state
- `after_submit_headless_*.png` - Post-login state

## 🐳 Docker Verification (Optional)

Test that Docker build works with Playwright:

```bash
# Build image (takes 5-10 minutes first time)
docker build -t tennis-scheduler-test .

# Verify Playwright is installed
docker run --rm tennis-scheduler-test playwright --version

# Test Chromium is available
docker run --rm tennis-scheduler-test playwright install chromium --dry-run
```

## 📊 Package Sizes

- **Local venv**: +140MB (Chromium browser)
- **Docker image**: +200MB (Chromium + dependencies)
- **Memory at runtime**: +100-150MB when browser active

## 🔍 Common Issues

### Issue: "TFC_USERNAME not found"

**Solution**: Make sure .env file exists and has credentials

### Issue: "Browser executable not found"

**Solution**: Run `playwright install chromium`

### Issue: "Login form elements not found"

**Solution**: Check screenshots - site structure may have changed

### Issue: "Captcha detected"

**Solution**: This is a blocker - Playwright can't solve captchas automatically

## ✅ Success Criteria

Your test is successful if:

1. ✅ Browser launches without errors
2. ✅ Login page loads and displays correctly
3. ✅ Form elements (username, password, submit) are found
4. ✅ Login completes and redirects away from auth page
5. ✅ No captcha or 2FA blocks the flow

## 🎯 Next Steps After Successful Test

1. **Document your results** in a comment or issue
2. **Proceed to implementation** - create `playwright_auth.py`
3. **Update scheduler** - replace token prep with Playwright login
4. **Test end-to-end** - verify booking works with Playwright tokens
5. **Deploy** - push to production with environment variables

## 📚 Full Documentation

See `PLAYWRIGHT_SETUP.md` for complete architecture and implementation details.
