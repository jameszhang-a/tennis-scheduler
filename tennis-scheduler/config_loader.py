import json
from datetime import datetime, timedelta
from dateutil.rrule import rrulestr
from sqlalchemy.orm import Session
from models import Schedule, ScheduleType, Token
from cryptography.fernet import Fernet
from util import parse_eastern_time, to_eastern
import os
import logging
import pytz

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
            refresh_expiry=0,
            session_state=""
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
            desired_time = parse_eastern_time(s["desired_time"])
            trigger_time = desired_time - timedelta(hours=168)
            schedule = Schedule(
                type=ScheduleType.ONE_OFF,
                desired_time=desired_time,
                trigger_time=trigger_time,
                court_id=s.get("court_id"),
                duration=s.get("duration", 60),  
                status="pending"
            )
            db.add(schedule)
        elif s["type"] == "recurring":
            # Parse RRULE with Eastern timezone context
            eastern = pytz.timezone('US/Eastern')
            # Start from a baseline Eastern time (today at midnight)
            dtstart = eastern.localize(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
            rrule = rrulestr(s["rrule"], dtstart=dtstart)
            # Generate up to 52 instances
            for dt in rrule[:52]:
                # Ensure the generated datetime is timezone-aware in Eastern
                eastern_dt = to_eastern(dt)
                schedule = Schedule(
                    type=ScheduleType.RECURRING,
                    desired_time=eastern_dt,
                    trigger_time=eastern_dt - timedelta(hours=168),
                    rrule=s["rrule"],
                    court_id=s.get("court_id"),
                    duration=s.get("duration", 60),  
                    status="pending"
                )
                db.add(schedule)
        db.commit()