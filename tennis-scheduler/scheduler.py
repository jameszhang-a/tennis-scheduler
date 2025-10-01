import logging
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from auth import (
    get_fresh_access_token,
    get_token_via_playwright,
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

    # Get token (optional when using Playwright - will be created on first auth)
    token = db.query(Token).first()
    if not token:
        logger.info(
            "No token found in database - Playwright will create one on first auth"
        )

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
                    # For immediate bookings, use Playwright to get fresh token now
                    playwright_time = utc_now
                    booking_time = utc_now + timedelta(minutes=1)
                    fernet_key = os.getenv("FERNET_KEY").encode()
                    
                    scheduler.add_job(
                        playwright_login_wrapper,
                        "date",
                        run_date=playwright_time,
                        args=[schedule.id, fernet_key],
                        id=f"playwright_auth_{schedule.id}",
                    )

                    scheduler.add_job(
                        book_slot_wrapper,
                        "date",
                        run_date=booking_time,
                        args=[schedule.id, fernet_key],
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
                        f"Past-due one-off schedule {schedule.id}: Playwright login at {immediate_trigger_eastern} Eastern, booking at {booking_trigger_eastern} Eastern for desired time {desired_time_eastern} Eastern"
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
        # Schedule Playwright login 4 minutes before booking
        playwright_time_utc = trigger_time_utc - timedelta(minutes=4)
        playwright_time_eastern = playwright_time_utc.astimezone(
            ZoneInfo("America/New_York")
        )

        # Only schedule Playwright login if it's still in the future
        if playwright_time_utc > utc_now:
            fernet_key = os.getenv("FERNET_KEY").encode()
            scheduler.add_job(
                playwright_login_wrapper,
                "date",
                run_date=playwright_time_utc,
                args=[schedule.id, fernet_key],
                id=f"playwright_auth_{schedule.id}",
            )
            logger.info(
                f"Scheduled Playwright login for booking {schedule.id} at {playwright_time_eastern} Eastern ({playwright_time_utc} UTC)"
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

    # Optional: Schedule dynamic token refresh if using refresh tokens (not needed with Playwright)
    # With Playwright, tokens are obtained fresh before each booking
    if token and token.refresh_expiry and token.refresh_expiry > time.time():
        schedule_next_token_refresh(scheduler, db, token.id, fernet)
        logger.info("Scheduled dynamic token refresh (refresh token available)")
    else:
        logger.info("Using Playwright-only authentication - no token refresh scheduled")


def prep_token_wrapper(token_id: int, fernet_key: bytes, schedule_id: int, scheduler):
    """Wrapper for prep_token_for_booking that creates its own DB session"""
    import os

    from models import Token
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Get database session
    def get_engine():
        db_path = os.getenv("DB_PATH", "/app/data/db.sqlite")
        return create_engine(f"sqlite:///{db_path}")

    SessionLocal = sessionmaker(bind=get_engine())
    db = SessionLocal()
    fernet = Fernet(fernet_key)

    try:
        prep_token_for_booking(db, token_id, fernet, schedule_id, scheduler)
    finally:
        db.close()


def book_slot_wrapper(schedule_id: int, fernet_key: bytes):
    """Wrapper for book_slot that creates its own DB session"""
    import os

    from models import Token
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Get database session
    def get_engine():
        db_path = os.getenv("DB_PATH", "/app/data/db.sqlite")
        return create_engine(f"sqlite:///{db_path}")

    SessionLocal = sessionmaker(bind=get_engine())
    db = SessionLocal()
    fernet = Fernet(fernet_key)

    try:
        book_slot(db, schedule_id, fernet)
    finally:
        db.close()


def playwright_login_wrapper(schedule_id: int, fernet_key: bytes):
    """Wrapper for Playwright login that creates its own DB session"""
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Get database session
    def get_engine():
        db_path = os.getenv("DB_PATH", "/app/data/db.sqlite")
        return create_engine(f"sqlite:///{db_path}")

    SessionLocal = sessionmaker(bind=get_engine())
    db = SessionLocal()
    fernet = Fernet(fernet_key)

    try:
        # Use headless mode by default (can be overridden via env var)
        headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
        get_token_via_playwright(db, fernet, schedule_id, headless=headless)
    finally:
        db.close()


def add_schedule_to_scheduler(scheduler: BackgroundScheduler, schedule):
    """Dynamically add a single schedule to the running scheduler using Playwright for auth."""
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    fernet_key = os.getenv("FERNET_KEY").encode()

    # Get database session
    def get_engine():
        db_path = os.getenv("DB_PATH", "/app/data/db.sqlite")
        return create_engine(f"sqlite:///{db_path}")

    SessionLocal = sessionmaker(bind=get_engine())
    db = SessionLocal()

    try:
        # Ensure trigger_time has timezone info (SQLite loses it)
        trigger_time_eastern = to_eastern(schedule.trigger_time)
        trigger_time_utc = trigger_time_eastern.astimezone(ZoneInfo("UTC"))
        utc_now = datetime.now(ZoneInfo("UTC"))

        # Add Playwright login job 4 minutes before booking
        if trigger_time_utc > utc_now:
            playwright_time = trigger_time_utc - timedelta(minutes=4)
            if playwright_time > utc_now:
                scheduler.add_job(
                    playwright_login_wrapper,
                    "date",
                    run_date=playwright_time,
                    args=[schedule.id, fernet_key],
                    id=f"playwright_auth_{schedule.id}",
                )
                logger.info(
                    f"Scheduled Playwright login for booking {schedule.id} at {playwright_time.astimezone(ZoneInfo('America/New_York'))} Eastern"
                )

        # Add booking job
        scheduler.add_job(
            book_slot_wrapper,
            "date",
            run_date=trigger_time_utc,
            args=[schedule.id, fernet_key],
            id=f"booking_{schedule.id}",
        )

        logger.info(f"Added schedule {schedule.id} to scheduler with Playwright auth")

    finally:
        db.close()
