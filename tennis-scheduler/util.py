from datetime import datetime
from zoneinfo import ZoneInfo


def format_timestamp(timestamp: float) -> str:
    """Convert Unix timestamp to readable Eastern Time format"""
    et_timezone = ZoneInfo("America/New_York")
    dt = datetime.fromtimestamp(timestamp, tz=et_timezone)
    return dt.strftime("%Y-%m-%d %I:%M:%S %p %Z")


def to_eastern(dt: datetime) -> datetime:
    """Convert datetime to Eastern timezone"""
    eastern = ZoneInfo("America/New_York")
    if dt.tzinfo is None:
        # Assume naive datetime is already in Eastern timezone
        return dt.replace(tzinfo=eastern)
    else:
        # Convert from other timezone to Eastern
        return dt.astimezone(eastern)


def parse_eastern_time(time_str: str) -> datetime:
    """Parse time string as Eastern timezone"""
    eastern = ZoneInfo("America/New_York")
    # Remove 'Z' suffix if present and parse as naive datetime
    clean_time_str = time_str.replace("Z", "")
    dt = datetime.fromisoformat(clean_time_str)
    # Add Eastern timezone to naive datetime
    return dt.replace(tzinfo=eastern)


def format_api_datetime(dt: datetime) -> str:
    """Format datetime for Atrium API in Eastern timezone"""
    eastern = ZoneInfo("America/New_York")
    if dt.tzinfo is None:
        # Assume input time is already in Eastern timezone
        eastern_dt = dt.replace(tzinfo=eastern)
    else:
        # Convert to Eastern time if timezone is specified
        eastern_dt = dt.astimezone(eastern)

    # Format as ISO string with timezone offset
    return eastern_dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def add_timezone_colon(time_str: str) -> str:
    """Add colon to timezone offset if needed (e.g., -0400 -> -04:00)"""
    if len(time_str) >= 5 and time_str[-5] in ["+", "-"]:
        return time_str[:-2] + ":" + time_str[-2:]
    return time_str
