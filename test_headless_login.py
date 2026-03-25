#!/usr/bin/env python3
"""
Test script to verify if TFC login works with headless browsers.
Run this before implementing the full Playwright solution.

Usage:
    python test_headless_login.py
"""

import os
import sys
import time

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Load environment variables
load_dotenv()


def test_login(headless: bool, test_name: str):
    """Test login with specific headless setting"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

    captured_requests = []
    login_successful = False
    error_message = None

    def log_request(route):
        """Log and capture important requests"""
        url = route.request.url

        # Log token endpoint requests
        if "/protocol/openid-connect/token" in url or "/auth" in url:
            print(f"  → Network: {route.request.method} {url[:80]}...")
            captured_requests.append(url)

        route.continue_()

    try:
        with sync_playwright() as p:
            # Launch browser with headless setting
            browser = p.chromium.launch(headless=headless)

            # Use common browser context settings to avoid detection
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )

            page = context.new_page()

            # Route all requests to log them
            page.route("**/*", log_request)

            print(f"  ✓ Browser launched (headless={headless})")

            # Navigate to login page
            print(f"  → Navigating to https://my.tfc.com/...")
            page.goto("https://my.tfc.com/", wait_until="networkidle", timeout=30000)

            # Take screenshot of what we see
            screenshot_name = f"login_page_headless_{headless}.png"
            page.screenshot(path=screenshot_name)
            print(f"  ✓ Screenshot saved: {screenshot_name}")

            # Check current URL
            current_url = page.url
            print(f"  ✓ Current URL: {current_url}")

            # Check for common anti-bot detection indicators
            page_content = page.content()

            if "captcha" in page_content.lower():
                print(f"  ⚠️  CAPTCHA detected on page")

            # Check for bot-related keywords and show context
            bot_keywords = ["bot", "automated", "automation"]
            for keyword in bot_keywords:
                if keyword in page_content.lower():
                    # Find the context around the keyword
                    lower_content = page_content.lower()
                    index = lower_content.find(keyword)
                    start = max(0, index - 50)
                    end = min(len(page_content), index + 50)
                    context = page_content[start:end].replace("\n", " ").strip()
                    print(f"  ⚠️  Found '{keyword}' in page content:")
                    print(f"      Context: ...{context}...")
                    break  # Only show first match

            # Try to find login form elements
            print(f"\n  → Searching for login form elements...")

            # Check for username field
            username_selectors = [
                'input[name="username"]',
                'input[id="username"]',
                'input[type="text"]',
                'input[placeholder*="username" i]',
                'input[placeholder*="email" i]',
            ]

            username_field = None
            for selector in username_selectors:
                try:
                    username_field = page.locator(selector).first
                    if username_field.count() > 0:
                        print(f"  ✓ Username field found: {selector}")
                        break
                except:
                    continue

            # Check for password field
            password_field = None
            try:
                password_field = page.locator('input[type="password"]').first
                if password_field.count() > 0:
                    print(f"  ✓ Password field found")
            except:
                pass

            # Check for submit button
            submit_button = None
            button_selectors = [
                'button:has-text("Sign In")',
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Log in")',
                'button:has-text("Login")',
            ]

            for selector in button_selectors:
                try:
                    submit_button = page.locator(selector).first
                    if submit_button.count() > 0:
                        print(f"  ✓ Submit button found: {selector}")
                        break
                except:
                    continue

            # Try to login if we have credentials
            username = os.getenv("TFC_USERNAME")
            password = os.getenv("TFC_PASSWORD")

            if (
                username
                and password
                and username_field
                and password_field
                and submit_button
            ):
                print(f"\n  → Attempting login with credentials from .env...")

                username_field.fill(username)
                print(f"  ✓ Filled username")

                password_field.fill(password)
                print(f"  ✓ Filled password")

                # Take screenshot before clicking
                page.screenshot(path=f"before_submit_headless_{headless}.png")

                submit_button.click()
                print(f"  ✓ Clicked submit button")

                # Wait for navigation or error
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)

                    # Take screenshot after submit
                    page.screenshot(path=f"after_submit_headless_{headless}.png")

                    final_url = page.url
                    print(f"  → Final URL: {final_url}")

                    # Check if we're still on auth page (login failed)
                    if "auth.tfc.io" in final_url or "auth.atriumapp.co" in final_url:
                        print(f"  ❌ Still on auth page - login may have failed")

                        # Check for error messages
                        error_selectors = [
                            ".error",
                            ".alert",
                            '[role="alert"]',
                            ".kc-feedback-text",
                            "#input-error",
                        ]

                        for selector in error_selectors:
                            try:
                                error_elem = page.locator(selector).first
                                if error_elem.count() > 0:
                                    error_text = error_elem.text_content()
                                    print(f"  ❌ Error message: {error_text}")
                                    error_message = error_text
                            except:
                                continue
                    else:
                        print(
                            f"  ✅ Login appears successful - redirected away from auth page"
                        )
                        login_successful = True

                except Exception as e:
                    print(f"  ⚠️  Post-login wait failed: {e}")

            else:
                if not (username and password):
                    print(
                        f"  ⚠️  Missing TFC_USERNAME or TFC_PASSWORD in .env - skipping login attempt"
                    )
                if not username_field or not password_field or not submit_button:
                    print(f"  ❌ Login form incomplete - cannot attempt login")

            # Wait a bit to see final state
            time.sleep(2)

            browser.close()

    except Exception as e:
        error_message = str(e)
        print(f"  ❌ Error: {e}")

    # Summary
    print(f"\n  SUMMARY:")
    print(f"    Headless mode: {headless}")
    print(f"    Login successful: {login_successful}")
    print(f"    Requests captured: {len(captured_requests)}")
    print(f"    Error: {error_message if error_message else 'None'}")

    return login_successful, error_message


def main():
    print("TFC Headless Browser Detection Test")
    print("=" * 60)

    # Check for credentials
    if not os.getenv("TFC_USERNAME") or not os.getenv("TFC_PASSWORD"):
        print("\n⚠️  WARNING: TFC_USERNAME and TFC_PASSWORD not found in .env")
        print("The test will still check if the page loads, but won't attempt login.\n")

    # Test 1: Headful browser (visible)
    headful_success, headful_error = test_login(
        headless=False, test_name="Headful Browser (Visible)"
    )

    # Test 2: Headless browser
    headless_success, headless_error = test_login(
        headless=True, test_name="Headless Browser (Invisible)"
    )

    # Final comparison
    print(f"\n{'='*60}")
    print("FINAL VERDICT")
    print(f"{'='*60}")

    if headful_success and headless_success:
        print("✅ PASSED: Both headful and headless modes work!")
        print("   → Playwright automation with headless=True is viable")
        return 0

    elif headful_success and not headless_success:
        print("⚠️  PARTIAL: Headful works, but headless fails")
        print("   → Site may detect/block headless browsers")
        print("   → Solutions:")
        print("      1. Use headless=False (browser will be visible but hidden)")
        print("      2. Use stealth mode with playwright-stealth")
        print("      3. Try Firefox instead of Chromium")
        return 1

    elif not headful_success and not headless_success:
        print("❌ FAILED: Neither mode worked")
        print("   → Possible issues:")
        print(f"      - Wrong credentials: {headful_error}")
        print("      - Captcha or 2FA required")
        print("      - Site structure changed")
        print("      - Network/firewall issues")
        return 2

    else:
        print("🤔 UNEXPECTED: Headless works but headful doesn't")
        print("   → This is unusual - review screenshots")
        return 3


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
