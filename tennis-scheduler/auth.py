import requests
import time
import logging
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from models import Token
import os

logger = logging.getLogger(__name__)

def get_fresh_access_token(db: Session, token_id: int, fernet: Fernet) -> str:
    token = db.query(Token).get(token_id)
    current_time = time.time()
    
    if token.access_expiry > current_time + 60:  # Buffer
        return fernet.decrypt(token.access_token).decode()
    
    if token.refresh_expiry < current_time:
        logger.error("Refresh token expired; update tokens.json")
        raise Exception("Refresh token expired")
    
    try:
        response = requests.post(
            os.getenv("TENNIS_AUTH_URL", "https://auth.atriumapp.co/realms/my-tfc/protocol/openid-connect/token"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": fernet.decrypt(token.refresh_token).decode(),
                "client_id": os.getenv("TENNIS_CLIENT_ID", "my-tfc")
            }
        )
        response.raise_for_status()
        data = response.json()
        
        # Update token
        token.access_token = fernet.encrypt(data["access_token"].encode())
        token.refresh_token = fernet.encrypt(data["refresh_token"].encode())
        token.access_expiry = current_time + data["expires_in"]
        token.refresh_expiry = current_time + data["refresh_expires_in"]
        token.session_state = data["session_state"]
        db.commit()
        
        logger.info("Token refreshed successfully")
        return data["access_token"]
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise