# setup_database.py
import os
from flask import Flask
from models.user_model import db

def setup_database():
    """Set up database without circular imports"""
    app = Flask(__name__)
    
    # Database configuration
    database_url = os.environ.get('DATABASE_URL', '')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize db
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        print('✅ Database tables verified')

if __name__ == '__main__':
    setup_database()