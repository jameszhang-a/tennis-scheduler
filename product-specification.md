Product Specification

1. Features

One-Off Booking:

Input: Desired date/time (e.g., "2025-08-10 14:00"), court ID (optional), token.
Calculates trigger: Desired time - 168 hours.
At trigger, calls API to book.

Recurring Booking:

Input: Rules like "Every Wednesday at 17:00" or "Every other Friday at 10:00 starting 2025-08-03".
Uses RRULE for recurrence.
Expands to individual instances (up to 52 future ones) and schedules separate triggers.

Input Mechanism:

Load from JSON files (e.g., schedules.json: list of dicts with keys like type ("one-off" or "recurring"), desired_time, rrule, court_id; tokens.json: dict with token encrypted).
On startup/reload, parse files, validate, insert into DB if not present.

Notifications:

Basic: Log success/failure; optional email (smtplib with env vars for SMTP config).

Logging and Monitoring:

Log API calls, errors, executions to file/console.
Reload config endpoint or signal for dynamic updates (e.g., via OS signal handler).

2. Architecture

Components:

Database: SQLite for persistence—tables: Schedules (id, type, desired_time, rrule, court_id, status, trigger_time), Tokens (id, encrypted_token).
Scheduler: APScheduler (BackgroundScheduler) with SQLAlchemyJobStore for DB persistence. Loads jobs from DB on startup.
Bot Core: Function book_slot(schedule_id) that fetches details from DB, calls API with decrypted token, updates status.
Config Loader: Module to read JSON files, encrypt tokens, insert/update DB.
API Integration: requests to POST to tennis API (e.g., with bearer token).

Data Flow:

On startup: Load configs → Insert into DB → Scheduler loads/adds jobs based on triggers.
At trigger: Run book_slot() → API call → Update DB status → Log/notify.
For recurring: On load, expand RRULE, create individual schedule entries in DB, add jobs.

Security:

Encrypt tokens in DB/JSON using Fernet (key from env var).
Assume single-user for now; DB designed for multi-user.

Scalability:

Handles up to 100 schedules on free tier.

3. Engineering Requirements

Tech Stack:

Language: Python 3.10+.
Libraries:

DB: sqlalchemy.
Scheduler: apscheduler.
API: requests.
Recurrence: python-dateutil.
Encryption: cryptography.
Other: json (built-in), logging, datetime, os for signals.

Code Structure:

models.py: SQLAlchemy models (Schedule, Token).
scheduler.py: Init scheduler, add jobs from DB.
bot.py: book_slot() with API call, retries (exponential backoff, 3 attempts).
config_loader.py: Parse JSON, encrypt, upsert to DB.
utils.py: Time calcs, encryption, RRULE expansion.
main.py: Entry point—load configs, init DB, start scheduler, run loop (e.g., while True: time.sleep(60) for reload checks).

Development Standards:

Type hints, pytest for units (mock requests, test calcs).
Error Handling: Catch exceptions, log, mark failed.
Timezone: UTC handling.
Precision: Exact datetime jobs.

Performance:

Low overhead; suitable for always-on container.

4. Deployment

Platform: Render.com free tier (background worker service for non-HTTP apps).

Why? Free persistent execution, volumes for configs/DB.
Alternatives: Heroku free dyno (with worker), PythonAnywhere scheduled tasks (but less flexible for always-on).

Containerization: Docker.

Dockerfile:
textFROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]

Volumes: Mount /app/data for schedules.json, tokens.json, db.sqlite.
