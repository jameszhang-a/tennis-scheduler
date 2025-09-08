import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from auth import get_fresh_access_token
from bot import book_slot
from cryptography.fernet import Fernet
from util import to_eastern

logger = logging.getLogger(__name__)


def init_scheduler(scheduler: BackgroundScheduler, db):
    from models import Schedule, Token

    scheduler.remove_all_jobs()

    fernet = Fernet(os.getenv("FERNET_KEY").encode())

    pending = db.query(Schedule).filter(Schedule.status == "pending").all()
    for schedule in pending:
        # Convert all times to UTC for consistent comparisons
        trigger_time_eastern = to_eastern(schedule.trigger_time)
        trigger_time_utc = trigger_time_eastern.astimezone(ZoneInfo("UTC"))

        desired_time_eastern = to_eastern(schedule.desired_time)
        desired_time_utc = desired_time_eastern.astimezone(ZoneInfo("UTC"))

        utc_now = datetime.now(ZoneInfo("UTC"))

        # Handle past-due schedules differently based on type
        if trigger_time_utc <= utc_now:
            # For one-off schedules, check if desired time is still in future
            if schedule.type.value == "one-off":
                # If desired time is still in the future (in UTC), schedule immediately
                if desired_time_utc > utc_now:
                    scheduler.add_job(
                        book_slot,
                        "date",
                        run_date=utc_now,
                        args=[db, schedule.id, fernet],
                        id=f"booking_{schedule.id}",
                    )
                    # Convert back to Eastern for logging
                    immediate_trigger_eastern = utc_now.astimezone(
                        ZoneInfo("America/New_York")
                    )
                    logger.info(
                        f"Past-due one-off schedule {schedule.id} rescheduled to run immediately at {immediate_trigger_eastern} Eastern ({utc_now} UTC) for desired time {desired_time_eastern} Eastern"
                    )
                    continue
                else:
                    logger.warning(
                        f"Skipping past-due one-off schedule {schedule.id} - desired time {desired_time_eastern} Eastern has already passed"
                    )
                    continue
            else:
                # For recurring schedules, skip if past due
                logger.warning(f"Skipping past-due recurring schedule {schedule.id}")
                continue

        # Normal scheduling for future trigger times
        # APScheduler expects UTC time
        scheduler.add_job(
            book_slot,
            "date",
            run_date=trigger_time_utc,  # Use UTC time for APScheduler
            args=[db, schedule.id, fernet],
            id=f"booking_{schedule.id}",
        )
        logger.info(
            f"Scheduled booking {schedule.id} for {trigger_time_eastern} Eastern ({trigger_time_utc} UTC)"
        )

    # Add token refresh job (every 20min)
    token = db.query(Token).first()
    if token:
        scheduler.add_job(
            get_fresh_access_token,
            "interval",
            minutes=20,
            args=[db, token.id, fernet],
            id="token_refresh",
            replace_existing=True,
        )
        logger.info("Scheduled token refresh")
