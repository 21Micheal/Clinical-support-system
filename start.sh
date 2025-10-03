#!/usr/bin/env bash
# start.sh
echo "🚀 Starting Flask application on Render..."

# Run database migrations if needed
echo "📦 Running database migrations..."
python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('✅ Database tables verified')
"

# Start Gunicorn
echo "🎯 Starting Gunicorn server..."
exec gunicorn --config gunicorn.conf.py "app:app"