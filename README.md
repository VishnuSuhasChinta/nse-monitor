# NSE Monitor

A service that monitors NSE (National Stock Exchange of India) corporate announcements and sends real-time Telegram notifications.

## Features

- **Announcement Monitoring**: Polls NSE announcements API for configured companies
- **Telegram Notifications**: Sends real-time alerts to multiple users via Telegram
- **Deduplication**: Tracks seen announcements to avoid duplicate notifications
- **Notification Throttling**: Rate-limits notifications per user to prevent spam
- **Health Checks**: Exposes HTTP health endpoint for monitoring service status
- **Resilient Polling**: Exponential backoff, circuit breaker, and automatic retries
- **Multi-User Support**: Configure notifications for multiple Telegram chat IDs

## Quick Start

### Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment** (copy `.env.example` to `.env`):
   ```bash
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_IDS=123456,789012  # comma-separated list
   ```

3. **Run the service**:
   ```bash
   python -m nse_monitor.main
   ```

### Configuration

Edit `config/config.yaml` to customize:
- **companies**: List of NSE symbols to monitor
- **poll_interval_seconds**: How often to check for announcements (default: 30s)
- **notification.max_per_minute**: Throttle limit per user (default: 20)
- **http**: Retry behavior, timeouts, backoff strategy

### Systemd Service (Linux)

Install as a systemd service:
```bash
sudo cp systemd/nse-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nse-monitor
sudo systemctl start nse-monitor
```

## Architecture

- **NSEClient**: Fetches announcements from NSE API with resilience features
- **Database**: SQLite-backed deduplication and user tracking
- **NotificationThrottle**: Batches and rate-limits Telegram messages
- **Scheduler**: Periodic polling with configurable intervals and jitter
- **Health Server**: HTTP endpoint for liveness checks

## Testing

Run tests with pytest:
```bash
pytest tests/
```

## Logs

Logs are written to `logs/monitor.log` with rotation. Monitor service health:
```bash
curl http://127.0.0.1:8787/health
```
