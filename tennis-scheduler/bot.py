import logging
import os
from datetime import timedelta

import requests
from auth import get_fresh_access_token
from cryptography.fernet import Fernet
from http_logger import logged_request
from models import Schedule, Token
from sqlalchemy.orm import Session
from util import add_timezone_colon, format_api_datetime, to_eastern

logger = logging.getLogger(__name__)


def get_amenity_id(court_id: str) -> int:
    """Map court_id to amenity_id for the Atrium API"""
    court_mapping = {
        "1": 8,  # Court 1 → amenity_id 8
        "2": 10,  # Court 2 → amenity_id 10
    }
    return court_mapping.get(court_id, 8)  # Default to court 1


def book_slot(
    db: Session,
    schedule_id: int,
    fernet: Fernet,
    prefilled_amenity_id: int | None = None,
):
    logger.info(f"book_slot function called for schedule {schedule_id}")
    schedule = db.query(Schedule).get(schedule_id)
    if not schedule:
        logger.error(f"Schedule {schedule_id} not found")
        return

    logger.info(
        f"Found schedule {schedule_id}: type={schedule.type.value}, desired_time={schedule.desired_time}, court_id={schedule.court_id}"
    )

    try:
        # Get fresh token
        token = db.query(Token).first()
        access_token = get_fresh_access_token(db, token.id, fernet)

        # Ensure desired_time is timezone-aware in Eastern
        desired_time = to_eastern(schedule.desired_time)

        # Calculate end time (30 minutes after start, or use duration if available)
        duration = getattr(schedule, "duration", 60)  # Default 60 minutes
        end_time = desired_time + timedelta(minutes=duration)

        # Format times for the API (ISO format with Eastern timezone)
        start_time_str = add_timezone_colon(format_api_datetime(desired_time))
        end_time_str = add_timezone_colon(format_api_datetime(end_time))

        # Prepare API payload
        amenity_id = (
            get_amenity_id(schedule.court_id or "1")
            if prefilled_amenity_id is None
            else prefilled_amenity_id
        )
        payload = {
            "amenity_type_id": "10",
            "start_time": start_time_str,
            "amenity_id": amenity_id,
            "guests": "1",
            "end_time": end_time_str,
            "amenity_reservation_type": "TR",
        }

        attempt_type = "retry" if prefilled_amenity_id is not None else "initial"
        logger.info(
            f"Booking slot {schedule_id}: Court {schedule.court_id} (amenity_id {amenity_id}) at {start_time_str} ({attempt_type} attempt)"
        )

        booking_url = (
            "https://api.atriumapp.co/api/v1/my/occupants/133055/amenity-reservations/"
        )

        response = logged_request(
            method="POST",
            url=booking_url,
            operation_name="court_booking",
            correlation_id=f"booking_{schedule_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload,
        )

        schedule.status = "success"
        logger.info(f"Booking {schedule_id} succeeded: {response.json()}")
    except Exception as e:
        # If the booking failed, try the other court
        if prefilled_amenity_id is None:
            logger.info(
                f"Booking {schedule_id} failed for court {schedule.court_id}, trying the other court"
            )
            book_slot(
                db,
                schedule_id,
                fernet,
                prefilled_amenity_id=10 if schedule.court_id == "1" else 8,
            )
            return

        schedule.status = "failed"
        logger.error(f"Booking {schedule_id} failed for both courts: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"Response body: {e.response.text}")
    finally:
        db.commit()
