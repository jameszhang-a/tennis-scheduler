import logging
import os
import time

import requests
from cryptography.fernet import Fernet
from http_logger import logged_request
from models import Token
from sqlalchemy.orm import Session
from util import format_timestamp

logger = logging.getLogger(__name__)


def get_fresh_access_token(db: Session, token_id: int, fernet: Fernet) -> str:

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
        return data["access_token"]
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise


def refresh_with_new_token(db: Session, fernet: Fernet, new_refresh_token: str) -> str:
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
        return data["access_token"]
    except Exception as e:
        logger.error(f"Token refresh with new token failed: {e}")
        raise
