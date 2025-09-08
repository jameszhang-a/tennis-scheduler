# Setup logging with JSON formatting for structured logs
import json
import logging
import os
import threading
import time

import uvicorn
from api import app, set_scheduler
from apscheduler.schedulers.background import BackgroundScheduler
from config_loader import load_configs
from models import Base
from scheduler import init_scheduler
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class JSONStructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs when structured_log extra is present"""

    def format(self, record):
        # Check if this is a structured log
        if hasattr(record, "structured_log"):
            return json.dumps(record.structured_log, ensure_ascii=False)
        else:
            # Use standard formatting for regular logs
            return super().format(record)


# Configure logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Remove any existing handlers
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Create console handler with JSON formatter
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(JSONStructuredFormatter())

# Add handler to root logger
root_logger.addHandler(console_handler)

# Also add a simple formatter for non-structured logs (backwards compatibility)
simple_handler = logging.StreamHandler()
simple_handler.setLevel(logging.INFO)
simple_handler.addFilter(lambda record: not hasattr(record, "structured_log"))
simple_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
root_logger.addHandler(simple_handler)
logger = logging.getLogger(__name__)


def run_api_server():
    """Run the FastAPI server in a separate thread"""
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)


def main():
    # Initialize DB
    db_path = os.getenv("DB_PATH", "/app/data/db.sqlite")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    # Set DB_PATH environment variable for API
    os.environ["DB_PATH"] = db_path

    # Load configs into DB
    db = Session()
    try:
        schedules_path = os.getenv("SCHEDULES_PATH", "/app/data/schedules.json")
        tokens_path = os.getenv("TOKENS_PATH", "/app/data/tokens.json")
        load_configs(db, schedules_path, tokens_path)
        logger.info("Configs loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configs: {e}")
        db.rollback()
        db.close()
        return

    # Start scheduler
    scheduler = BackgroundScheduler()
    init_scheduler(scheduler, db)
    scheduler.start()
    logger.info("Scheduler started")

    # Make scheduler available to API
    set_scheduler(scheduler)

    # Start API server in a separate thread
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    logger.info("API server started on http://0.0.0.0:8000")

    try:
        # Keep container running; check for config reloads
        while True:
            # Check periodically for manual reload signals if added later
            time.sleep(60)
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
    finally:
        db.close()


if __name__ == "__main__":
    main()
