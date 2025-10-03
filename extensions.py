from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Create a single SQLAlchemy instance
db = SQLAlchemy()
migrate = Migrate()
