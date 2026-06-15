# Deployment Guide

## Local deployment

1. Install Python 3.11 or newer.
2. Run `python -m pip install -r requirements.txt`.
3. Optionally run `python -m flask --app backend.app seed`.
4. Start with `python run.py`.

## Render or Railway

- Runtime: Python 3
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn backend.app:app`
- Environment variable: `TRACKER_DB=/var/data/equipment_tracker.db` when a persistent disk is attached
- Environment variable: `SECRET_KEY=<long-random-production-secret>`

For production, add `gunicorn` to `requirements.txt` and attach persistent storage. SQLite is suitable for the prototype; migrate to PostgreSQL for multiple concurrent workers or larger workloads.

## Validation checklist

- `/api/health` returns HTTP 200.
- Create, list, inspect, detail, dashboard, and CSV endpoints work.
- The database path is writable and persistent.
- Mobile and desktop layouts render correctly.
- Error responses do not expose stack traces.
- User and admin login sessions work over HTTPS.
