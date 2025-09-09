import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from auth import (
    get_fresh_access_token,
    prep_token_for_booking,
    schedule_next_token_refresh,
)
from bot import book_slot
from cryptography.fernet import Fernet
from util import to_eastern

logger = logging.getLogger(__name__)


def init_scheduler(scheduler: BackgroundScheduler, db):
    from models import Schedule, Token

    scheduler.remove_all_jobs()

    fernet = Fernet(os.getenv("FERNET_KEY").encode())

    # Get token early since we need it for token prep jobs
    token = db.query(Token).first()
    if not token:
        logger.error("No token found in database - cannot schedule token prep jobs")
        return

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
                    # For immediate bookings, also refresh token immediately
                    scheduler.add_job(
                        prep_token_for_booking,
                        "date",
                        run_date=utc_now,
                        args=[db, token.id, fernet, schedule.id, scheduler],
                        id=f"token_prep_{schedule.id}",
                    )

                    # Schedule the booking 30 seconds after token prep to ensure token is ready
                    booking_time = utc_now + timedelta(seconds=30)
                    scheduler.add_job(
                        book_slot,
                        "date",
                        run_date=booking_time,
                        args=[db, schedule.id, fernet],
                        id=f"booking_{schedule.id}",
                    )
                    # Convert back to Eastern for logging
                    immediate_trigger_eastern = utc_now.astimezone(
                        ZoneInfo("America/New_York")
                    )
                    booking_trigger_eastern = booking_time.astimezone(
                        ZoneInfo("America/New_York")
                    )
                    logger.info(
                        f"Past-due one-off schedule {schedule.id}: token prep at {immediate_trigger_eastern} Eastern, booking at {booking_trigger_eastern} Eastern for desired time {desired_time_eastern} Eastern"
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
        # Schedule token refresh 2 minutes before booking
        token_prep_time_utc = trigger_time_utc - timedelta(minutes=2)
        token_prep_time_eastern = token_prep_time_utc.astimezone(
            ZoneInfo("America/New_York")
        )

        # Only schedule token prep if it's still in the future
        if token_prep_time_utc > utc_now:
            scheduler.add_job(
                prep_token_for_booking,
                "date",
                run_date=token_prep_time_utc,
                args=[db, token.id, fernet, schedule.id, scheduler],
                id=f"token_prep_{schedule.id}",
            )
            logger.info(
                f"Scheduled token prep for booking {schedule.id} at {token_prep_time_eastern} Eastern ({token_prep_time_utc} UTC)"
            )

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

    # Schedule dynamic token refresh based on refresh token expiry
    schedule_next_token_refresh(scheduler, db, token.id, fernet)
    logger.info("Scheduled dynamic token refresh")
