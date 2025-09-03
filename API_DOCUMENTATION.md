# Tennis Scheduler API Documentation

## Overview

The Tennis Scheduler API provides endpoints to manage and monitor tennis court reservations. The API is built with FastAPI and includes automatic interactive documentation.

## Running the API

### Local Development

```bash
# Install dependencies (if not already installed)
pip install -r requirements.txt

# Run the API locally
python run_local.py
```

The API will be available at:

- API Base URL: `http://localhost:8000`
- Interactive API Documentation (Swagger UI): `http://localhost:8000/docs`
- Alternative API Documentation (ReDoc): `http://localhost:8000/redoc`

### Docker

The API runs automatically when you start the Docker container:

```bash
docker-compose up
```

## API Endpoints

### Health Check

```
GET /api/health
```

Returns the health status of the service.

**Response:**

```json
{
  "status": "healthy",
  "service": "tennis-scheduler"
}
```

### Get All Schedules

```
GET /api/schedules
```

Retrieve all scheduled reservations with optional filtering.

**Query Parameters:**

- `status` (optional): Filter by status (`pending`, `success`, `failed`)
- `court_id` (optional): Filter by court ID (`1` or `2`)
- `limit` (optional, default: 100): Maximum number of results (1-1000)
- `offset` (optional, default: 0): Number of results to skip for pagination

**Example Request:**

```
GET /api/schedules?status=pending&court_id=1&limit=10
```

**Response:**

```json
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
  }
]
```

### Get Schedule by ID

```
GET /api/schedules/{schedule_id}
```

Retrieve a specific schedule by its ID.

**Response:** Single schedule object (same format as above)

### Get Upcoming Schedules

```
GET /api/schedules/upcoming
```

Get all pending schedules for the next N days.

**Query Parameters:**

- `days` (optional, default: 7): Number of days to look ahead (1-30)

### Cancel Schedule

```
DELETE /api/schedules/{schedule_id}
```

Cancel a pending schedule. Only pending schedules can be cancelled.

**Response:**

```json
{
  "message": "Schedule cancelled successfully",
  "schedule_id": 1
}
```

### Get Scheduler Status

```
GET /api/scheduler/status
```

Get the current status of the background scheduler, including all active jobs.

**Response:**

```json
{
  "is_running": true,
  "total_jobs": 5,
  "jobs": [
    {
      "job_id": "booking_1",
      "next_run_time": "2024-01-02T18:00:00-05:00",
      "name": "book_slot"
    },
    {
      "job_id": "token_refresh",
      "next_run_time": "2024-01-01T14:20:00-05:00",
      "name": "get_fresh_access_token"
    }
  ]
}
```

### Get Statistics

```
GET /api/stats
```

Get overall statistics about the scheduler.

**Response:**

```json
{
  "total_schedules": 52,
  "pending_schedules": 48,
  "successful_schedules": 3,
  "failed_schedules": 1,
  "next_booking": "2024-01-02T18:00:00-05:00"
}
```

### Get Token Status

```
GET /api/token/status
```

Check the status of authentication tokens.

**Response:**

```json
{
  "has_refresh_token": true,
  "access_token_valid": true,
  "access_expiry": "2024-01-01T15:30:00",
  "refresh_expiry": "2024-01-08T14:00:00"
}
```

## Testing with Postman

1. **Import to Postman:**

   - Open Postman
   - Create a new collection called "Tennis Scheduler"
   - Add the base URL as a variable: `{{base_url}}` = `http://localhost:8000`

2. **Example Requests:**

   **Get All Pending Schedules:**

   ```
   GET {{base_url}}/api/schedules?status=pending
   ```

   **Get Next 14 Days of Schedules:**

   ```
   GET {{base_url}}/api/schedules/upcoming?days=14
   ```

   **Check Scheduler Health:**

   ```
   GET {{base_url}}/api/scheduler/status
   ```

3. **Postman Collection (Save as tennis-scheduler.postman_collection.json):**
   ```json
   {
     "info": {
       "name": "Tennis Scheduler API",
       "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
     },
     "variable": [
       {
         "key": "base_url",
         "value": "http://localhost:8000",
         "type": "string"
       }
     ],
     "item": [
       {
         "name": "Health Check",
         "request": {
           "method": "GET",
           "url": "{{base_url}}/api/health"
         }
       },
       {
         "name": "Get All Schedules",
         "request": {
           "method": "GET",
           "url": "{{base_url}}/api/schedules"
         }
       },
       {
         "name": "Get Pending Schedules",
         "request": {
           "method": "GET",
           "url": "{{base_url}}/api/schedules?status=pending"
         }
       },
       {
         "name": "Get Upcoming Schedules",
         "request": {
           "method": "GET",
           "url": "{{base_url}}/api/schedules/upcoming"
         }
       },
       {
         "name": "Get Scheduler Status",
         "request": {
           "method": "GET",
           "url": "{{base_url}}/api/scheduler/status"
         }
       },
       {
         "name": "Get Statistics",
         "request": {
           "method": "GET",
           "url": "{{base_url}}/api/stats"
         }
       },
       {
         "name": "Get Token Status",
         "request": {
           "method": "GET",
           "url": "{{base_url}}/api/token/status"
         }
       }
     ]
   }
   ```

## Response Models

All datetime fields are returned in ISO 8601 format with timezone information (Eastern Time).

### Schedule Object

- `id`: Unique identifier
- `type`: Schedule type (`one-off` or `recurring`)
- `desired_time`: When the court should be booked
- `trigger_time`: When the booking attempt will be made (7 days before desired_time)
- `court_id`: Court identifier (`1` or `2`)
- `status`: Current status (`pending`, `success`, `failed`, `cancelled`)
- `duration`: Reservation duration in minutes
- `rrule`: Recurrence rule for recurring schedules (RFC 5545 format)

## Error Responses

The API uses standard HTTP status codes:

- `200 OK`: Successful request
- `404 Not Found`: Resource not found
- `400 Bad Request`: Invalid request parameters
- `500 Internal Server Error`: Server error

Error responses include a detail message:

```json
{
  "detail": "Schedule not found"
}
```

## CORS Configuration

The API is configured to accept requests from any origin for development. In production, update the CORS settings in `api.py` to restrict access to your React frontend domain.

## Future React Integration

The API is designed to be easily integrated with a React admin portal. The CORS middleware is already configured, and all responses use JSON format compatible with modern frontend frameworks.

Example React fetch:

```javascript
const response = await fetch(
  "http://localhost:8000/api/schedules?status=pending"
);
const schedules = await response.json();
```
