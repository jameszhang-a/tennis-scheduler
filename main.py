import os
import time
import logging
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from apscheduler.schedulers.background import BackgroundScheduler
from config_loader import load_configs
from scheduler import init_scheduler
from models import Base

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    # Initialize DB
    db_path = "/app/data/db.sqlite"
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    
    # Load configs into DB
    db = Session()
    try:
        load_configs(db, "/app/data/schedules.json", "/app/data/tokens.json")
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
    
    try:
        # Keep container running; check for config reloads
        while True:
            time.sleep(60)  # Check periodically for manual reload signals if added later
    except KeyboardInterrupt:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
    finally:
        db.close()

if __name__ == "__main__":
    main()