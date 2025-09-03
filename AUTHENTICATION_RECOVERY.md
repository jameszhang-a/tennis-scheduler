# Authentication Token Recovery Guide

## Problem Diagnosis

The error you encountered indicates that the refresh token has expired, causing all subsequent authentication attempts to fail. This is a cascading failure that affects:

1. **Token Refresh Job**: Fails every 20 minutes with "Refresh token expired" error
2. **Booking Jobs**: Will fail when they try to get fresh access tokens
3. **Scheduler Continues**: APScheduler keeps running but all token-dependent jobs fail

## Enhanced Monitoring

I've added new API endpoints to help detect and monitor this issue:

### New Endpoints:

#### 1. Enhanced Token Status

```bash
GET /api/token/status
```

**New fields added:**

- `refresh_token_expired`: Boolean indicating if refresh token is expired
- `days_until_refresh_expires`: Days remaining before refresh token expires
- `last_refresh_attempt`: Estimated last token refresh attempt time

#### 2. Scheduler Alerts

```bash
GET /api/scheduler/alerts
```

**Provides:**

- Critical alerts (expired tokens, scheduler down)
- Warnings (tokens expiring soon, access token expired)
- Alert counts and overall status
- Actionable recommendations

## Recovery Steps

### 1. Check Current Status

```bash
# Check token status
curl http://localhost:8000/api/token/status

# Check for alerts
curl http://localhost:8000/api/scheduler/alerts
```

### 2. If Refresh Token Expired

**Manual intervention required:**

1. **Get new refresh token** from the tennis booking website:

   - Log into the booking system in your browser
   - Use browser dev tools to capture the OAuth response
   - Extract the new `refresh_token` value

2. **Update tokens.json:**

   ```json
   {
     "refresh_token": "your_new_refresh_token_here"
   }
   ```

3. **Restart the scheduler:**

   ```bash
   # If running locally
   Ctrl+C to stop, then python run_local.py

   # If running in Docker
   docker-compose restart
   ```

### 3. Preventive Monitoring

Set up regular monitoring by checking these endpoints:

```bash
# Daily check - should show "healthy" status
curl http://localhost:8000/api/scheduler/alerts

# Weekly check - monitor token expiry
curl http://localhost:8000/api/token/status
```

## Root Cause Analysis

### Why This Happens:

1. **Refresh tokens have limited lifespans** (typically 7-30 days)
2. **No automatic recovery** for expired refresh tokens
3. **OAuth flow requires manual intervention** to get new refresh tokens
4. **APScheduler doesn't stop jobs** that consistently fail

### System Behavior:

- Scheduler logs show repeated "Refresh token expired" errors
- Token refresh job continues running every 20 minutes but always fails
- Access tokens become stale and can't be refreshed
- Booking attempts fail silently or with authentication errors

## Enhanced Error Handling

The enhanced token status endpoint now provides:

1. **Proactive warnings** when tokens are about to expire
2. **Clear status indicators** for token health
3. **Days remaining** calculations for planning token renewal
4. **Actionable alerts** with specific recovery steps

## Recommended Monitoring Strategy

1. **Add to monitoring dashboard**: Check `/api/scheduler/alerts` endpoint
2. **Set up notifications**: Alert when `status` is not "healthy"
3. **Weekly token checks**: Monitor `days_until_refresh_expires`
4. **Automate token renewal reminders**: When < 7 days remaining

## Prevention

To prevent this issue:

1. **Monitor token expiry dates** using the new API endpoints
2. **Set calendar reminders** to renew tokens before expiry
3. **Consider implementing webhook notifications** for token alerts
4. **Document the token renewal process** for your team

The enhanced API now gives you visibility into this issue before it becomes critical, allowing for proactive token management.
