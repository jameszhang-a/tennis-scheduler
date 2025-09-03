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
        now = eastern_now()
        
        # Handle past-due schedules differently based on type
        if trigger_time <= now:
            # For one-off schedules, check if desired time is still in future
            if schedule.type.value == "one-off":
                desired_time = to_eastern(schedule.desired_time)
                # If desired time is still in the future, schedule immediately
                if desired_time > now:
                    immediate_trigger = now + timedelta(seconds=30)
                    scheduler.add_job(
                        book_slot,
                        "date",
                        run_date=immediate_trigger,
                        args=[db, schedule.id, fernet],
                        id=f"booking_{schedule.id}"
                    )
                    logger.info(f"Past-due one-off schedule {schedule.id} rescheduled to run immediately at {immediate_trigger} for desired time {desired_time}")
                    continue
                else:
                    logger.warning(f"Skipping past-due one-off schedule {schedule.id} - desired time {desired_time} has already passed")
                    continue
            else:
                # For recurring schedules, skip if past due
                logger.warning(f"Skipping past-due recurring schedule {schedule.id}")
                continue
        
        # Normal scheduling for future trigger times
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