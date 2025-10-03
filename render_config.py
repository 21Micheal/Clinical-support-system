import os
from urllib.parse import urlparse

class RenderConfig:
    # Parse DATABASE_URL from Render
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url:
        # Fix postgres:// to postgresql:// if needed
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        SQLALCHEMY_DATABASE_URI = database_url
        
        # Parse for raw psycopg2 connections if needed
        url = urlparse(database_url)
        os.environ['PG_HOST'] = url.hostname or 'localhost'
        os.environ['PG_USER'] = url.username or 'postgres'
        os.environ['PG_PASSWORD'] = url.password or ''
        os.environ['PG_DATABASE'] = url.path[1:] if url.path else 'health_care'
        os.environ['PG_PORT'] = str(url.port or 5432)
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///local.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')
 
    # Additional production settings
    DEBUG = False
    TESTING = False
    
    # Security settings for production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Scheduler settings
    SCHEDULER_API_ENABLED = False  # Disable APScheduler REST API for security