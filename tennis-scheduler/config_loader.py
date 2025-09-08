import json
import logging
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet
from dateutil.rrule import rrulestr
from models import Schedule, ScheduleType, Token
from sqlalchemy.orm import Session
from util import parse_eastern_time, to_eastern

logger = logging.getLogger(__name__)


def load_configs(db: Session, schedules_path: str, tokens_path: str):
    fernet = Fernet(os.getenv("FERNET_KEY").encode())

    # Load tokens
    with open(tokens_path, "r") as f:
        token_data = json.load(f)
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise ValueError("No refresh_token in tokens.json")

    token = db.query(Token).first()
    if not token:
        token = Token(
            refresh_token=fernet.encrypt(refresh_token.encode()),
            access_token=fernet.encrypt(b""),
            access_expiry=0,
            refresh_expiry=time.time() + 20 * 60,
            session_state="",
        )
        db.add(token)
    else:
        token.refresh_token = fernet.encrypt(refresh_token.encode())
    db.commit()

    # Load schedules
    with open(schedules_path, "r") as f:
        schedules = json.load(f)

    for s in schedules:
        if s["type"] == "one-off":
            # Parse desired time as Eastern, then convert to UTC for all calculations
            desired_time_eastern = parse_eastern_time(s["desired_time"])
            desired_time_utc = desired_time_eastern.astimezone(ZoneInfo("UTC"))

            # Work entirely in UTC
            utc_now = datetime.now(ZoneInfo("UTC"))
            time_until_desired = desired_time_utc - utc_now

            logger.info(
                f"Processing one-off schedule: desired_time={desired_time_eastern} Eastern ({desired_time_utc} UTC), utc_now={utc_now}, time_until_desired={time_until_desired}"
            )

            # If the desired time is within 7 days, schedule it to run immediately
            # Otherwise, schedule it 7 days (168 hours) in advance
            if time_until_desired <= timedelta(days=7):
                # Schedule to run in 30 seconds from actual UTC now
                trigger_time_utc = utc_now + timedelta(seconds=1)
                # Convert to Eastern for database storage
                trigger_time = trigger_time_utc.astimezone(ZoneInfo("America/New_York"))
                logger.info(
                    f"One-off schedule for {desired_time_eastern} is within 7 days, scheduling to run immediately at {trigger_time} Eastern ({trigger_time_utc} UTC)"
                )
            else:
                # Standard 7-day advance scheduling (168 hours before desired time in UTC)
                trigger_time_utc = desired_time_utc - timedelta(hours=168)
                trigger_time = trigger_time_utc.astimezone(ZoneInfo("America/New_York"))
                logger.info(
                    f"One-off schedule for {desired_time_eastern} is more than 7 days away, scheduling trigger for {trigger_time} Eastern ({trigger_time_utc} UTC)"
                )

            schedule = Schedule(
                type=ScheduleType.ONE_OFF,
                desired_time=desired_time_eastern,
                trigger_time=trigger_time,
                court_id=s.get("court_id"),
                duration=s.get("duration", 60),
                status="pending",
            )
            db.add(schedule)
        elif s["type"] == "recurring":
            # Parse RRULE with Eastern timezone context
            eastern = ZoneInfo("America/New_York")
            # Start from a baseline Eastern time (today at midnight)
            utc_now = datetime.now(ZoneInfo("UTC"))
            eastern_now = utc_now.astimezone(eastern)
            # Create a naive datetime for dtstart, then let rrulestr handle timezone
            dtstart_naive = eastern_now.replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=None
            )
            dtstart = dtstart_naive.replace(tzinfo=eastern)
            rrule = rrulestr(s["rrule"], dtstart=dtstart)
            # Generate up to 52 instances
            for dt in rrule[:52]:
                # dt from rrule should already be timezone-aware in Eastern
                # If it's not, convert it properly
                if dt.tzinfo is None:
                    eastern_dt = dt.replace(tzinfo=eastern)
                else:
                    eastern_dt = dt.astimezone(eastern)
                # Calculate trigger time in UTC, then convert to Eastern for storage
                eastern_dt_utc = eastern_dt.astimezone(ZoneInfo("UTC"))
                trigger_time_utc = eastern_dt_utc - timedelta(hours=168)
                trigger_time_eastern = trigger_time_utc.astimezone(eastern)

                schedule = Schedule(
                    type=ScheduleType.RECURRING,
                    desired_time=eastern_dt,
                    trigger_time=trigger_time_eastern,
                    rrule=s["rrule"],
                    court_id=s.get("court_id"),
                    duration=s.get("duration", 60),
                    status="pending",
                )
                db.add(schedule)
        db.commit()
