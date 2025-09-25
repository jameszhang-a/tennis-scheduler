import logging
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from cryptography.fernet import Fernet
from http_logger import logged_request
from models import Token
from sqlalchemy.orm import Session
from util import format_timestamp

logger = logging.getLogger(__name__)


def schedule_next_token_refresh(scheduler, db: Session, token_id: int, fernet: Fernet):
    """Schedule automatic token refresh using a hybrid approach"""
    token: Token = db.query(Token).get(token_id)
    if not token:
        logger.error("No token found - cannot schedule next refresh")
        return

    current_time = time.time()
    access_expiry = token.access_expiry
    refresh_expiry = token.refresh_expiry

    # Remove existing token refresh jobs if they exist
    try:
        scheduler.remove_job("token_refresh")
    except:
        pass  # Job might not exist

    try:
        scheduler.remove_job("token_refresh_interval")
    except:
        pass  # Job might not exist

    # Approach 1: Regular interval refresh every 20 minutes
    # This handles the 30-minute access token expiry cycle
    scheduler.add_job(
        auto_refresh_token,
        "interval",
        minutes=20,
        args=[scheduler, db, token_id, fernet],
        id="token_refresh_interval",
        replace_existing=True,
    )
    logger.info(
        "Scheduled regular token refresh every 20 minutes (for 30-min access token expiry)"
    )

    # Approach 2: Smart scheduling before refresh token expires
    # This ensures we refresh before the refresh token itself expires
    next_refresh_time = refresh_expiry - 30

    if next_refresh_time > current_time:
        # Convert to datetime for APScheduler
        next_refresh_datetime = datetime.fromtimestamp(
            next_refresh_time, tz=ZoneInfo("UTC")
        )
        next_refresh_eastern = next_refresh_datetime.astimezone(
            ZoneInfo("America/New_York")
        )

        # Schedule the refresh token expiry protection job
        scheduler.add_job(
            auto_refresh_token,
            "date",
            run_date=next_refresh_datetime,
            args=[scheduler, db, token_id, fernet],
            id="token_refresh_expiry_protection",
            replace_existing=True,
        )

        logger.info(
            f"Scheduled refresh token expiry protection for {next_refresh_eastern} Eastern"
        )
    else:
        logger.warning(
            f"Refresh token expires very soon ({format_timestamp(refresh_expiry)}), relying on interval refresh only"
        )


def auto_refresh_token(scheduler, db: Session, token_id: int, fernet: Fernet):
    """Automatically refresh token and manage scheduling"""
    try:
        logger.info("Performing automatic token refresh")
        get_fresh_access_token(
            db, token_id, fernet, scheduler=None
        )  # Don't auto-reschedule here

        # Only reschedule if this was called from the expiry protection job
        # The interval job will continue running automatically
        current_job = scheduler.get_job("token_refresh_expiry_protection")
        if current_job:
            logger.info(
                "Refresh token expiry protection job completed, rescheduling..."
            )
            schedule_next_token_refresh(scheduler, db, token_id, fernet)

    except Exception as e:
        logger.error(f"Automatic token refresh failed: {e}")
        # Try to schedule another attempt in 5 minutes as fallback
        next_attempt = datetime.now(ZoneInfo("UTC")) + timedelta(minutes=5)
        scheduler.add_job(
            auto_refresh_token,
            "date",
            run_date=next_attempt,
            args=[scheduler, db, token_id, fernet],
            id="token_refresh_retry",
            replace_existing=True,
        )
        logger.info("Scheduled retry token refresh in 5 minutes")


def get_fresh_access_token(
    db: Session, token_id: int, fernet: Fernet, scheduler=None
) -> str:

    token: Token = db.query(Token).get(token_id)
    current_time = time.time()

    logger.info(
        f"Getting fresh access token for token {token_id}. Token expire time: {format_timestamp(token.access_expiry)}. Refresh expire time: {format_timestamp(token.refresh_expiry)}"
    )

    if token.access_expiry > current_time + 2:  # Buffer
        logger.info(
            f"Access token is still valid.  Access expiry: {format_timestamp(token.access_expiry)}. Current time: {format_timestamp(current_time)}"
        )
        return fernet.decrypt(token.access_token).decode()

    if token.refresh_expiry < current_time:
        logger.error("Refresh token expired; update tokens.json")
        raise Exception("Refresh token expired")

    try:
        auth_url = os.getenv(
            "TENNIS_AUTH_URL",
            "https://auth.atriumapp.co/realms/my-tfc/protocol/openid-connect/token",
        )

        response = logged_request(
            method="POST",
            url=auth_url,
            operation_name="token_refresh",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": fernet.decrypt(token.refresh_token).decode(),
                "client_id": os.getenv("TENNIS_CLIENT_ID", "my-tfc"),
            },
        )
        data = response.json()

        # Update token
        token.access_token = fernet.encrypt(data["access_token"].encode())
        token.refresh_token = fernet.encrypt(data["refresh_token"].encode())
        token.access_expiry = current_time + data["expires_in"]
        token.refresh_expiry = current_time + data["refresh_expires_in"]
        token.session_state = data["session_state"]
        db.commit()

        logger.info(
            f"Token refreshed successfully. Token expire time: {format_timestamp(token.access_expiry)}. Refresh expire time: {format_timestamp(token.refresh_expiry)}"
        )

        # Schedule next automatic refresh if scheduler is provided
        if scheduler:
            schedule_next_token_refresh(scheduler, db, token_id, fernet)

        return data["access_token"]
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise


