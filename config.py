import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # PostgreSQL configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Development settings
    DEBUG = True
    TESTING = False
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

class ChatbotConfig:
    # Path to your fine-tuned model (not used with Groq)
    MODEL_PATH = os.getenv('CHATBOT_MODEL_PATH', './fine_tuned_model')
    
    # Generation parameters
    MAX_LENGTH = 512
    TEMPERATURE = 0.7
    TOP_P = 0.9
    
    # Model configuration (Groq uses cloud GPUs, not local)
    USE_GPU = False  # Always False for API-based models
    PRECISION = 'float32'  # Not needed for Groq API