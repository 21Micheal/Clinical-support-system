#!/usr/bin/env bash
echo "🚀 Starting Flask application on Render..."

# Set up database using separate script
echo "📦 Setting up database..."
python setup_database.py

# Start Gunicorn
echo "🎯 Starting Gunicorn server..."
exec gunicorn --bind=0.0.0.0:10000 --workers=2 --threads=2 --timeout=120 "app:app"