def prep_token_for_booking(
    db: Session, token_id: int, fernet: Fernet, schedule_id: int, scheduler=None
) -> str:
    """Refresh token specifically for an upcoming booking to ensure it's fresh"""
    logger.info(f"Preparing token for upcoming booking {schedule_id}")

    token: Token = db.query(Token).get(token_id)
    current_time = time.time()

    # Always refresh the token when preparing for booking to ensure maximum freshness
    if token.refresh_expiry < current_time:
        logger.error(
            f"Refresh token expired while preparing for booking {schedule_id}; update tokens.json"
        )
        raise Exception("Refresh token expired")

    try:
        auth_url = os.getenv(
            "TENNIS_AUTH_URL",
            "https://auth.atriumapp.co/realms/my-tfc/protocol/openid-connect/token",
        )

        response = logged_request(
            method="POST",
            url=auth_url,
            operation_name="booking_token_prep",
            correlation_id=f"prep_booking_{schedule_id}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": fernet.decrypt(token.refresh_token).decode(),
                "client_id": os.getenv("TENNIS_CLIENT_ID", "my-tfc"),
            },
        )
        data = response.json()

        # Update token
        token.access_token = fernet.encrypt(data["access_token"].encode())
        token.refresh_token = fernet.encrypt(data["refresh_token"].encode())
        token.access_expiry = current_time + data["expires_in"]
        token.refresh_expiry = current_time + data["refresh_expires_in"]
        token.session_state = data["session_state"]
        db.commit()

        logger.info(
            f"Token prepared for booking {schedule_id}. Token expire time: {format_timestamp(token.access_expiry)}. Refresh expire time: {format_timestamp(token.refresh_expiry)}"
        )

        # Schedule next automatic refresh if scheduler is provided
        if scheduler:
            schedule_next_token_refresh(scheduler, db, token_id, fernet)

        return data["access_token"]
    except Exception as e:
        logger.error(f"Token preparation for booking {schedule_id} failed: {e}")
        raise


def refresh_with_new_token(
    db: Session, fernet: Fernet, new_refresh_token: str, scheduler=None
) -> str:
    """Refresh tokens using a new refresh token provided by the user"""
    current_time = time.time()

    try:
        auth_url = os.getenv(
            "TENNIS_AUTH_URL",
            "https://auth.atriumapp.co/realms/my-tfc/protocol/openid-connect/token",
        )

        response = logged_request(
            method="POST",
            url=auth_url,
            operation_name="manual_token_refresh",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": new_refresh_token.strip(),  # Strip any whitespace
                "client_id": os.getenv("TENNIS_CLIENT_ID", "my-tfc"),
            },
        )
        data = response.json()

        # Get existing token or create new one
        token = db.query(Token).first()
        if not token:
            token = Token()
            db.add(token)
            logger.info("Creating new token record")
        else:
            logger.info("Updating existing token record")

        # Update token with new values
        token.access_token = fernet.encrypt(data["access_token"].encode())
        token.refresh_token = fernet.encrypt(data["refresh_token"].encode())
        token.access_expiry = current_time + data["expires_in"]
        token.refresh_expiry = current_time + data["refresh_expires_in"]
        token.session_state = data["session_state"]
        db.commit()

        logger.info("Token refreshed successfully with new refresh token")

        # Schedule next automatic refresh if scheduler is provided
        if scheduler:
            # Get the token ID for scheduling
            token_id = token.id
            schedule_next_token_refresh(scheduler, db, token_id, fernet)

        return data["access_token"]
    except Exception as e:
        logger.error(f"Token refresh with new token failed: {e}")
        raise
