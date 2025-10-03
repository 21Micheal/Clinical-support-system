# scheduler.py - Automated outbreak prediction scheduler

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import current_app
from outbreak_predictor import OutbreakPredictor
from models.user_model import db, Predictions, OutbreakAlert
from datetime import datetime, timedelta
from sqlalchemy import func
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OutbreakScheduler:
    """
    Automated scheduler for outbreak predictions
    Runs daily predictions and sends alerts
    """
    
    def __init__(self, app=None):
        self.scheduler = BackgroundScheduler()
        self.predictor = OutbreakPredictor()
        self.app = app
        
    def init_app(self, app):
        """Initialize scheduler with Flask app"""
        self.app = app
        
        # Schedule daily predictions at 6:00 AM
        self.scheduler.add_job(
            func=self.run_daily_predictions,
            trigger=CronTrigger(hour=6, minute=0),
            id='daily_predictions',
            name='Run daily outbreak predictions',
            replace_existing=True
        )
        
        # Schedule weekly model retraining at Sunday 2:00 AM
        self.scheduler.add_job(
            func=self.retrain_models,
            trigger=CronTrigger(day_of_week='sun', hour=2, minute=0),
            id='weekly_retraining',
            name='Retrain outbreak prediction models',
            replace_existing=True
        )
        
        # Schedule hourly check for critical alerts
        self.scheduler.add_job(
            func=self.check_critical_alerts,
            trigger=CronTrigger(minute=0),
            id='hourly_critical_check',
            name='Check for critical alerts',
            replace_existing=True
        )
        
        logger.info("✅ Outbreak prediction scheduler initialized")
        
    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("🚀 Outbreak prediction scheduler started")
    
    def shutdown(self):
        """Shutdown the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("🛑 Outbreak prediction scheduler stopped")
    
    def run_daily_predictions(self):
        """
        Run outbreak predictions for all disease-location combinations
        Called daily at 6:00 AM
        """
        with self.app.app_context():
            logger.info("🔄 Starting daily outbreak predictions...")
            
            try:
                # Get all disease-location combinations with sufficient data
                combinations = db.session.query(
                    Predictions.predicted_disease,
                    Predictions.location,
                    func.count(Predictions.id).label('case_count')
                ).group_by(
                    Predictions.predicted_disease,
                    Predictions.location
                ).having(func.count(Predictions.id) >= 10).all()
                
                logger.info(f"📊 Found {len(combinations)} disease-location combinations")
                
                high_risk_count = 0
                critical_count = 0
                predictions_made = 0
                
                for disease, location, case_count in combinations:
                    try:
                        # Make prediction
                        result = self.predictor.predict_outbreak(disease, location, days_ahead=7)
                        
                        if "error" not in result:
                            # Save to database
                            alert = OutbreakAlert(
                                disease=disease,
                                location=location,
                                risk_level=result['risk_level'],
                                predicted_cases=result['predicted_cases_7d'],
                                confidence=result['confidence'],
                                prediction_data=json.dumps(result),
                                timestamp=datetime.now()
                            )
                            db.session.add(alert)
                            
                            predictions_made += 1
                            
                            # Count risks
                            if result['risk_level'] == 'CRITICAL':
                                critical_count += 1
                                self.send_alert_notification(disease, location, result)
                            elif result['risk_level'] == 'HIGH':
                                high_risk_count += 1
                                self.send_alert_notification(disease, location, result)
                            
                            logger.info(f"✅ Predicted {disease} in {location}: {result['risk_level']}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error predicting {disease} in {location}: {e}")
                        continue
                
                db.session.commit()
                
                logger.info(f"""
                ✅ Daily predictions complete:
                   - Total predictions: {predictions_made}
                   - Critical alerts: {critical_count}
                   - High risk alerts: {high_risk_count}
                """)
                
                # Send summary report
                self.send_daily_summary(predictions_made, critical_count, high_risk_count)
                
            except Exception as e:
                logger.error(f"❌ Error in daily predictions: {e}")
                db.session.rollback()
    
    def retrain_models(self):
        """
        Retrain prediction models with latest data
        Called weekly on Sundays at 2:00 AM
        """
        with self.app.app_context():
            logger.info("🔄 Starting weekly model retraining...")
            
            try:
                combinations = db.session.query(
                    Predictions.predicted_disease,
                    Predictions.location,
                    func.count(Predictions.id).label('case_count')
                ).group_by(
                    Predictions.predicted_disease,
                    Predictions.location
                ).having(func.count(Predictions.id) >= 30).all()
                
                models_trained = 0
                
                for disease, location, case_count in combinations:
                    try:
                        predictor = OutbreakPredictor()
                        success = predictor.train_model(disease, location, days=90)
                        
                        if success:
                            # Save model
                            model_path = f"models/outbreak_{disease}_{location}.pkl"
                            predictor.save_model(model_path)
                            models_trained += 1
                            
                            logger.info(f"✅ Trained model for {disease} in {location}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error training model for {disease} in {location}: {e}")
                        continue
                
                logger.info(f"✅ Weekly retraining complete. Models trained: {models_trained}")
                
            except Exception as e:
                logger.error(f"❌ Error in weekly retraining: {e}")
    
    def check_critical_alerts(self):
        """
        Check for critical alerts and send notifications
        Called hourly
        """
        with self.app.app_context():
            try:
                # Get critical alerts from last hour
                one_hour_ago = datetime.now() - timedelta(hours=1)
                
                critical_alerts = OutbreakAlert.query.filter(
                    OutbreakAlert.timestamp >= one_hour_ago,
                    OutbreakAlert.risk_level == 'CRITICAL',
                    OutbreakAlert.action_taken == False
                ).all()
                
                if critical_alerts:
                    logger.warning(f"🚨 {len(critical_alerts)} unaddressed critical alerts found!")
                    
                    for alert in critical_alerts:
                        logger.warning(f"   - {alert.disease} in {alert.location}")
                        # Resend notification
                        prediction_data = json.loads(alert.prediction_data)
                        self.send_alert_notification(alert.disease, alert.location, prediction_data)
                
            except Exception as e:
                logger.error(f"❌ Error checking critical alerts: {e}")
    
    def send_alert_notification(self, disease, location, prediction):
        """Send notification for high-risk outbreak prediction"""
        try:
            message = f"""
