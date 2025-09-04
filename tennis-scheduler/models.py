import enum

from sqlalchemy import Column, DateTime, Enum, Float, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ScheduleType(enum.Enum):
    ONE_OFF = "one-off"
    RECURRING = "recurring"


class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True)
    type = Column(Enum(ScheduleType), nullable=False)
    desired_time = Column(DateTime, nullable=False)
    rrule = Column(String)  # For recurring schedules
    court_id = Column(String)  # Optional
    status = Column(String, default="pending")  # pending, success, failed
    trigger_time = Column(DateTime, nullable=False)
    duration = Column(Integer, default=60)  # Duration in minutes, defaults to 60


class Token(Base):
    __tablename__ = "tokens"
    id = Column(Integer, primary_key=True)
    access_token = Column(String)  # Encrypted
    refresh_token = Column(String)  # Encrypted
    access_expiry = Column(Float)  # Unix timestamp
    refresh_expiry = Column(Float)  # Unix timestamp
    session_state = Column(String)  # From OAuth response
