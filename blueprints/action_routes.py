from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.user_model import UserActions, Predictions, Demographics
from extensions import db
import logging
from sqlalchemy.exc import IntegrityError, OperationalError

bp = Blueprint('action', __name__)  # Create a blueprint for actions and predictions

@bp.route('/log_action/<disease>', methods=['GET', 'POST'])
def log_action(disease):
    if 'user_id' not in session:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('auth.login'))

    return render_template('log_action.html', disease=disease)


logger = logging.getLogger(__name__) # Create a logger

@bp.route('/save_action/<disease>', methods=['POST'])
def save_action(disease):
    if 'user_id' not in session:
        flash("You need to be logged in to log actions.", "warning")
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    action = request.form.get('action')
    hospital = request.form.get('hospital')
    notes = request.form.get('notes', '')

    if not action:
        flash("Please select an action before saving.", "danger")
        return redirect(url_for('action.log_action', disease=disease))

    try:
        user_action = UserActions(user_id=user_id, disease=disease, action=action, hospital=hospital, notes=notes)
        db.session.add(user_action)
        db.session.commit()
        logger.info(f"Action logged successfully: User ID={user_id}, Disease={disease}, Action={action}, Notes={notes}")
        flash("Your action has been logged successfully!", "success")
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"IntegrityError while saving action: {e}")
        flash("There was a database error saving your action.  Please try again later.", "danger")
    except OperationalError as e:
        db.session.rollback()
        logger.error(f"OperationalError while saving action: {e}")
        flash("There was a database connection error. Please try again later.", "danger")
    except Exception as e:
        db.session.rollback()
        logger.exception(f"An unexpected error occurred: {e}") # Log the full traceback
        flash("An unexpected error occurred. Please try again later.", "danger")


    return redirect(url_for('action.log_action', disease=disease))