🚨 OUTBREAK ALERT

Disease: {disease}
Location: {location}
Risk Level: {prediction['risk_level']}
Predicted Cases (7 days): {prediction['predicted_cases_7d']}
Confidence: {prediction['confidence']}
Trend: {prediction['trend']}

RECOMMENDATIONS:
{chr(10).join(['  • ' + r for r in prediction['recommendations'][:3]])}

Dashboard: https://your-domain.com/outbreak-prediction
            """
            
            logger.warning(f"🚨 ALERT: {message}")
            
            # TODO: Implement actual notification sending
            # Examples:
            # - Email to health officials
            # - SMS to community health workers
            # - Push notifications to mobile apps
            # - Slack/Teams notifications
            
            # Example: Email notification
            # send_email(
            #     to=['health@example.com'],
            #     subject=f'OUTBREAK ALERT: {disease} in {location}',
            #     body=message
            # )
            
            # Example: SMS notification
            # send_sms(
            #     phone='+254712345678',
            #     message=message
            # )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending notification: {e}")
            return False
    
    def send_daily_summary(self, total_predictions, critical_count, high_count):
        """Send daily summary report"""
        try:
            summary = f"""
📊 DAILY OUTBREAK PREDICTION SUMMARY
Date: {datetime.now().strftime('%Y-%m-%d')}

Total Predictions: {total_predictions}
Critical Alerts: {critical_count}
High Risk Alerts: {high_count}

Dashboard: https://your-domain.com/outbreak-prediction
            """
            
            logger.info(f"📧 Daily summary: {summary}")
            
            # TODO: Send to administrators
            # send_email(
            #     to=['admin@example.com'],
            #     subject='Daily Outbreak Prediction Summary',
            #     body=summary
            # )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending summary: {e}")
            return False


# ===================================
# Integration with Flask App
# ===================================

def init_scheduler(app):
    """Initialize and start the outbreak prediction scheduler"""
    scheduler = OutbreakScheduler(app)
    scheduler.start()
    
    # Register shutdown handler
    import atexit
    atexit.register(lambda: scheduler.shutdown())
    
    return scheduler


# ===================================
# Manual Trigger Functions
# ===================================

def trigger_predictions_now(app):
    """Manually trigger predictions (useful for testing)"""
    scheduler = OutbreakScheduler(app)
    scheduler.run_daily_predictions()


def trigger_retraining_now(app):
    """Manually trigger model retraining"""
    scheduler = OutbreakScheduler(app)
    scheduler.retrain_models()


# ===================================
# Usage in main app.py
# ===================================

"""
# In your app.py or __init__.py

from scheduler import init_scheduler

app = Flask(__name__)
# ... your app configuration ...

# Initialize scheduler
if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    scheduler = init_scheduler(app)
    
# Or for testing, run manually:
# with app.app_context():
#     from scheduler import trigger_predictions_now
#     trigger_predictions_now(app)
"""


# ===================================
# CLI Commands (Optional)
# ===================================

"""
# Add these Flask CLI commands for manual control

from flask.cli import with_appcontext
import click

@app.cli.command('predict-outbreaks')
@with_appcontext
def predict_outbreaks_command():
    '''Run outbreak predictions manually'''
    click.echo('Running outbreak predictions...')
    trigger_predictions_now(current_app)
    click.echo('Done!')

@app.cli.command('retrain-models')
@with_appcontext
def retrain_models_command():
    '''Retrain prediction models manually'''
    click.echo('Retraining models...')
    trigger_retraining_now(current_app)
    click.echo('Done!')

# Usage:
# flask predict-outbreaks
# flask retrain-models
"""


# ===================================
# Testing the Scheduler
# ===================================

if __name__ == "__main__":
    from flask import Flask
    from models.user_model import db
    
    # Create test app
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:pass@localhost/health_care'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    # Test predictions
    with app.app_context():
        scheduler = OutbreakScheduler(app)
        print("Testing daily predictions...")
        scheduler.run_daily_predictions()
        print("Test complete!")