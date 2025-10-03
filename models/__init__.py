# This file makes the models directory a Python package
from .user_model import db, User, Demographics, Predictions, OutbreakAlert

__all__ = ['db', 'User', 'Demographics', 'Predictions', 'OutbreakAlert']