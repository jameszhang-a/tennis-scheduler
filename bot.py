import requests
import logging
from auth import get_fresh_access_token
from models import Schedule
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
import os

logger = logging.getLogger(__name__)

def book_slot(db: Session, schedule_id: int):
    fernet = Fernet(os.getenv("FERNET_KEY").encode())
    schedule = db.query(Schedule).get(schedule_id)
    if not schedule:
        logger.error(f"Schedule {schedule_id} not found")
        return
    
    try:
        # Get fresh token
        token = db.query(Token).first()
        access_token = get_fresh_access_token(db, token.id, fernet)
        
        # Make booking API call (hypothetical endpoint; adjust per actual API)
        response = requests.post(
            f"{os.getenv('TENNIS_API_BASE_URL', 'https://api.atriumapp.co')}/book",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "date": schedule.desired_time.date().isoformat(),
                "time": schedule.desired_time.time().isoformat(),
                "court": schedule.court_id or "1"
            }
        )
        response.raise_for_status()
        schedule.status = "success"
        logger.info(f"Booking {schedule_id} succeeded")
    except Exception as e:
        schedule.status = "failed"
        logger.error(f"Booking {schedule_id} failed: {e}")
    finally:
        db.commit()