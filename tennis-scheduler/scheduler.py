from apscheduler.schedulers.background import BackgroundScheduler
from bot import book_slot
from auth import get_fresh_access_token
from datetime import datetime, timedelta, timezone
from util import eastern_now, to_eastern
import logging
from cryptography.fernet import Fernet
import os

logger = logging.getLogger(__name__)

def init_scheduler(scheduler: BackgroundScheduler, db):
    from models import Schedule, Token
    scheduler.remove_all_jobs()
    
    fernet = Fernet(os.getenv("FERNET_KEY").encode())
    
    pending = db.query(Schedule).filter(Schedule.status == "pending").all()
    for schedule in pending:
        # Ensure trigger_time is timezone-aware in Eastern
        trigger_time = to_eastern(schedule.trigger_time)
        if trigger_time <= eastern_now():
            logger.warning(f"Skipping past-due schedule {schedule.id}")
            continue
        scheduler.add_job(
            book_slot,
            "date",
            run_date=trigger_time,  # Use the timezone-aware trigger_time
            args=[db, schedule.id, fernet],
            id=f"booking_{schedule.id}"
        )
        logger.info(f"Scheduled booking {schedule.id} for {trigger_time}")
    
    # Add token refresh job (every 20min)
    token = db.query(Token).first()
    if token:
        scheduler.add_job(
            get_fresh_access_token,
            "interval",
            minutes=20,
            args=[db, token.id, fernet],
            id="token_refresh",
            replace_existing=True
        )
        logger.info("Scheduled token refresh")