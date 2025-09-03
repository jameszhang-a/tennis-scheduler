import requests
import logging
from auth import get_fresh_access_token
from models import Schedule, Token
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from datetime import timedelta
from util import format_api_datetime, add_timezone_colon, to_eastern
import os

logger = logging.getLogger(__name__)

def get_amenity_id(court_id: str) -> int:
    """Map court_id to amenity_id for the Atrium API"""
    court_mapping = {
        "1": 8,   # Court 1 → amenity_id 8
        "2": 10   # Court 2 → amenity_id 10
    }
    return court_mapping.get(court_id, 8)  # Default to court 1

def book_slot(db: Session, schedule_id: int, fernet: Fernet):
    schedule = db.query(Schedule).get(schedule_id)
    if not schedule:
        logger.error(f"Schedule {schedule_id} not found")
        return
    
    try:
        # Get fresh token
        token = db.query(Token).first()
        access_token = get_fresh_access_token(db, token.id, fernet)
        
        # Ensure desired_time is timezone-aware in Eastern
        desired_time = to_eastern(schedule.desired_time)
        
        # Calculate end time (30 minutes after start, or use duration if available)
        duration = getattr(schedule, 'duration', 60)  # Default 60 minutes
        end_time = desired_time + timedelta(minutes=duration)
        
        # Format times for the API (ISO format with Eastern timezone)
        start_time_str = add_timezone_colon(format_api_datetime(desired_time))
        end_time_str = add_timezone_colon(format_api_datetime(end_time))
        
        # Prepare API payload
        amenity_id = get_amenity_id(schedule.court_id or "1")
        payload = {
            "amenity_type_id": "10",
            "start_time": start_time_str,
            "amenity_id": amenity_id,
            "guests": "1",
            "end_time": end_time_str,
            "amenity_reservation_type": "TR"
        }
        
        logger.info(f"Booking slot {schedule_id}: Court {schedule.court_id} at {start_time_str}")
        
        response = requests.post(
            "https://api.atriumapp.co/api/v1/my/occupants/133055/amenity-reservations/",
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload
        )
        response.raise_for_status()
        schedule.status = "success"
        logger.info(f"Booking {schedule_id} succeeded: {response.json()}")
    except Exception as e:
        schedule.status = "failed"
        logger.error(f"Booking {schedule_id} failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response body: {e.response.text}")
    finally:
        db.commit()