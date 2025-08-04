# Tennis Court Booking Automation System

An automated tennis court booking system that integrates with the Atrium API to schedule bookings exactly 168 hours (1 week) in advance.

## Features

- **One-off Bookings**: Schedule specific date/time bookings
- **Recurring Bookings**: Use RRULE patterns for regular bookings (e.g., "Every Wednesday at 5 PM")
- **Automatic Scheduling**: Books courts exactly 168 hours in advance
- **OAuth Token Management**: Handles access token refresh automatically
- **Court Selection**: Supports Court 1 and Court 2
- **Configurable Duration**: Default 30-minute slots, customizable per booking
- **Timezone Handling**: Automatically converts to Eastern timezone for API

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Set the encryption key for token storage:

```bash
export FERNET_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
```

### 3. Configuration Files

#### `data/tokens.json`

```json
{
  "refresh_token": "your_oauth_refresh_token_here"
}
```

#### `data/schedules.json`

```json
[
  {
    "type": "one-off",
    "desired_time": "2025-08-04T07:00:00",
    "court_id": "1",
    "duration": 30
  },
  {
    "type": "recurring",
    "rrule": "FREQ=WEEKLY;BYDAY=WE;BYHOUR=17;BYMINUTE=0;COUNT=52",
    "court_id": "2",
    "duration": 30
  }
]
```

### 4. Run the Application

```bash
python main.py
```

## Configuration Details

### Court Mapping

- `"court_id": "1"` → Atrium `amenity_id: 8` (Court 1)
- `"court_id": "2"` → Atrium `amenity_id: 10` (Court 2)

### Schedule Types

#### One-off Booking

```json
{
  "type": "one-off",
  "desired_time": "2025-08-04T07:00:00",
  "court_id": "1",
  "duration": 30
}
```

#### Recurring Booking

```json
{
  "type": "recurring",
  "rrule": "FREQ=WEEKLY;BYDAY=WE;BYHOUR=17;BYMINUTE=0;COUNT=52",
  "court_id": "2",
  "duration": 60
}
```

### RRULE Examples

- Every Wednesday at 5 PM: `FREQ=WEEKLY;BYDAY=WE;BYHOUR=17;BYMINUTE=0;COUNT=52`
- Every other Friday at 10 AM: `FREQ=WEEKLY;INTERVAL=2;BYDAY=FR;BYHOUR=10;BYMINUTE=0;COUNT=26`
- Daily at 7 AM weekdays: `FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=7;BYMINUTE=0;COUNT=260`

## API Integration

The system integrates with the Atrium API:

- **URL**: `https://api.atriumapp.co/api/v1/my/occupants/133055/amenity-reservations/`
- **Method**: POST
- **Authentication**: Bearer token (OAuth)
- **Payload**:
  ```json
  {
    "amenity_type_id": "10",
    "start_time": "2025-08-04T07:00:00-04:00",
    "amenity_id": 8,
    "guests": "1",
    "end_time": "2025-08-04T07:30:00-04:00",
    "amenity_reservation_type": "TR"
  }
  ```

## How It Works

1. **Startup**: Loads configurations from JSON files into SQLite database
2. **Scheduling**: Creates APScheduler jobs for each booking trigger time (168 hours before desired time)
3. **Execution**: When trigger time arrives, calls Atrium API with proper authentication
4. **Token Management**: Automatically refreshes OAuth tokens every 20 minutes
5. **Logging**: Records all booking attempts, successes, and failures

## Database Schema

### Schedules Table

- `id`: Primary key
- `type`: ONE_OFF or RECURRING
- `desired_time`: When you want to play
- `trigger_time`: When the booking attempt will be made (168 hours before)
- `court_id`: "1" or "2"
- `duration`: Minutes (default 30)
- `status`: pending, success, failed
- `rrule`: RRULE string for recurring bookings

### Tokens Table

- `id`: Primary key
- `access_token`: Encrypted OAuth access token
- `refresh_token`: Encrypted OAuth refresh token
- `access_expiry`: Unix timestamp
- `refresh_expiry`: Unix timestamp
- `session_state`: OAuth session state

## Deployment

### Docker

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Platform Recommendations

- **Render.com**: Free tier background worker service
- **Heroku**: Worker dyno
- **Railway**: Background service

Mount `/app/data` volume for persistent configuration and database files.

## Security

- OAuth tokens are encrypted using Fernet (AES 128)
- Encryption key stored in environment variable
- Database designed for single-user but extensible for multi-user
- No sensitive data in configuration files (tokens encrypted)

## Monitoring

- Comprehensive logging to console
- API response logging for debugging
- Booking success/failure tracking in database
- Token refresh monitoring

## Troubleshooting

### Common Issues

1. **"Refresh token expired"**: Update `data/tokens.json` with fresh OAuth token
2. **"Schedule not found"**: Database may be corrupted, check `data/db.sqlite`
3. **API errors**: Check network connectivity and OAuth token validity
4. **Timezone issues**: Verify system timezone and daylight saving time handling

### Debug Mode

Set log level to DEBUG for verbose output:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Follow PEP 8 style guidelines
2. Add type hints to all functions
3. Write unit tests for new features
4. Update documentation for API changes
