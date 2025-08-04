from apscheduler.schedulers.background import BackgroundScheduler
from bot import book_slot
from auth import get_fresh_access_token
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def init_scheduler(scheduler: BackgroundScheduler, db):
    from models import Schedule, Token
    # Clear existing jobs
    scheduler.remove_all_jobs()
    
    # Load pending schedules
    pending = db.query(Schedule).filter(Schedule.status == "pending").all()
    for schedule in pending:
        if schedule.trigger_time <= datetime.utcnow():
            logger.warning(f"Skipping past-due schedule {schedule.id}")
            continue
        scheduler.add_job(
            book_slot,
            "date",
            run_date=schedule.trigger_time,
            args=[db, schedule.id],
            id=f"booking_{schedule.id}"
        )
        logger.info(f"Scheduled booking {schedule.id} for {schedule.trigger_time}")
    
    # Add token refresh job (every 20min)
    token = db.query(Token).first()
    if token:
        scheduler.add_job(
            get_fresh_access_token,
            "interval",
            minutes=20,
            args=[db, token.id],
            id="token_refresh",
            replace_existing=True
        )
        logger.info("Scheduled token refresh")