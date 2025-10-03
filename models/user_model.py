from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import psycopg2
import os
from extensions import db
from datetime import datetime
#from models import Users  # Import your Users model

from dotenv import load_dotenv

bcrypt = Bcrypt()
from psycopg2 import OperationalError

# Load environment variables once at module level
load_dotenv()

# PostgreSQL connection configuration
def get_postgres_connection():
    try:
        connection = psycopg2.connect(
            host=os.environ.get('PG_HOST', 'localhost'),
            user=os.environ.get('PG_USER', 'postgres'),
            password=os.environ.get('PG_PASSWORD', ''),
            database=os.environ.get('PG_DATABASE', 'health_care'),
            port=os.environ.get('PG_PORT', '5432')
        )
        print("✅ PostgreSQL connection established successfully!")
        return connection
    except OperationalError as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        print(f"   Host: {os.environ.get('PG_HOST')}")
        print(f"   User: {os.environ.get('PG_USER')}")
        print(f"   Database: {os.environ.get('PG_DATABASE')}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

# Initialize database connection (for raw SQL operations)
def get_db_connection():
    return get_postgres_connection()

# Test function to verify connection
def test_connection():
    conn = get_postgres_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()
                print(f"✅ PostgreSQL Version: {version[0]}")
            return True
        except Exception as e:
            print(f"❌ Error executing query: {e}")
            return False
        finally:
            conn.close()
    return False



# PostgreSQL Models
class Demographics(db.Model):
    __tablename__ = 'demographics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    location = db.Column(db.String(50), nullable=False)



bcrypt = Bcrypt()

# Single User class for both authentication and demographics
class User(db.Model):
    __tablename__ = 'users'
    
    # Authentication fields
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    
    # Demographic fields (nullable for when users first register)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    region = db.Column(db.String(100), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    actions = db.relationship('UserActions', backref='user', lazy=True, cascade="all, delete-orphan")
    predictions = db.relationship('Predictions', backref='user', lazy=True)

class UserActions(db.Model):
    __tablename__ = 'user_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Now points to users.id
    disease = db.Column(db.String(100), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    hospital = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Predictions(db.Model):
    __tablename__ = 'predictions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Now points to users.id
    predicted_disease = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(50), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class OutbreakAlert(db.Model):
    """Store outbreak predictions and alerts"""
    __tablename__ = 'outbreak_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    disease = db.Column(db.String(100), nullable=False, index=True)
    location = db.Column(db.String(100), nullable=False, index=True)
    risk_level = db.Column(db.String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    predicted_cases = db.Column(db.Integer, nullable=False)
    confidence = db.Column(db.String(20), nullable=False)  # LOW, MEDIUM, HIGH
    prediction_data = db.Column(db.Text, nullable=True)  # JSON string with full prediction
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Optional: Link to actions taken
    action_taken = db.Column(db.Boolean, default=False)
    action_notes = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<OutbreakAlert {self.disease} in {self.location}: {self.risk_level}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'disease': self.disease,
            'location': self.location,
            'risk_level': self.risk_level,
            'predicted_cases': self.predicted_cases,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'action_taken': self.action_taken
        }


class OutbreakNotification(db.Model):
    """Track notifications sent for outbreaks"""
    __tablename__ = 'outbreak_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.Integer, db.ForeignKey('outbreak_alerts.id'), nullable=False)
    recipient_type = db.Column(db.String(50), nullable=False)  # email, sms, push, dashboard
    recipient = db.Column(db.String(255), nullable=False)  # email address, phone number, user_id
    message = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    delivered = db.Column(db.Boolean, default=False)
    read = db.Column(db.Boolean, default=False)
    
    # Relationship
    alert = db.relationship('OutbreakAlert', backref='notifications')
    
    def __repr__(self):
        return f'<OutbreakNotification to {self.recipient} at {self.sent_at}>'


class ModelTrainingLog(db.Model):
    """Track ML model training history"""
    __tablename__ = 'model_training_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    disease = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    training_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    data_points = db.Column(db.Integer, nullable=False)  # Number of data points used
    accuracy_score = db.Column(db.Float, nullable=True)  # Model accuracy if available
    status = db.Column(db.String(20), nullable=False)  # success, failed
    error_message = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<ModelTraining {self.disease}-{self.location} on {self.training_date}>'


# New database model for storing follow-up responses
# class FollowUpResponses(db.Model):
#     __tablename__ = 'followup_responses'
    
#     id = db.Column(db.Integer, primary_key=True)
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
#     prediction_id = db.Column(db.Integer, db.ForeignKey('predictions.id'), nullable=False)
#     question = db.Column(db.String(500), nullable=False)
#     answer = db.Column(db.String(500), nullable=False)
#     category = db.Column(db.String(100))
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
#     user = db.relationship('User', backref='followup_responses')
#     prediction = db.relationship('Predictions', backref='followup_responses')


# Debug function to check environment
def debug_environment():
    print("🔍 Environment variables:")
    print(f"   PG_HOST: {os.environ.get('PG_HOST')}")
    print(f"   PG_USER: {os.environ.get('PG_USER')}")
    print(f"   PG_DATABASE: {os.environ.get('PG_DATABASE')}")
    print(f"   PG_PORT: {os.environ.get('PG_PORT')}")
    print(f"   PG_PASSWORD: {'***SET***' if os.environ.get('PG_PASSWORD') else '❌ NOT SET'}")

# Run debug on import
# debug_environment()
# test_connection()