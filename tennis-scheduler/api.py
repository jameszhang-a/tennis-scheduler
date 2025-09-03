from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine, func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
import pytz
from models import Base, Schedule, ScheduleType, Token
from apscheduler.schedulers.background import BackgroundScheduler
import os
import logging

logger = logging.getLogger(__name__)

# Pydantic models for API responses
class ScheduleResponse(BaseModel):
    id: int
    type: str
    desired_time: datetime
    trigger_time: datetime
    court_id: Optional[str]
    status: str
    duration: int
    rrule: Optional[str]
    
    @validator('type', pre=True)
    def convert_enum(cls, v):
        if hasattr(v, 'value'):
            return v.value
        return v
    
    @validator('desired_time', 'trigger_time')
    def convert_timezone(cls, dt):
        # Ensure times are in Eastern timezone for display
        eastern = pytz.timezone('US/Eastern')
        if dt.tzinfo is None:
            return eastern.localize(dt)
        return dt.astimezone(eastern)
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class SchedulerJobResponse(BaseModel):
    job_id: str
    next_run_time: Optional[datetime]
    name: str
    func_name: str
    args: Optional[List[str]] = []
    kwargs: Optional[dict] = {}
    trigger: str
    misfire_grace_time: Optional[int]
    max_instances: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class SchedulerStatusResponse(BaseModel):
    is_running: bool
    total_jobs: int
    jobs: List[SchedulerJobResponse]

class StatsResponse(BaseModel):
    total_schedules: int
    pending_schedules: int
    successful_schedules: int
    failed_schedules: int
    next_booking: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class TokenStatusResponse(BaseModel):
    has_refresh_token: bool
    access_token_valid: bool
    access_expiry: Optional[datetime]
    refresh_expiry: Optional[datetime]
    refresh_token_expired: bool
    days_until_refresh_expires: Optional[float]
    last_refresh_attempt: Optional[datetime]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

# Create FastAPI app
app = FastAPI(
    title="Tennis Scheduler API",
    description="API for managing tennis court reservations",
    version="1.0.0"
)

# Add CORS middleware for future React integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
def get_engine():
    db_path = os.getenv("DB_PATH", "/app/data/db.sqlite")
    return create_engine(f"sqlite:///{db_path}")

# Dependency to get DB session
def get_db():
    SessionLocal = sessionmaker(bind=get_engine())
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Store scheduler reference
scheduler_ref = {"scheduler": None}

def set_scheduler(scheduler: BackgroundScheduler):
    """Set the scheduler reference for API access"""
    scheduler_ref["scheduler"] = scheduler

def get_scheduler():
    """Get the scheduler instance"""
    return scheduler_ref["scheduler"]

@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "tennis-scheduler"}

