from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify, Blueprint
from models.user_model import UserActions, User, Demographics, Predictions, OutbreakAlert, OutbreakNotification
from blueprints.auth_routes import register_user, authenticate_user, get_user_profile, update_user_demographics
from smart_recommendations import get_smart_recommendations, FollowUpResponses
from config import Config
from extensions import db, migrate
from fuzzywuzzy import process
from datetime import datetime
import numpy as np
import pandas as pd
import pickle
from scheduler import init_scheduler
from render_config import RenderConfig

import requests
import os
from dotenv import load_dotenv  

from flask_migrate import Migrate

load_dotenv() 

dashboard_bp = Blueprint('dashboard', __name__)

def create_app():
    app = Flask(__name__)
    
    # Use Render config if DATABASE_URL is present (indicating production)
    if os.environ.get('DATABASE_URL'):
        app.config.from_object(RenderConfig)
        print("✅ Using Render production configuration")
    else:
        # Your existing development config
        app.config.from_object(Config)
        print("✅ Using development configuration")
    
    # Initialize database
    db.init_app(app)
    migrate = Migrate(app, db)

    # Only run scheduler in production or main process
    # This prevents duplicate schedulers in debug/reload mode
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        try:
            from scheduler import init_scheduler
            scheduler = init_scheduler(app)
            print("✅ Outbreak prediction scheduler started")
        except ImportError as e:
            print(f"⚠️ Scheduler import failed: {e}")
        except Exception as e:
            print(f"⚠️ Scheduler initialization failed: {e}")

    # Register blueprints
    from blueprints.auth_routes import bp as auth_bp
    from blueprints.action_routes import bp as action_bp
    from blueprints.chatbot_routes import chatbot_bp
    from blueprints.admin_routes import admin_bp
    from blueprints.outbreak_routes import outbreak_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(action_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(outbreak_bp)

    # Create tables within app context
    with app.app_context():
        db.create_all()
        print("✅ Database tables created/verified")

    return app
# app = create_app()

# Health check endpoint for Render
@dashboard_bp.route('/health')
def health_check():
    """Health check endpoint for Render monitoring"""
    try:
        from models.user_model import db
        # Test database connection
        db.session.execute('SELECT 1')
        return {
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        }, 200
    except Exception as e:
        return {
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }, 500

# CLI commands for manual scheduler control (optional)
@dashboard_bp.cli.command('predict-outbreaks')
def predict_outbreaks_command():
    """Run outbreak predictions manually"""
    try:
        from scheduler import trigger_predictions_now
        with app.app_context():
            trigger_predictions_now(app)
        print("✅ Outbreak predictions completed manually")
    except Exception as e:
        print(f"❌ Manual prediction failed: {e}")

@dashboard_bp.cli.command('retrain-models')
def retrain_models_command():
    """Retrain prediction models manually"""
    try:
        from scheduler import trigger_retraining_now
        with app.app_context():
            trigger_retraining_now(app)
        print("✅ Model retraining completed manually")
    except Exception as e:
        print(f"❌ Manual retraining failed: {e}")

    # Middleware
    @app.before_request
    def block_unwanted_requests():
        unwanted_paths = ['/hybridaction/zybTrackerStatisticsAction']
        if request.path in unwanted_paths:
            abort(404)

    @app.after_request
    def set_csp(response):
        response.headers['Content-Security-Policy'] = (
            "default-src * data: blob:; "  # Allow all sources (only use this if needed)
            "style-src * 'unsafe-inline'; "  # Allow all styles including TailwindCDN
            "script-src * 'unsafe-inline' 'unsafe-eval'; "  # Allow scripts from any source
            "img-src * data:; "  # Allow images from any source
            "connect-src *; "  # Allow API connections
            "font-src * data:; "  # Allow fonts from any source
        )
        return response

    return app


# LOAD MODEL AND DATASETS

# Load datasets
sym_des = pd.read_csv("dataset2/updated_symptoms.csv")
precautions = pd.read_csv("dataset2/updated_precautions.csv")
workout = pd.read_csv("dataset2/updated_workout.csv")
description = pd.read_csv("dataset2/updated_description.csv")
medications = pd.read_csv("dataset2/updated_medications.csv")
diets = pd.read_csv("dataset2/updated_diets.csv")


MODEL_PATH = "models/random_forest_model.pkl"
ENCODER_PATH = "models/label_encoder.pkl"

import joblib

# Load Random Forest model and encoder
try:
    model = joblib.load(MODEL_PATH)
    encoder = joblib.load(ENCODER_PATH)
    print("✅ Model and encoder loaded successfully!")
except FileNotFoundError as e:
    print(f"🚨 Error loading model or encoder: {e}")




# Load the prediction model
# svc = pickle.load(open('models/svc1.pkl', 'rb'))

# Helper function for disease data
def helper(disease):
    desc = description[description['Disease'] == disease]['Description'].values
    desc = " ".join([w for w in desc])

    pre = precautions[precautions['Disease'] == disease][['Precaution_1', 'Precaution_2', 'Precaution_3', 'Precaution_4']].values
    med = medications[medications['Disease'] == disease]['Medication'].values
    die = diets[diets['Disease'] == disease]['Diet'].values
    wrkout = workout[workout['disease'] == disease]['workout'].values

    return desc, pre, med, die, wrkout


# Prediction Function
def get_predicted_value(symptoms):
    input_vector = np.zeros(len(symptoms_dict))
    for symptom in symptoms:
        if symptom in symptoms_dict:
            input_vector[symptoms_dict[symptom]] = 1

    # Convert to DataFrame with feature names
    input_df = pd.DataFrame([input_vector], columns=list(symptoms_dict.keys()))
    return diseases_list[model.predict(input_df)[0]]


# SYMPTOM AND DISEASE DATA

symptoms_dict = {'itching': 0, 'skin_rash': 1, 'nodal_skin_eruptions': 2, 'continuous_sneezing': 3, 'shivering': 4, 'chills': 5, 'joint_pain': 6, 'stomach_pain': 7, 'acidity': 8, 'ulcers_on_tongue': 9, 'muscle_wasting': 10, 'vomiting': 11, 'burning_micturition': 12, 'spotting_ urination': 13, 'fatigue': 14, 'weight_gain': 15, 'anxiety': 16, 'cold_hands_and_feets': 17, 'mood_swings': 18, 'weight_loss': 19, 'restlessness': 20, 'lethargy': 21, 'patches_in_throat': 22, 'irregular_sugar_level': 23, 'cough': 24, 'high_fever': 25, 'sunken_eyes': 26, 'breathlessness': 27, 'sweating': 28, 'dehydration': 29, 'indigestion': 30, 'headache': 31, 'yellowish_skin': 32, 'dark_urine': 33, 'nausea': 34, 'loss_of_appetite': 35, 'pain_behind_the_eyes': 36, 'back_pain': 37, 'constipation': 38, 'abdominal_pain': 39, 'diarrhoea': 40, 'mild_fever': 41, 'yellow_urine': 42, 'yellowing_of_eyes': 43, 'acute_liver_failure': 44, 'fluid_overload': 45, 'swelling_of_stomach': 46, 'swelled_lymph_nodes': 47, 'malaise': 48, 'blurred_and_distorted_vision': 49, 'phlegm': 50, 'throat_irritation': 51, 'redness_of_eyes': 52, 'sinus_pressure': 53, 'runny_nose': 54, 'congestion': 55, 'chest_pain': 56, 'weakness_in_limbs': 57, 'fast_heart_rate': 58, 'pain_during_bowel_movements': 59, 'pain_in_anal_region': 60, 'bloody_stool': 61, 'irritation_in_anus': 62, 'neck_pain': 63, 'dizziness': 64, 'cramps': 65, 'bruising': 66, 'obesity': 67, 'swollen_legs': 68, 'swollen_blood_vessels': 69, 'puffy_face_and_eyes': 70, 'enlarged_thyroid': 71, 'brittle_nails': 72, 'swollen_extremeties': 73, 'excessive_hunger': 74, 'extra_marital_contacts': 75, 'drying_and_tingling_lips': 76, 'slurred_speech': 77, 'knee_pain': 78, 'hip_joint_pain': 79, 'muscle_weakness': 80, 'stiff_neck': 81, 'swelling_joints': 82, 'movement_stiffness': 83, 'spinning_movements': 84, 'loss_of_balance': 85, 'unsteadiness': 86, 'weakness_of_one_body_side': 87, 'loss_of_smell': 88, 'bladder_discomfort': 89, 'foul_smell_of urine': 90, 'continuous_feel_of_urine': 91, 'passage_of_gases': 92, 'internal_itching': 93, 'toxic_look_(typhos)': 94, 'depression': 95, 'irritability': 96, 'muscle_pain': 97, 'altered_sensorium': 98, 'red_spots_over_body': 99, 'belly_pain': 100, 'abnormal_menstruation': 101, 'dischromic _patches': 102, 'watering_from_eyes': 103, 'increased_appetite': 104, 'polyuria': 105, 'family_history': 106, 'mucoid_sputum': 107, 'rusty_sputum': 108, 'lack_of_concentration': 109, 'visual_disturbances': 110, 'receiving_blood_transfusion': 111, 'receiving_unsterile_injections': 112, 'coma': 113, 'stomach_bleeding': 114, 'distention_of_abdomen': 115, 'history_of_alcohol_consumption': 116, 'fluid_overload.1': 117, 'blood_in_sputum': 118, 'prominent_veins_on_calf': 119, 'palpitations': 120, 'painful_walking': 121, 'pus_filled_pimples': 122, 'blackheads': 123, 'scurring': 124, 'skin_peeling': 125, 'silver_like_dusting': 126, 'small_dents_in_nails': 127, 'inflammatory_nails': 128, 'blister': 129, 'red_sore_around_nose': 130, 'yellow_crust_ooze': 131}
diseases_list = {15: 'Fungal infection', 4: 'Allergy', 16: 'GERD', 9: 'Chronic cholestasis', 14: 'Drug Reaction', 33: 'Peptic ulcer diseae', 1: 'AIDS', 12: 'Diabetes ', 17: 'Gastroenteritis', 6: 'Bronchial Asthma', 23: 'Hypertension ', 30: 'Migraine', 7: 'Cervical spondylosis', 32: 'Paralysis (brain hemorrhage)', 28: 'Jaundice', 29: 'Malaria', 8: 'Chicken pox', 11: 'Dengue', 37: 'Typhoid', 40: 'hepatitis A', 19: 'Hepatitis B', 20: 'Hepatitis C', 21: 'Hepatitis D', 22: 'Hepatitis E', 3: 'Alcoholic hepatitis', 36: 'Tuberculosis', 10: 'Common Cold', 34: 'Pneumonia', 13: 'Dimorphic hemmorhoids(piles)', 18: 'Heart attack', 39: 'Varicose veins', 26: 'Hypothyroidism', 24: 'Hyperthyroidism', 25: 'Hypoglycemia', 31: 'Osteoarthristis', 5: 'Arthritis', 0: '(vertigo) Paroymsal  Positional Vertigo', 2: 'Acne', 38: 'Urinary tract infection', 35: 'Psoriasis', 27: 'Impetigo'}



# ===================================
# Helper Functions for Models
# ===================================

def get_recent_alerts(days=7, risk_levels=None):
    """
    Get recent outbreak alerts
    
    Args:
        days: Number of days to look back
        risk_levels: List of risk levels to filter (e.g., ['HIGH', 'CRITICAL'])
    
    Returns:
        List of OutbreakAlert objects
    """
    from datetime import timedelta
    
    start_date = datetime.utcnow() - timedelta(days=days)
    query = OutbreakAlert.query.filter(OutbreakAlert.timestamp >= start_date)
    
    if risk_levels:
        query = query.filter(OutbreakAlert.risk_level.in_(risk_levels))
    
    return query.order_by(OutbreakAlert.timestamp.desc()).all()


def get_alerts_by_location(location, limit=10):
    """Get alerts for a specific location"""
    return OutbreakAlert.query.filter_by(
        location=location
    ).order_by(OutbreakAlert.timestamp.desc()).limit(limit).all()


def get_alerts_by_disease(disease, limit=10):
    """Get alerts for a specific disease"""
    return OutbreakAlert.query.filter_by(
        disease=disease
    ).order_by(OutbreakAlert.timestamp.desc()).limit(limit).all()


def get_critical_alerts():
    """Get all critical alerts from the last 24 hours"""
    from datetime import timedelta
    
    yesterday = datetime.utcnow() - timedelta(days=1)
    return OutbreakAlert.query.filter(
        OutbreakAlert.timestamp >= yesterday,
        OutbreakAlert.risk_level == 'CRITICAL'
    ).order_by(OutbreakAlert.timestamp.desc()).all()


def mark_alert_action_taken(alert_id, notes=None):
    """Mark that action has been taken on an alert"""
    alert = OutbreakAlert.query.get(alert_id)
    if alert:
        alert.action_taken = True
        if notes:
            alert.action_notes = notes
        db.session.commit()
        return True
    return False


def get_outbreak_statistics():
    """Get overall outbreak statistics"""
    from sqlalchemy import func
    
    total_alerts = OutbreakAlert.query.count()
    
    critical_count = OutbreakAlert.query.filter_by(risk_level='CRITICAL').count()
    high_count = OutbreakAlert.query.filter_by(risk_level='HIGH').count()
    medium_count = OutbreakAlert.query.filter_by(risk_level='MEDIUM').count()
    low_count = OutbreakAlert.query.filter_by(risk_level='LOW').count()
    
    # Most affected location
    most_affected = db.session.query(
        OutbreakAlert.location,
        func.count(OutbreakAlert.id).label('alert_count')
    ).group_by(OutbreakAlert.location).order_by(
        func.count(OutbreakAlert.id).desc()
    ).first()
    
    # Most common disease
    most_common_disease = db.session.query(
        OutbreakAlert.disease,
        func.count(OutbreakAlert.id).label('alert_count')
    ).group_by(OutbreakAlert.disease).order_by(
        func.count(OutbreakAlert.id).desc()
    ).first()
    
    return {
        'total_alerts': total_alerts,
        'critical': critical_count,
        'high': high_count,
        'medium': medium_count,
        'low': low_count,
        'most_affected_location': most_affected[0] if most_affected else None,
        'most_common_disease': most_common_disease[0] if most_common_disease else None
    }




@dashboard_bp.route('/dashboard')
def dashboard():
    username = session.get('username')
    if 'user_id' not in session:
        flash("You need to log in to access the dashboard.", "warning")
        return redirect(url_for('auth.login'))

    user_id = session['user_id']
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found. Please log in again.", "danger")
        return redirect(url_for('auth.logout'))

    return render_template('index.html', user=user,  symptoms_dict=symptoms_dict, username=username)

def process_symptoms(form):
    """Process and validate symptoms input"""
    manual_symptoms = form.get('manual_symptoms', '').strip()
    selected_symptoms = form.getlist('selected_symptoms')  # ✅ Ensure checkboxes are captured

    # Ensure that only one input method is used
    if manual_symptoms and selected_symptoms:
        return {'is_valid': False, 'message': "Please provide symptoms using either manual input or selection, not both."}

    # Convert symptoms to a list
    symptoms = []
    if manual_symptoms:
        symptoms = [s.strip().lower().replace(' ', '_') for s in manual_symptoms.split(',') if s]
    elif selected_symptoms:
        symptoms = selected_symptoms  # ✅ Now capturing selected symptoms correctly

    if not symptoms:
        return {'is_valid': False, 'message': "Please provide symptoms either by typing or selecting from the list."}

    return {'is_valid': True, 'data': symptoms}



# Update your predict route to pass prediction_id to template
# This ensures the button has access to the prediction ID

# Safe version of predict route with proper error handling

@dashboard_bp.route('/predict', methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        if 'user_id' not in session:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'You must log in to make predictions.'})
            flash("You must log in to make predictions.", "danger")
            return redirect(url_for('auth.login'))

        user_id = session['user_id']
        user = User.query.filter_by(id=user_id).first()

        if not user:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Invalid user. Please log in again.'})
            flash("Invalid user. Please log in again.", "danger")
            return redirect(url_for('auth.logout'))

        # Debug the actual form data structure
        print("🔍 Raw form data:", dict(request.form))
        print("🔍 Form keys:", list(request.form.keys()))

         # Initialize prediction_id at the top
        prediction_id = None
        
        # Handle multipart form data parsing
        form_data = {}
        try:
            # If it's multipart form data, the fields might be in a different format
            if request.content_type and 'multipart/form-data' in request.content_type:
                # Extract individual fields from the multipart data
                for key in request.form:
                    # For regular fields, get the first value
                    if key not in ['selected_symptoms']:
                        form_data[key] = request.form.get(key, '').strip()
                    # For selected_symptoms, get all values
                    else:
                        form_data[key] = request.form.getlist(key)
            else:
                # Regular form data
                form_data = request.form.to_dict()
                # Handle selected_symptoms as list for regular forms too
                if 'selected_symptoms' in request.form:
                    form_data['selected_symptoms'] = request.form.getlist('selected_symptoms')
                    
        except Exception as parse_error:
            print(f"❌ Form parsing error: {parse_error}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Error parsing form data.'})
            flash("Error parsing form data.", "danger")
            return redirect(url_for('dashboard.predict'))

        print("🔍 Parsed form data:", form_data)
        
        try:
            # Extract fields from parsed form data
            gender = form_data.get('gender', '').strip()
            age = form_data.get('age', '').strip()
            area = form_data.get('area', '').strip()
            selected_symptoms = form_data.get('selected_symptoms', [])
            manual_symptoms = form_data.get('manual_symptoms', '').strip()

            print(f"✅ Extracted fields - Gender: {gender}, Age: {age}, Area: {area}")
            print(f"✅ Selected symptoms: {selected_symptoms}")
            print(f"✅ Manual symptoms: {manual_symptoms}")

            # Validate required fields
            if not all([gender, age, area]):
                error_msg = "Please fill in all required fields: gender, age, and area."
                print(f"❌ Missing fields - Gender: {gender}, Age: {age}, Area: {area}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': error_msg})
                flash(error_msg, "danger")
                return redirect(url_for('dashboard.predict'))

             # Check if we have either selected symptoms OR manual symptoms
            if not selected_symptoms and not manual_symptoms:
                error_msg = "Please select symptoms from the list or enter symptoms manually."
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': error_msg})
                flash(error_msg, "danger")
                return redirect(url_for('dashboard.predict'))

            session['area'] = area
            print("✅ Session area set:", session.get('area'))

            # ✅ Process symptoms - create a proper form-like object
            class FormData:
                def __init__(self, data):
                    self.data = data
                
                def get(self, key, default=None):
                    return self.data.get(key, default)
                
                def getlist(self, key):
                    return self.data.get(key, []) if isinstance(self.data.get(key), list) else [self.data.get(key)] if self.data.get(key) else []

            form_obj = FormData(form_data)
            symptoms_result = process_symptoms(form_obj)
            
            if not symptoms_result['is_valid']:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': symptoms_result['message']})
                flash(symptoms_result['message'], "danger")
                return redirect(url_for('dashboard.predict'))

            symptoms = symptoms_result['data']
            
            # ✅ Fix symptom counting
            if isinstance(symptoms, list):
                if symptoms and isinstance(symptoms[0], str):
                    symptoms_count = len(symptoms)
                else:
                    symptoms_count = sum(symptoms)
            else:
                symptoms_count = 5
            
            print(f"✅ Processed Symptoms: {symptoms} (Count: {symptoms_count})")

            # ✅ Predict Disease
            predicted_disease = get_predicted_value(symptoms)
            dis_des, precautions, medications, rec_diet, workout = helper(predicted_disease)

            def ensure_list(data):
                if isinstance(data, (np.ndarray, pd.Series)):
                    return data.tolist()
                elif isinstance(data, list):
                    return data
                else:
                    return [data]

            workout = ensure_list(workout)
            medications = ensure_list(medications)
            precautions = ensure_list(precautions)
            rec_diet = ensure_list(rec_diet)

            # ✅ Save Prediction
            prediction = Predictions(
                user_id=user_id,
                predicted_disease=predicted_disease,
                location=area,
                age=age,
                gender=gender
            )
            db.session.add(prediction)
            db.session.flush() 
            db.session.commit()
            
            prediction_id = prediction.id
            print(f"🎯 Diagnosis Complete: {predicted_disease} (ID: {prediction_id})")

            # ✅ SMART RECOMMENDATIONS
            smart_recommendations = None
            try:
                smart_recommendations = get_smart_recommendations(
                    user_id=user_id,
                    predicted_disease=predicted_disease,
                    symptoms_count=symptoms_count,
                    gender=gender,
                    age=age,
                    location=area
                )
                print(f"🧠 Smart Recommendations Generated")
            except Exception as rec_error:
                print(f"⚠️ Warning: Could not generate recommendations: {str(rec_error)}")

            # ✅ Outbreak Detection
            outbreak_notification = None
            THRESHOLD = 2

            try:
                user_location_cases = db.session.query(
                    db.func.count(db.distinct(Predictions.user_id))
                ).filter(
                    Predictions.predicted_disease == predicted_disease,
                    Predictions.location == area
                ).scalar()

                if user_location_cases >= THRESHOLD:
                    outbreak_notification = (
                        f"🚨 Alert: {predicted_disease} cases in {area} have reached "
                        f"{user_location_cases}. This exceeds the threshold of {THRESHOLD}. Please exercise caution."
                    )
                    print(f"🚨 Outbreak Notification: {outbreak_notification}")
                else:
                    print(f"No outbreak: {user_location_cases} < {THRESHOLD}")
            except Exception as outbreak_error:
                print(f"⚠️ Warning: Could not check outbreak: {str(outbreak_error)}")

            # ✅ Handle AJAX vs regular requests
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            if is_ajax:
                response_data = {
                    'success': True,
                    'predicted_disease': predicted_disease,
                    'dis_des': dis_des,
                    'precautions': precautions,
                    'medications': medications,
                    'rec_diet': rec_diet,
                    'workout': workout,
                    'outbreak_notification': outbreak_notification,
                    'prediction_id': prediction_id
                }
                
                if smart_recommendations:
                    response_data['smart_recommendations'] = smart_recommendations
                    
                return jsonify(response_data)
            
            # ✅ Regular form submission
            if outbreak_notification:
                flash(outbreak_notification, 'warning')
                
            return render_template('index.html', 
                                symptoms_dict=symptoms_dict,
                                predicted_disease=predicted_disease,
                                dis_des=dis_des,
                                my_precautions=precautions,
                                medications=medications,
                                my_diet=rec_diet,
                                workout=workout,
                                prediction_id=prediction_id,
                                smart_recommendations=smart_recommendations,
                                outbreak_notification=outbreak_notification)

        except Exception as e:
            print(f"❌ Error in predict route: {str(e)}")
            import traceback
            traceback.print_exc()
            
            db.session.rollback()
            
            error_message = f'Error processing diagnosis: {str(e)}'
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': error_message})
            else:
                flash(error_message, "danger")
                return redirect(url_for('dashboard.predict'))

    # GET request — show form
    return render_template('index.html', 
                        symptoms_dict=symptoms_dict,
                        predicted_disease=None, 
                        dis_des="Description not available",
                        my_precautions=["Precaution not available"], 
                        medications=["Medication not available"],
                        my_diet=["Diet not available"], 
                        workout=["Workout not available"],
                        prediction_id=None) 



# Add this route to your dashboard routes (routes.py or wherever your routes are)

@dashboard_bp.route('/view_recommendations/<int:prediction_id>')
def view_recommendations(prediction_id):
    """Display smart recommendations for a specific prediction"""
    if 'user_id' not in session:
        flash("You must log in to view recommendations.", "danger")
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    
    # Get the prediction
    prediction = Predictions.query.filter_by(
        id=prediction_id,
        user_id=user_id  # Ensure user can only view their own predictions
    ).first_or_404()
    
    # Count symptoms (if you have a symptoms field, otherwise estimate)
    # If you don't store symptoms, you can use a default or estimate
    # For now, let's estimate based on severity - you may need to adjust this
    symptoms_count = 5  # Default, or calculate from stored data
    
    # Generate smart recommendations
    try:
        smart_recommendations = get_smart_recommendations(
            user_id=user_id,
            predicted_disease=prediction.predicted_disease,
            symptoms_count=symptoms_count,
            gender=prediction.gender,
            age=prediction.age,
            location=prediction.location
        )
    except Exception as e:
        app.logger.error(f"Error generating recommendations: {str(e)}")
        flash("Error generating recommendations. Please try again.", "danger")
        return redirect(url_for('dashboard.index'))
    
    # Get user info for display
    user = User.query.get(user_id)
    
    return render_template(
        'recommendations.html',
        prediction=prediction,
        recommendations=smart_recommendations,
        user=user
    )



@dashboard_bp.route('/save_followup', methods=['POST'])
def save_followup():
    """
    Save user responses to follow-up questions
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'})
    
    try:
        data = request.get_json()
        user_id = session['user_id']
        prediction_id = data.get('prediction_id')
        responses = data.get('responses', [])
        
        if not prediction_id or not responses:
            return jsonify({'success': False, 'message': 'Missing required data'})
        
        # Save each response
        saved_count = 0
        for response in responses:
            followup = FollowUpResponses(
                user_id=user_id,
                prediction_id=prediction_id,
                question=response.get('question'),
                answer=response.get('answer'),
                category=response.get('category')
            )
            db.session.add(followup)
            saved_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Saved {saved_count} follow-up responses',
            'saved_count': saved_count
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error saving follow-up responses: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})


@dashboard_bp.route('/get_followup_history/<int:prediction_id>')
def get_followup_history(prediction_id):
    """
    Retrieve follow-up responses for a specific prediction
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'})
    
    try:
        user_id = session['user_id']
        
        responses = FollowUpResponses.query.filter_by(
            user_id=user_id,
            prediction_id=prediction_id
        ).all()
        
        response_data = [{
            'question': r.question,
            'answer': r.answer,
            'category': r.category,
            'created_at': r.created_at.isoformat()
        } for r in responses]
        
        return jsonify({
            'success': True,
            'responses': response_data
        })
        
    except Exception as e:
        print(f"❌ Error retrieving follow-up history: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})


@dashboard_bp.route('/user_health_profile')
def user_health_profile():
    """
    Show comprehensive health profile with recommendations history
    """
    if 'user_id' not in session:
        flash("You must log in to view your health profile.", "danger")
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    
    # Get user's prediction history
    predictions = Predictions.query.filter_by(user_id=user_id).order_by(
        Predictions.created_at.desc()
    ).limit(10).all()
    
    # Get user's follow-up response history
    followup_stats = db.session.query(
        FollowUpResponses.category,
        db.func.count(FollowUpResponses.id).label('count')
    ).filter(
        FollowUpResponses.user_id == user_id
    ).group_by(FollowUpResponses.category).all()
    
    # Calculate health engagement score
    total_predictions = len(predictions)
    total_followups = sum([stat[1] for stat in followup_stats])
    engagement_score = min(100, (total_followups / max(total_predictions, 1)) * 100)
    
    # Get recurring conditions
    recurring_conditions = db.session.query(
        Predictions.predicted_disease,
        db.func.count(Predictions.id).label('count')
    ).filter(
        Predictions.user_id == user_id
    ).group_by(Predictions.predicted_disease).having(
        db.func.count(Predictions.id) >= 2
    ).all()
    
    return render_template('health_profile.html',
                         predictions=predictions,
                         followup_stats=followup_stats,
                         engagement_score=round(engagement_score, 1),
                         recurring_conditions=recurring_conditions)


@dashboard_bp.route('/recommendation_feedback', methods=['POST'])
def recommendation_feedback():
    """
    Collect user feedback on recommendations usefulness
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'})
    
    try:
        data = request.get_json()
        prediction_id = data.get('prediction_id')
        feedback_type = data.get('feedback_type')  # 'helpful', 'not_helpful', 'followed'
        comments = data.get('comments', '')
        
        # You can create a new model for this or extend existing UserActions model
        # For now, we'll log it
        print(f"📊 Recommendation Feedback: User {session['user_id']}, "
              f"Prediction {prediction_id}, Type: {feedback_type}, Comments: {comments}")
        
        return jsonify({
            'success': True,
            'message': 'Thank you for your feedback!'
        })
        
    except Exception as e:
        print(f"❌ Error saving feedback: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})




@dashboard_bp.route('/emergency_resources')
def emergency_resources():
    """
    Display emergency contacts and resources based on user location
    """
    user_location = session.get('area', 'Unknown')
    
    # You can expand this with a database of local emergency contacts
    emergency_contacts = {
        'general': {
            'emergency': '999',  # Adjust for your country
            'ambulance': '999',
            'poison_control': '...',
        },
        'hospitals': [
            # Populate with local hospitals based on location
        ],
        'pharmacies': [
            # Populate with 24/7 pharmacies
        ]
    }
    
    return render_template('emergency_resources.html',
                         location=user_location,
                         contacts=emergency_contacts)


@dashboard_bp.route('/disease_stats/<disease>')
def disease_stats(disease):
    app.logger.debug(f"Accessing disease stats for: {disease}")

    user_location = session.get('area', 'kisii')
    app.logger.debug(f"User location from session: {user_location}")

    # ✅ Overall Gender Stats - ONLY for this specific disease
    gender_stats_query = db.session.query(
        Predictions.gender,
        db.func.count(Predictions.id).label('cases')  # Count prediction records, not distinct users
    ).filter(
        Predictions.predicted_disease == disease
    ).group_by(Predictions.gender).all()

    gender_stats = [{"gender": row[0], "cases": row[1]} for row in gender_stats_query]
    app.logger.debug(f"✅ Gender stats for {disease}: {gender_stats}")

    # ✅ Overall Age Group Stats - ONLY for this specific disease
    age_group_stats_query = db.session.query(
        db.case(
            (Predictions.age < 18, '0-17'),
            (Predictions.age.between(18, 35), '18-35'),
            (Predictions.age.between(36, 55), '36-55'),
            (Predictions.age > 55, '55+')
        ).label('age_group'),
        db.func.count(Predictions.id).label('cases')  # Count prediction records
    ).filter(
        Predictions.predicted_disease == disease
    ).group_by('age_group').all()

    age_group_stats = [{"age_group": row[0], "cases": row[1]} for row in age_group_stats_query]
    app.logger.debug(f"✅ Age group stats for {disease}: {age_group_stats}")

    # ✅ Gender per location - ONLY for this specific disease
    location_gender_stats_query = db.session.query(
        Predictions.location,
        Predictions.gender,
        db.func.count(Predictions.id).label('cases')
    ).filter(
        Predictions.predicted_disease == disease
    ).group_by(Predictions.location, Predictions.gender).all()

    # ✅ Age Group per location - ONLY for this specific disease
    location_age_group_stats_query = db.session.query(
        Predictions.location,
        db.case(
            (Predictions.age < 18, '0-17'),
            (Predictions.age.between(18, 35), '18-35'),
            (Predictions.age.between(36, 55), '36-55'),
            (Predictions.age > 55, '55+')
        ).label('age_group'),
        db.func.count(Predictions.id).label('cases')
    ).filter(
        Predictions.predicted_disease == disease
    ).group_by(Predictions.location, 'age_group').all()

    # ✅ Other diseases in the SAME regions where this disease exists
    # First, get all locations where this disease is present
    disease_locations = db.session.query(
        Predictions.location
    ).filter(
        Predictions.predicted_disease == disease
    ).distinct().all()
    
    disease_location_list = [loc[0] for loc in disease_locations]

    # Then get other diseases ONLY in those locations
    location_disease_breakdown_query = db.session.query(
        Predictions.location,
        Predictions.predicted_disease,
        db.func.count(Predictions.id).label('cases')
    ).filter(
        Predictions.predicted_disease != disease,
        Predictions.location.in_(disease_location_list)
    ).group_by(Predictions.location, Predictions.predicted_disease).all()

    # Organize location-specific data
    location_gender_stats = {}
    location_age_group_stats = {}
    location_disease_stats = {}

    for location, gender, cases in location_gender_stats_query:
        location_gender_stats.setdefault(location, []).append({"gender": gender, "cases": cases})
        app.logger.debug(f"  📍 {location} - Gender: {gender} = {cases} cases")

    for location, age_group, cases in location_age_group_stats_query:
        location_age_group_stats.setdefault(location, []).append({"age_group": age_group, "cases": cases})
        app.logger.debug(f"  📍 {location} - Age Group: {age_group} = {cases} cases")

    for location, disease_name, cases in location_disease_breakdown_query:
        location_disease_stats.setdefault(location, []).append({"name": disease_name, "cases": cases})

    # ✅ Verify totals match
    for location in location_gender_stats.keys():
        total_gender_cases = sum(stat['cases'] for stat in location_gender_stats.get(location, []))
        total_age_cases = sum(stat['cases'] for stat in location_age_group_stats.get(location, []))
        app.logger.debug(f"  🔍 {location} totals - Gender: {total_gender_cases}, Age: {total_age_cases}")

    # ✅ Summary Message
    most_affected_gender = max(gender_stats, key=lambda x: x["cases"], default=None) if gender_stats else None
    max_cases = max([g["cases"] for g in age_group_stats], default=0) if age_group_stats else 0
    most_affected_age_groups = [a["age_group"] for a in age_group_stats if a["cases"] == max_cases] if age_group_stats else []

    message = None
    if most_affected_gender and most_affected_age_groups:
        age_group_text = " & ".join(most_affected_age_groups)
        message = (
            f"For {disease}, the most affected gender is {most_affected_gender['gender']} "
            f"and the most affected age group(s) are {age_group_text}."
        )

    # ✅ Location stats for Map - ONLY for this specific disease
    location_stats = db.session.query(
        Predictions.location,
        db.func.count(Predictions.id).label('cases')
    ).filter(
        Predictions.predicted_disease == disease
    ).group_by(Predictions.location).all()

    disease_data = {
        stat.location: {
            "cases": stat.cases,
            "coordinates": get_coordinates(stat.location),
            "gender_stats": location_gender_stats.get(stat.location, []),
            "age_group_stats": location_age_group_stats.get(stat.location, []),
            "diseases": location_disease_stats.get(stat.location, [])
        }
        for stat in location_stats
    }

    # ✅ Final verification - total cases should match
    total_cases = sum(stat.cases for stat in location_stats)
    total_gender_cases = sum(g['cases'] for g in gender_stats)
    total_age_cases = sum(a['cases'] for a in age_group_stats)
    
    app.logger.debug(f"📊 FINAL TOTALS for {disease}:")
    app.logger.debug(f"  Total cases: {total_cases}")
    app.logger.debug(f"  Total gender cases: {total_gender_cases}")
    app.logger.debug(f"  Total age cases: {total_age_cases}")
    
    if total_cases != total_gender_cases or total_cases != total_age_cases:
        app.logger.warning(f"⚠️ MISMATCH DETECTED! Cases: {total_cases}, Gender: {total_gender_cases}, Age: {total_age_cases}")

    app.logger.debug(f"Final disease_data: {disease_data}")

    return render_template(
        'disease_stats.html',
        disease=disease,
        gender_stats=gender_stats,
        age_group_stats=age_group_stats,
        disease_data=disease_data,
        message=message
    )

@dashboard_bp.route('/log_action/<disease>', methods=['GET', 'POST'])
def log_action(disease):
    if 'user_id' not in session:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)  # Now using the single User model
    
    if not user:
        flash("User not found. Please log in again.", "danger")
        return redirect(url_for('auth.logout'))

    username = user.username
    session['username'] = username

    return render_template('log_action.html', disease=disease, username=username)


@dashboard_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        flash("Please log in to access your profile.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = User.query.get(user_id)
    
    if not user:
        flash("User not found. Please log in again.", "danger")
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        age = request.form.get('age')
        gender = request.form.get('gender')
        location = request.form.get('location')
        region = request.form.get('region')
        
        # Convert age to int if provided
        age = int(age) if age else None
        
        if update_user_demographics(user_id, age, gender, location, region):
            flash("Profile updated successfully!", "success")
        else:
            flash("Error updating profile. Please try again.", "danger")
        
        return redirect(url_for('dashboard.profile'))

    return render_template('profile.html', user=user)



# EHR endroute
@dashboard_bp.route('/health_records')
def health_records():
    if 'user_id' not in session:
        flash('You need to log in to view your health records.', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    health_records = UserActions.query.filter_by(user_id=user_id).all()

    return render_template('health_records.html', health_records=health_records)


def get_coordinates(county):
    coordinates = {
        "Baringo": [0.4668, 35.9906],
        "Bomet": [-0.7812, 35.3413],
        "Bungoma": [0.5633, 34.5656],
        "Busia": [0.4347, 34.2422],
        "Elgeyo-Marakwet": [1.0339, 35.5451],
        "Embu": [-0.5391, 37.4597],
        "Garissa": [-0.4522, 39.6461],
        "Homa Bay": [-0.5306, 34.4571],
        "Isiolo": [0.3546, 37.5828],
        "Kajiado": [-1.8531, 36.7918],
        "Kakamega": [0.2827, 34.7529],
        "Kericho": [-0.3645, 35.2923],
        "Kiambu": [-1.1011, 36.6517],
        "Kilifi": [-3.6305, 39.8499],
        "Kirinyaga": [-0.6884, 37.3176],
        "Kisii": [-0.6785, 34.7806],
        "Kisumu": [-0.0917, 34.7679],
        "Kitui": [-1.375, 38.0104],
        "Kwale": [-4.1794, 39.4521],
        "Laikipia": [0.2027, 36.8785],
        "Lamu": [-2.277, 40.902],
        "Machakos": [-1.5177, 37.2634],
        "Makueni": [-1.8042, 37.6206],
        "Mandera": [3.9366, 41.867],
        "Marsabit": [2.3305, 37.9983],
        "Meru": [0.0477, 37.6495],
        "Migori": [-1.0634, 34.4736],
        "Mombasa": [-4.0435, 39.6682],
        "Murang'a": [-0.7836, 37.0349],
        "Nairobi": [-1.286389, 36.817223],
        "Nakuru": [-0.3031, 36.0800],
        "Nandi": [0.1138, 35.1809],
        "Narok": [-1.0784, 35.8633],
        "Nyamira": [-0.5666, 34.9358],
        "Nyandarua": [-0.3861, 36.6597],
        "Nyeri": [-0.4162, 36.9513],
        "Samburu": [1.2265, 36.7213],
        "Siaya": [0.0611, 34.2421],
        "Taita-Taveta": [-3.3148, 38.4856],
        "Tana River": [-1.4822, 40.0769],
        "Tharaka-Nithi": [-0.3007, 37.7068],
        "Trans Nzoia": [1.0204, 35.0055],
        "Turkana": [3.1122, 35.5979],
        "Uasin Gishu": [0.5154, 35.2698],
        "Vihiga": [0.0756, 34.7317],
        "Wajir": [1.7496, 40.0573],
        "West Pokot": [1.2389, 35.1489]
    }
    return coordinates.get(county, [-1.286389, 36.817223])  # Default to Nairobi


@dashboard_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Remove all session data
    flash("You have been logged out.", "info")
    return redirect(url_for('dashboard.login'))


@dashboard_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Demographic fields (optional during registration)
        age = request.form.get('age')
        gender = request.form.get('gender')
        location = request.form.get('location')
        region = request.form.get('region')

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('dashboard.register'))

        if register_user(username, email, password):
            # If demographics were provided during registration, update them
            if age or gender or location or region:
                # Get the newly created user
                user = User.query.filter_by(email=email).first()
                if user:
                    update_user_demographics(user.id, age, gender, location, region)
            
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('dashboard.login'))
        else:
            flash("Username or email already exists!", "danger")
            return redirect(url_for('dashboard.register'))
    return render_template('register.html')

@dashboard_bp.route('/', methods=['GET', 'POST'])
def root():
    return render_template('login.html')


@dashboard_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Use SQLAlchemy version
        user = authenticate_user(email, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect('/dashboard')
        else:
            flash("Invalid email or password!", "danger")
            return redirect(url_for('auth.login'))
    return render_template('login.html')



from bs4 import BeautifulSoup
import requests


@dashboard_bp.route('/search_disease', methods=['GET'])
def search_disease():
    """Search for a disease in Wikipedia and display results."""
    query = request.args.get('query', '').strip()
    app.logger.debug(f"🔍 Searching Wikipedia for: '{query}'")

    if not query:
        flash("Please enter a disease name to search.", "warning")
        return redirect(url_for('dashboard.predict'))

    try:
        # ✅ Step 1: Search for pages matching the query
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            'action': 'query',
            'list': 'search',
            'srsearch': query,
            'format': 'json',
            'srlimit': 1
        }
        
        headers = {
            'User-Agent': 'ClinicalSupportSystem/1.0 (https://yourdomain.com; contact@email.com)'
        }
        
        # Search for matching pages
        search_response = requests.get(search_url, params=search_params, headers=headers, timeout=10)
        
        if search_response.status_code != 200:
            flash("Error searching Wikipedia. Please try again.", "danger")
            return redirect(url_for('dashboard.predict'))
        
        search_data = search_response.json()
        
        if not search_data.get('query', {}).get('search'):
            flash(f"No Wikipedia results found for '{query}'. Try a different disease name.", "danger")
            return redirect(url_for('dashboard.predict'))
        
        # Get the first search result
        first_result = search_data['query']['search'][0]
        page_title = first_result['title']
        
        app.logger.debug(f"🔍 Found Wikipedia page: {page_title}")
        
        # ✅ Step 2: Get the page summary
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_title.replace(' ', '_')}"
        summary_response = requests.get(wiki_url, headers=headers, timeout=10)
        
        if summary_response.status_code == 200:
            data = summary_response.json()
            app.logger.debug(f"✅ Wikipedia Data Received for: {data.get('title', 'Unknown')}")
            
            return render_template('search_results.html', query=query, data=data)
        else:
            flash("Error retrieving disease information. Please try again.", "danger")
            return redirect(url_for('dashboard.predict'))

    except requests.exceptions.Timeout:
        app.logger.error("❌ Wikipedia API request timed out")
        flash("Search timed out. Please try again.", "danger")
        return redirect(url_for('dashboard.predict'))
        
    except requests.exceptions.ConnectionError:
        app.logger.error("❌ Wikipedia API connection error")
        flash("Network error. Please check your internet connection.", "danger")
        return redirect(url_for('dashboard.predict'))
        
    except Exception as e:
        app.logger.error(f"❌ Unexpected error during Wikipedia search: {str(e)}")
        flash("An unexpected error occurred. Please try again.", "danger")
        return redirect(url_for('dashboard.predict'))

from difflib import get_close_matches
# ✅ New Route: Process Disease Stats Query After Wikipedia Search
@dashboard_bp.route('/query_disease_stats', methods=['GET', 'POST'])
def query_disease_stats():
    """Handle searching for diseases."""
    if request.method == 'POST':
        user_query = request.form.get('query', '').strip()
        app.logger.debug(f"📊 Searching for closest match in DB: {user_query}")

        if not user_query:
            flash("Invalid search query.", "warning")
            return redirect(url_for('dashboard.query_disease_stats'))

        matched_disease = get_close_matches(user_query, diseases_list.values(), n=1, cutoff=0.6)

        if matched_disease:
            matched_disease_name = matched_disease[0]
            app.logger.debug(f"🔹 Closest match found: {matched_disease_name}")
            return redirect(url_for('dashboard.disease_stats', disease=matched_disease_name))
        else:
            flash("No matching disease found. Check your spelling and Try again.", "danger")
            return redirect(url_for('dashboard.query_disease_stats'))

    # Handle GET request (e.g., render the search form)
    return render_template('search_results.html')


# about view function and path
@dashboard_bp.route('/about')
def about():
    return render_template("about.html")

# contact view function and path
@dashboard_bp.route('/contact')
def contact():
    return render_template("contact.html")

# developer view function and path
@dashboard_bp.route('/developer')
def developer():
    return render_template("developer.html")

# about view function and path
@dashboard_bp.route('/blog')
def blog():
    return render_template("blog.html")

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=3000)

