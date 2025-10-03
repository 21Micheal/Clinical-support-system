#!/usr/bin/env bash
echo "🚀 Starting application..."
exec gunicorn --bind=0.0.0.0:10000 --workers=2 --timeout=120 "app:app"
