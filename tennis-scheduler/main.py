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

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
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
