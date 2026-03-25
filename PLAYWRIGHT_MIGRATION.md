# Migrating to Playwright Authentication

This guide explains how to migrate from manual refresh token management to automated Playwright-based authentication.

## What Changed?

### Before (Refresh Token Flow)

- Required manual token updates in `tokens.json`
- Refresh tokens expired every ~30 days
- Complex token refresh scheduling
- System failed when refresh tokens expired

### After (Playwright Flow)

- Automatic browser login before each booking
- No manual token management
- Fresh tokens obtained every time
- System handles authentication automatically

## Migration Steps

### 1. Update Environment Variables

Add your TFC credentials to `.env`:

```bash
# Add these new variables
TFC_USERNAME=your_tfc_username
TFC_PASSWORD=your_tfc_password

# Optional: Control headless mode (default: true)
PLAYWRIGHT_HEADLESS=true
```

### 2. Optional: Remove tokens.json

The `tokens.json` file is now **optional**. You can:

**Option A: Remove it entirely**

```bash
rm data/tokens.json  # System will use Playwright only
```

**Option B: Keep it as backup**

- System will try refresh token first
- Falls back to Playwright if refresh fails
- Useful for hybrid approach

### 3. Rebuild Docker Image

```bash
# Pull latest code
git pull

# Rebuild with Playwright dependencies
docker build -t tennis-scheduler .

# Run with new environment variables
docker run -d \
  -e TFC_USERNAME=your_username \
  -e TFC_PASSWORD=your_password \
  -e FERNET_KEY=your_key \
  -v $(pwd)/data:/app/data \
  -p 8000:8000 \
  tennis-scheduler
```

### 4. Verify Playwright Works

Check the logs to confirm Playwright authentication:

```bash
docker logs <container_id> | grep -i playwright
```

You should see:

```
Scheduled Playwright login for booking X at [time] Eastern
Successfully captured access token (expires in 1800s)
Token obtained via Playwright for booking X
```

## Configuration Options

### Environment Variables

| Variable              | Default | Description                     |
| --------------------- | ------- | ------------------------------- |
| `TFC_USERNAME`        | -       | TFC account username (required) |
| `TFC_PASSWORD`        | -       | TFC account password (required) |
| `PLAYWRIGHT_HEADLESS` | `true`  | Run browser in headless mode    |

### Headless Mode

**Headless (default):**

```bash
PLAYWRIGHT_HEADLESS=true  # Browser runs invisibly
```

**Headful (for debugging):**

```bash
PLAYWRIGHT_HEADLESS=false  # Browser window visible (but backgrounded in Docker)
```

## How It Works

### Authentication Timeline

```
Booking scheduled for: 10:00 AM
├── 09:56 AM - Playwright login starts
│   ├── Launch browser
│   ├── Navigate to my.tfc.com
│   ├── Fill credentials
│   ├── Intercept OAuth token
│   └── Store in database (encrypted)
├── 09:57 AM - Login complete
└── 10:00 AM - Booking executes with fresh token
```

### Scheduling Logic

1. **New Schedule Created** → Playwright job scheduled 4 min before booking
2. **Playwright Job Runs** → Gets fresh access token via browser automation
3. **Booking Job Runs** → Uses fresh token from Playwright

## Troubleshooting

### Playwright Login Fails

**Check credentials:**

```bash
# Verify env vars are set
docker exec <container_id> printenv | grep TFC_
```

**Check for captcha:**

```bash
# View Playwright logs
docker logs <container_id> | grep "captcha\|2FA\|verification"
```

### Headless Mode Blocked

If the site blocks headless browsers:

```bash
# Switch to headful mode
docker run -d \
  -e PLAYWRIGHT_HEADLESS=false \
  ... other vars
```

### Browser Not Found in Docker

Rebuild the image to ensure Playwright is installed:

```bash
docker build --no-cache -t tennis-scheduler .
```

## Monitoring

### Check Scheduled Jobs

```bash
curl http://localhost:8000/api/scheduler/jobs | jq .
```

Look for `playwright_auth_*` jobs:

```json
{
  "job_id": "playwright_auth_123",
  "func_name": "playwright_login_wrapper",
  "next_run_time": "2024-10-01T09:56:00-04:00"
}
```

### Check Token Status

```bash
curl http://localhost:8000/api/token/status | jq .
```

With Playwright, you'll see tokens refreshed before each booking.

## Rollback Plan

If you need to rollback to refresh tokens:

1. **Restore tokens.json:**

   ```bash
   # Restore from backup
   cp data/tokens.json.backup data/tokens.json
   ```

2. **Remove TFC credentials from env:**

   ```bash
   # System will fall back to refresh token flow
   docker run -d \
     -e FERNET_KEY=your_key \
     -v $(pwd)/data:/app/data \
     tennis-scheduler
   ```

3. **Checkout previous version:**
   ```bash
   git checkout <previous-commit>
   docker build -t tennis-scheduler .
   ```

## FAQ

**Q: Do I still need tokens.json?**  
A: No, it's optional. Playwright can handle all authentication.

**Q: Will my existing schedules work?**  
A: Yes, they'll automatically use Playwright authentication.

**Q: What if my password changes?**  
A: Update the `TFC_PASSWORD` environment variable and restart the container.

**Q: Does this work with 2FA?**  
A: No, Playwright cannot solve 2FA automatically. Disable 2FA or use app-specific passwords.

**Q: Is it slower than refresh tokens?**  
A: Login takes ~3-8 seconds, but runs 4 minutes before booking, so no impact.

**Q: Can I use both methods?**  
A: Yes! Keep tokens.json and add Playwright. System tries refresh first, falls back to Playwright.

## Security Considerations

### Credential Storage

**Production:**

- Use secrets management (Kubernetes Secrets, AWS Secrets Manager, etc.)
- Never commit credentials to git
- Use environment variable injection

**Example with Docker Secrets:**

```bash
echo "your_username" | docker secret create tfc_username -
echo "your_password" | docker secret create tfc_password -

docker service create \
  --secret tfc_username \
  --secret tfc_password \
  ...
```

### Token Encryption

- Access tokens still encrypted with Fernet
- Same security level as before
- Tokens stored in database, not logs

## Performance Impact

| Metric          | Before                 | After        | Change                     |
| --------------- | ---------------------- | ------------ | -------------------------- |
| Container Size  | ~200MB                 | ~400MB       | +200MB (Chromium)          |
| Memory (idle)   | ~50MB                  | ~50MB        | No change                  |
| Memory (auth)   | ~50MB                  | ~200MB       | +150MB during login        |
| Auth Time       | ~0.5s (refresh)        | ~5s (login)  | +4.5s (not during booking) |
| Booking Success | Fails if token expired | Always works | ✅ Improved                |

## Next Steps

1. ✅ Verify headless test passes
2. ✅ Add credentials to environment
3. ✅ Deploy updated container
4. ✅ Monitor first booking
5. ✅ Remove tokens.json (optional)

## Support

If you encounter issues:

1. Check logs: `docker logs <container_id>`
2. Test locally: `python test_headless_login.py`
3. Review screenshots in project root
4. Check Playwright docs: https://playwright.dev

---

**Migration Complete!** 🎉  
Your scheduler now uses automated browser authentication.