@app.get("/api/schedules", response_model=List[ScheduleResponse])
def get_schedules(
    status: Optional[str] = Query(None, description="Filter by status (pending, success, failed)"),
    court_id: Optional[str] = Query(None, description="Filter by court ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: Session = Depends(get_db)
):
    """Get all schedules with optional filtering"""
    query = db.query(Schedule)
    
    if status:
        query = query.filter(Schedule.status == status)
    if court_id:
        query = query.filter(Schedule.court_id == court_id)
    
    # Order by desired_time descending (most recent first)
    query = query.order_by(Schedule.desired_time.desc())
    
    schedules = query.offset(offset).limit(limit).all()
    return schedules

@app.get("/api/schedules/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Get a specific schedule by ID"""
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule

def _format_scheduler_job(job) -> SchedulerJobResponse:
    """Helper function to format a scheduler job"""
    # Convert args to string representation for JSON serialization
    args_str = [str(arg) for arg in job.args] if job.args else []
    kwargs_str = {k: str(v) for k, v in job.kwargs.items()} if job.kwargs else {}
    
    return SchedulerJobResponse(
        job_id=job.id,
        next_run_time=job.next_run_time.astimezone(pytz.timezone('US/Eastern')) if job.next_run_time else None,
        name=job.name,
        func_name=job.func.__name__ if hasattr(job.func, '__name__') else str(job.func),
        args=args_str,
        kwargs=kwargs_str,
        trigger=str(job.trigger),
        misfire_grace_time=job.misfire_grace_time,
        max_instances=job.max_instances
    )

@app.get("/api/scheduler/status", response_model=SchedulerStatusResponse)
def get_scheduler_status():
    """Get the current status of the scheduler"""
    scheduler = get_scheduler()
    if not scheduler:
        return SchedulerStatusResponse(is_running=False, total_jobs=0, jobs=[])
    
    jobs = [_format_scheduler_job(job) for job in scheduler.get_jobs()]
    
    return SchedulerStatusResponse(
        is_running=scheduler.running,
        total_jobs=len(jobs),
        jobs=jobs
    )

@app.get("/api/scheduler/jobs", response_model=List[SchedulerJobResponse])
def get_scheduler_jobs(
    job_type: Optional[str] = Query(None, description="Filter by job type (booking, token_refresh)"),
    sort_by: str = Query("next_run_time", description="Sort by: next_run_time, job_id, func_name"),
    order: str = Query("asc", description="Sort order: asc, desc"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results")
):
    """Get all scheduler jobs with filtering and sorting options"""
    scheduler = get_scheduler()
    if not scheduler:
        return []
    
    jobs = [_format_scheduler_job(job) for job in scheduler.get_jobs()]
    
    # Filter by job type
    if job_type:
        if job_type.lower() == "booking":
            jobs = [job for job in jobs if job.job_id.startswith("booking_")]
        elif job_type.lower() == "token_refresh":
            jobs = [job for job in jobs if job.job_id == "token_refresh"]
        elif job_type.lower() == "other":
            jobs = [job for job in jobs if not job.job_id.startswith("booking_") and job.job_id != "token_refresh"]
    
    # Sort jobs
    reverse = order.lower() == "desc"
    if sort_by == "next_run_time":
        jobs.sort(key=lambda x: x.next_run_time or datetime.min.replace(tzinfo=pytz.UTC), reverse=reverse)
    elif sort_by == "job_id":
        jobs.sort(key=lambda x: x.job_id, reverse=reverse)
    elif sort_by == "func_name":
        jobs.sort(key=lambda x: x.func_name, reverse=reverse)
    
    return jobs[:limit]

@app.get("/api/scheduler/jobs/upcoming", response_model=List[SchedulerJobResponse])
def get_upcoming_jobs(
    hours: int = Query(24, ge=1, le=168, description="Number of hours to look ahead"),
    job_type: Optional[str] = Query(None, description="Filter by job type (booking, token_refresh)")
):
    """Get scheduler jobs that will run in the next N hours"""
    scheduler = get_scheduler()
    if not scheduler:
        return []
    
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    end_time = now + timedelta(hours=hours)
    
    jobs = [_format_scheduler_job(job) for job in scheduler.get_jobs()]
    
    # Filter by time range
    upcoming_jobs = [
        job for job in jobs 
        if job.next_run_time and now <= job.next_run_time <= end_time
    ]
    
    # Filter by job type if specified
    if job_type:
        if job_type.lower() == "booking":
            upcoming_jobs = [job for job in upcoming_jobs if job.job_id.startswith("booking_")]
        elif job_type.lower() == "token_refresh":
            upcoming_jobs = [job for job in upcoming_jobs if job.job_id == "token_refresh"]
    
    # Sort by next run time
    upcoming_jobs.sort(key=lambda x: x.next_run_time)
    
    return upcoming_jobs

@app.get("/api/scheduler/jobs/token-refresh", response_model=List[SchedulerJobResponse])
def get_token_refresh_jobs():
    """Get all token refresh jobs"""
    scheduler = get_scheduler()
    if not scheduler:
        return []
    
    jobs = [_format_scheduler_job(job) for job in scheduler.get_jobs()]
    token_jobs = [job for job in jobs if "token" in job.job_id.lower() or "refresh" in job.func_name.lower()]
    
    return token_jobs

@app.get("/api/scheduler/alerts")
def get_scheduler_alerts(db: Session = Depends(get_db)):
    """Get alerts about potential scheduler issues"""
    alerts = []
    warnings = []
    
    # Check token status
    token = db.query(Token).first()
    if token:
        import time
        current_time = time.time()
        
        # Critical: Refresh token expired
        if token.refresh_expiry and token.refresh_expiry < current_time:
            alerts.append({
                "type": "critical",
                "category": "authentication",
                "message": "Refresh token has expired. Update tokens.json with new credentials.",
                "action_required": "Manual token update needed",
                "timestamp": datetime.fromtimestamp(token.refresh_expiry).isoformat()
            })
        
        # Warning: Refresh token expiring soon (within 7 days)
        elif token.refresh_expiry and (token.refresh_expiry - current_time) < (7 * 24 * 3600):
            days_left = (token.refresh_expiry - current_time) / (24 * 3600)
            warnings.append({
                "type": "warning",
                "category": "authentication",
                "message": f"Refresh token expires in {days_left:.1f} days",
                "action_required": "Plan token renewal",
                "timestamp": datetime.fromtimestamp(token.refresh_expiry).isoformat()
            })
        
        # Warning: Access token expired (should refresh automatically)
        if token.access_expiry and token.access_expiry < current_time:
            warnings.append({
                "type": "warning",
                "category": "authentication",
                "message": "Access token has expired. Next booking may fail if token refresh also fails.",
                "action_required": "Monitor next booking attempt",
                "timestamp": datetime.fromtimestamp(token.access_expiry).isoformat()
            })
    else:
        alerts.append({
            "type": "critical",
            "category": "authentication",
            "message": "No authentication tokens found in database",
            "action_required": "Configure tokens.json and restart scheduler",
            "timestamp": datetime.now().isoformat()
        })
    
    # Check for upcoming bookings without valid tokens
    if alerts:  # If there are token issues
        eastern = pytz.timezone('US/Eastern')
        now = datetime.now(eastern)
        end_time = now + timedelta(days=7)
        
        upcoming_schedules = db.query(Schedule).filter(
            Schedule.status == "pending",
            Schedule.desired_time >= now,
            Schedule.desired_time <= end_time
        ).count()
        
        if upcoming_schedules > 0:
            alerts.append({
                "type": "critical",
                "category": "bookings",
                "message": f"{upcoming_schedules} upcoming bookings will fail due to token issues",
                "action_required": "Fix authentication tokens immediately",
                "timestamp": now.isoformat()
            })
    
    # Check scheduler status
    scheduler = get_scheduler()
    if not scheduler or not scheduler.running:
        alerts.append({
            "type": "critical",
            "category": "scheduler",
            "message": "Scheduler is not running",
            "action_required": "Restart the scheduler service",
            "timestamp": datetime.now().isoformat()
        })
    
    return {
        "alerts": alerts,
        "warnings": warnings,
        "alert_count": len(alerts),
        "warning_count": len(warnings),
        "status": "critical" if alerts else "warning" if warnings else "healthy",
        "last_check": datetime.now().isoformat()
    }

@app.get("/api/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Get scheduler statistics"""
    total = db.query(func.count(Schedule.id)).scalar()
    pending = db.query(func.count(Schedule.id)).filter(Schedule.status == "pending").scalar()
    successful = db.query(func.count(Schedule.id)).filter(Schedule.status == "success").scalar()
    failed = db.query(func.count(Schedule.id)).filter(Schedule.status == "failed").scalar()
    
    # Get next pending booking
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    next_booking = db.query(Schedule).filter(
        Schedule.status == "pending",
        Schedule.desired_time > now
    ).order_by(Schedule.desired_time).first()
    
    return StatsResponse(
        total_schedules=total,
        pending_schedules=pending,
        successful_schedules=successful,
        failed_schedules=failed,
        next_booking=next_booking.desired_time if next_booking else None
    )

@app.get("/api/token/status", response_model=TokenStatusResponse)
def get_token_status(db: Session = Depends(get_db)):
    """Get the status of authentication tokens with enhanced monitoring"""
    token = db.query(Token).first()
    if not token:
        return TokenStatusResponse(
            has_refresh_token=False,
            access_token_valid=False,
            access_expiry=None,
            refresh_expiry=None,
            refresh_token_expired=True,
            days_until_refresh_expires=None,
            last_refresh_attempt=None
        )
    
    import time
    current_time = time.time()
    
    # Calculate refresh token status
    refresh_expired = token.refresh_expiry < current_time if token.refresh_expiry else True
    days_until_expires = None
    if token.refresh_expiry and not refresh_expired:
        days_until_expires = (token.refresh_expiry - current_time) / (24 * 3600)
    
    # Check for recent token refresh attempts in scheduler logs
    # This is a simplified approach - in production you might want to store this in the database
    scheduler = get_scheduler()
    last_refresh_attempt = None
    if scheduler:
        for job in scheduler.get_jobs():
            if job.id == "token_refresh" and hasattr(job, 'next_run_time'):
                # Estimate last run time based on interval
                if job.next_run_time:
                    eastern = pytz.timezone('US/Eastern')
                    next_run = job.next_run_time.astimezone(eastern)
                    # Token refresh runs every 20 minutes, so last attempt was ~20 minutes before next
                    last_refresh_attempt = next_run - timedelta(minutes=20)
                break
    
    return TokenStatusResponse(
        has_refresh_token=bool(token.refresh_token),
        access_token_valid=token.access_expiry > current_time if token.access_expiry else False,
        access_expiry=datetime.fromtimestamp(token.access_expiry) if token.access_expiry else None,
        refresh_expiry=datetime.fromtimestamp(token.refresh_expiry) if token.refresh_expiry else None,
        refresh_token_expired=refresh_expired,
        days_until_refresh_expires=round(days_until_expires, 2) if days_until_expires else None,
        last_refresh_attempt=last_refresh_attempt
    )

@app.get("/api/schedules/upcoming", response_model=List[ScheduleResponse])
def get_upcoming_schedules(
    days: int = Query(7, ge=1, le=30, description="Number of days to look ahead"),
    db: Session = Depends(get_db)
):
    """Get upcoming schedules for the next N days"""
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    end_date = now + timedelta(days=days)
    
    schedules = db.query(Schedule).filter(
        Schedule.status == "pending",
        Schedule.desired_time >= now,
        Schedule.desired_time <= end_date
    ).order_by(Schedule.desired_time).all()
    
    return schedules

@app.get("/api/scheduler/summary")
def get_scheduler_summary():
    """Get a summary of scheduler status including both database schedules and live jobs"""
    scheduler = get_scheduler()
    if not scheduler:
        return {
            "scheduler_running": False,
            "live_jobs": {"total": 0, "booking_jobs": 0, "token_refresh_jobs": 0, "other_jobs": 0},
            "next_token_refresh": None,
            "next_booking": None,
            "message": "Scheduler not available"
        }
    
    jobs = [_format_scheduler_job(job) for job in scheduler.get_jobs()]
    
    # Categorize jobs
    booking_jobs = [job for job in jobs if job.job_id.startswith("booking_")]
    token_jobs = [job for job in jobs if job.job_id == "token_refresh"]
    other_jobs = [job for job in jobs if not job.job_id.startswith("booking_") and job.job_id != "token_refresh"]
    
    # Find next occurrences
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    
    future_booking_jobs = [job for job in booking_jobs if job.next_run_time and job.next_run_time > now]
    future_token_jobs = [job for job in token_jobs if job.next_run_time and job.next_run_time > now]
    
    next_booking = min(future_booking_jobs, key=lambda x: x.next_run_time).next_run_time if future_booking_jobs else None
    next_token_refresh = min(future_token_jobs, key=lambda x: x.next_run_time).next_run_time if future_token_jobs else None
    
    return {
        "scheduler_running": scheduler.running,
        "live_jobs": {
            "total": len(jobs),
            "booking_jobs": len(booking_jobs),
            "token_refresh_jobs": len(token_jobs),
            "other_jobs": len(other_jobs)
        },
        "next_token_refresh": next_token_refresh.isoformat() if next_token_refresh else None,
        "next_booking": next_booking.isoformat() if next_booking else None,
        "current_time": now.isoformat()
    }

@app.delete("/api/schedules/{schedule_id}")
def cancel_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Cancel a pending schedule"""
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    if schedule.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending schedules can be cancelled")
    
    # Update schedule status
    schedule.status = "cancelled"
    db.commit()
    
    # Remove from scheduler if exists
    scheduler = get_scheduler()
    if scheduler:
        job_id = f"booking_{schedule_id}"
        try:
            scheduler.remove_job(job_id)
            logger.info(f"Removed job {job_id} from scheduler")
        except:
            pass  # Job might not exist
    
    return {"message": "Schedule cancelled successfully", "schedule_id": schedule_id}

if __name__ == "__main__":
    # This allows running the API standalone for testing
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
