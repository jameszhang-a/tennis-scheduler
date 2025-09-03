# Tennis Scheduler API - Quick Start Guide

## What's New

I've implemented a REST API for your tennis scheduler using FastAPI. The API runs alongside your existing scheduler and provides endpoints to:

- View all scheduled tasks
- Filter schedules by status or court
- Get upcoming reservations
- Check scheduler status and active jobs
- View statistics and token status
- Cancel pending schedules

## Quick Start

### 1. Run Locally (Easiest for Testing)

```bash
# Make sure you're in the project directory
cd /Users/james/code/project/tennis-scheduler

# Run the scheduler with API
python run_local.py
```

The API will be available at:

- **API Base**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc

### 2. Test with Postman

#### Option A: Import the Collection

1. Open Postman
2. Click "Import"
3. Select the file: `tennis-scheduler.postman_collection.json`
4. All endpoints will be ready to test!

#### Option B: Manual Testing

Try these URLs in Postman:

```
GET http://localhost:8000/api/health
GET http://localhost:8000/api/schedules?status=pending
GET http://localhost:8000/api/scheduler/status
GET http://localhost:8000/api/stats
```

### 3. Key Endpoints

| Endpoint                      | Description                       |
| ----------------------------- | --------------------------------- |
| `GET /api/schedules`          | List all schedules (with filters) |
| `GET /api/schedules/upcoming` | Get next 7 days of schedules      |
| `GET /api/scheduler/status`   | Check if scheduler is running     |
| `GET /api/stats`              | Get booking statistics            |
| `DELETE /api/schedules/{id}`  | Cancel a pending schedule         |

## Technical Details

### Architecture

- **Framework**: FastAPI (async, modern Python web framework)
- **Database**: Same SQLite database as your scheduler
- **Threading**: API runs in separate thread from scheduler
- **CORS**: Enabled for future React integration

### Files Added/Modified

1. **`tennis-scheduler/api.py`** - Main API implementation
2. **`tennis-scheduler/main.py`** - Updated to run API server
3. **`run_local.py`** - Local development runner
4. **`API_DOCUMENTATION.md`** - Full API documentation
5. **`tennis-scheduler.postman_collection.json`** - Postman collection

### Why FastAPI?

- Already in your requirements.txt
- Automatic API documentation
- Built-in validation with Pydantic
- Great performance with async support
- Easy integration with React frontends
- Type hints for better code clarity

## Next Steps

1. **Test the API** - Run it locally and try the endpoints
2. **React Admin Portal** - When ready, the API is CORS-enabled for frontend integration
3. **Authentication** - Consider adding API key or OAuth for production
4. **Deployment** - The Docker setup already includes the API

## Example API Response

```json
// GET /api/schedules?status=pending&limit=2
[
  {
    "id": 1,
    "type": "recurring",
    "desired_time": "2024-01-09T18:00:00-05:00",
    "trigger_time": "2024-01-02T18:00:00-05:00",
    "court_id": "1",
    "status": "pending",
    "duration": 60,
    "rrule": "FREQ=WEEKLY;BYDAY=TU;BYHOUR=18;BYMINUTE=0;COUNT=10"
  },
  {
    "id": 2,
    "type": "recurring",
    "desired_time": "2024-01-16T18:00:00-05:00",
    "trigger_time": "2024-01-09T18:00:00-05:00",
    "court_id": "1",
    "status": "pending",
    "duration": 60,
    "rrule": "FREQ=WEEKLY;BYDAY=TU;BYHOUR=18;BYMINUTE=0;COUNT=10"
  }
]
```

## Troubleshooting

- **Port 8000 in use**: Change the port in `main.py` and `run_local.py`
- **Import errors**: Make sure you're running from the project root
- **No schedules**: Check that your `data/schedules.json` has valid entries
- **FERNET_KEY warning**: The script generates a temporary key for testing
