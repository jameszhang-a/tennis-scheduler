import logging
from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo

from models import Schedule, ScheduleType
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_schedules_from_request(
    db: Session, request, scheduler  # CreateScheduleRequest type from api.py
) -> List[Schedule]:
    """
    Creates schedule entries based on user request.
    Special logic: Even for single occurrences, create 2 booking attempts.
    """
    created_schedules = []
    eastern = ZoneInfo("America/New_York")

    if request.schedule_type == "one-off":
        # Parse the date and time
        date_str = request.date
        time_str = request.time
        desired_datetime = datetime.strptime(
            f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=eastern)

        # Create 2 booking attempts as requested
        for week_offset in [0, 1]:  # Current date and 1 week later
            target_time = desired_datetime + timedelta(weeks=week_offset)
            schedule = create_single_schedule(
                db,
                target_time,
                request.court_id,
                request.duration,
                ScheduleType.ONE_OFF,
            )
            created_schedules.append(schedule)

    else:  # recurring
        # Generate RRULE
        day_map = {
            "MON": "MO",
            "TUE": "TU",
            "WED": "WE",
            "THU": "TH",
            "FRI": "FR",
            "SAT": "SA",
            "SUN": "SU",
        }
        hour, minute = request.time.split(":")
        rrule = f"FREQ=WEEKLY;BYDAY={day_map[request.day_of_week]};BYHOUR={hour};BYMINUTE={minute};COUNT={request.occurrences}"

        # Calculate next occurrence of the selected day
        next_occurrence = get_next_day_occurrence(
            request.day_of_week, request.time, eastern
        )

        # For recurring, we still create individual schedule entries
        # But special case: if occurrences = 1, create 2 attempts
        if request.occurrences == 1:
            for week_offset in [0, 1]:
                target_time = next_occurrence + timedelta(weeks=week_offset)
                schedule = create_single_schedule(
                    db,
                    target_time,
                    request.court_id,
                    request.duration,
                    ScheduleType.RECURRING,
                    rrule,
                )
                created_schedules.append(schedule)
        else:
            # Normal recurring schedule expansion
            for i in range(request.occurrences):
                target_time = next_occurrence + timedelta(weeks=i)
                schedule = create_single_schedule(
                    db,
                    target_time,
                    request.court_id,
                    request.duration,
                    ScheduleType.RECURRING,
                    rrule,
                )
                created_schedules.append(schedule)

    db.commit()

    # Now add all schedules to scheduler after commit (so they have IDs)
    for schedule in created_schedules:
        add_schedule_to_scheduler(scheduler, schedule)

    return created_schedules


def get_next_day_occurrence(day_of_week: str, time_str: str, timezone) -> datetime:
    """
    Find the next occurrence of a specific day of week.
    If today is that day but the time has passed, get next week's occurrence.
    """
    day_map = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}

    now = datetime.now(timezone)
    target_day = day_map[day_of_week]
    days_ahead = target_day - now.weekday()

    if days_ahead < 0:  # Target day already happened this week
        days_ahead += 7
    elif days_ahead == 0:  # Today is the target day
        # Check if the time has passed
        hour, minute = map(int, time_str.split(":"))
        target_time_today = now.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if now >= target_time_today:
            days_ahead = 7  # Schedule for next week

    hour, minute = map(int, time_str.split(":"))
    target_date = now + timedelta(days=days_ahead)
    return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)


def create_single_schedule(
    db: Session,
    desired_time: datetime,
    court_id: str,
    duration: int,
    schedule_type: ScheduleType,
    rrule: str = None,
) -> Schedule:
    """Create a single schedule entry with proper trigger time calculation."""
    # Calculate trigger time (7 days before or immediate if within 7 days)
    utc_now = datetime.now(ZoneInfo("UTC"))
    desired_time_utc = desired_time.astimezone(ZoneInfo("UTC"))
    time_until_desired = desired_time_utc - utc_now

    if time_until_desired <= timedelta(days=7):
        trigger_time = utc_now + timedelta(seconds=30)
    else:
        trigger_time = desired_time_utc - timedelta(days=7)

    trigger_time_eastern = trigger_time.astimezone(ZoneInfo("America/New_York"))

    schedule = Schedule(
        type=schedule_type,
        desired_time=desired_time,
        trigger_time=trigger_time_eastern,
        court_id=court_id,
        duration=duration,
        status="pending",
        rrule=rrule,
    )

    db.add(schedule)
    return schedule


def add_schedule_to_scheduler(scheduler, schedule: Schedule):
    """Dynamically add a single schedule to the running scheduler."""
    # Import from scheduler module to reuse the centralized logic
    from scheduler import add_schedule_to_scheduler as scheduler_add_schedule

    scheduler_add_schedule(scheduler, schedule)
