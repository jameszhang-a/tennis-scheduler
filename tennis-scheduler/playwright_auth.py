"""
Playwright-based authentication for TFC login.
Eliminates the need for manual refresh token management.
"""

import logging
import os
import time
from typing import Optional

from playwright.sync_api import Route, sync_playwright

logger = logging.getLogger(__name__)


def login_with_playwright(
    username: Optional[str] = None,
    password: Optional[str] = None,
    headless: bool = True,
) -> dict:
    """
    Uses Playwright to log in to TFC and capture OAuth tokens from the network.

    Args:
        username: TFC username (defaults to TFC_USERNAME env var)
        password: TFC password (defaults to TFC_PASSWORD env var)
        headless: Whether to run browser in headless mode

    Returns:
        dict with 'access_token', 'refresh_token', 'expires_in', 'refresh_expires_in', 'session_state'

    Raises:
        Exception: If login fails or tokens cannot be captured
    """
    # Get credentials from env if not provided
    username = username or os.getenv("TFC_USERNAME")
    password = password or os.getenv("TFC_PASSWORD")

    if not username or not password:
        raise ValueError(
            "TFC_USERNAME and TFC_PASSWORD must be provided or set in environment variables"
        )

    captured_token = {}

    def handle_route(route: Route):
        """Intercept token endpoint responses to capture OAuth tokens"""
        response = route.fetch()

        # Check if this is the token endpoint
        if "/protocol/openid-connect/token" in route.request.url:
            try:
                response_body = response.json()
                if "access_token" in response_body:
                    captured_token.update(response_body)
                    logger.info(
                        f"Successfully captured access token (expires in {response_body.get('expires_in')}s)"
                    )
            except Exception as e:
                logger.warning(f"Failed to parse token response: {e}")

        route.fulfill(response=response)

    try:
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = context.new_page()

            # Intercept all requests to token endpoint
            page.route("**/protocol/openid-connect/token**", handle_route)

            logger.info("Navigating to TFC login page...")
            page.goto("https://my.tfc.com/", wait_until="networkidle", timeout=30000)

            current_url = page.url
            logger.info(f"Loaded page: {current_url}")

            # Fill in credentials
            logger.info("Filling login form...")
            username_field = page.locator('input[name="username"]').first
            password_field = page.locator('input[type="password"]').first
            submit_button = page.locator('input[type="submit"]').first

            if username_field.count() == 0 or password_field.count() == 0:
                raise Exception(
                    "Login form not found - page structure may have changed"
                )

            username_field.fill(username)
            password_field.fill(password)

            logger.info("Submitting login form...")
            submit_button.click()

            # Wait for successful redirect
            try:
                page.wait_for_url(
                    "https://my.tfc.com/**", timeout=30000, wait_until="networkidle"
                )
                final_url = page.url
                logger.info(f"Login successful, redirected to: {final_url}")
            except Exception as e:
                # Check if we're still on auth page (login failed)
                if "auth.tfc.io" in page.url or "auth.atriumapp.co" in page.url:
                    # Try to find error message
                    error_elem = page.locator(".kc-feedback-text").first
                    if error_elem.count() > 0:
                        error_msg = error_elem.text_content()
                        raise Exception(f"Login failed: {error_msg}")
                    raise Exception(
                        "Login failed - still on auth page (check credentials)"
                    )
                raise Exception(f"Login navigation failed: {e}")

            # Give network time to complete token exchange
            time.sleep(2)

            browser.close()

    except Exception as e:
        logger.error(f"Playwright login failed: {e}")
        raise

    if not captured_token or "access_token" not in captured_token:
        raise Exception(
            "Failed to capture access token from login flow - token endpoint may not have been called"
        )

    logger.info(
        f"Successfully obtained tokens via Playwright (access expires in {captured_token.get('expires_in')}s)"
    )

    return captured_token


def test_login(headless: bool = True) -> bool:
    """
    Test function to verify Playwright login works.

    Args:
        headless: Whether to run in headless mode

    Returns:
        True if login succeeds, False otherwise
    """
    try:
        tokens = login_with_playwright(headless=headless)
        logger.info("✅ Playwright login test successful")
        logger.info(f"   Access token expires in: {tokens.get('expires_in')}s")
        logger.info(f"   Refresh token expires in: {tokens.get('refresh_expires_in')}s")
        return True
    except Exception as e:
        logger.error(f"❌ Playwright login test failed: {e}")
        return False
