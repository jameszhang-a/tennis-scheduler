from datetime import datetime
import pytz

def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=pytz.UTC)
    return dt.astimezone(pytz.UTC)

def format_api_datetime(dt: datetime) -> str:
    """Format datetime for Atrium API in Eastern timezone"""
    eastern = pytz.timezone('US/Eastern')
    if dt.tzinfo is None:
        # Assume input time is already in Eastern timezone
        eastern_dt = eastern.localize(dt)
    else:
        # Convert to Eastern time if timezone is specified
        eastern_dt = dt.astimezone(eastern)
    
    # Format as ISO string with timezone offset
    return eastern_dt.strftime("%Y-%m-%dT%H:%M:%S%z")

def add_timezone_colon(time_str: str) -> str:
    """Add colon to timezone offset if needed (e.g., -0400 -> -04:00)"""
    if len(time_str) >= 5 and time_str[-5] in ['+', '-']:
        return time_str[:-2] + ':' + time_str[-2:]
    return time_str