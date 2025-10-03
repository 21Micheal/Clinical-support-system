# routes/outbreak_prediction.py
from flask import Blueprint, request, jsonify, render_template, session
from outbreak_predictor import OutbreakPredictor
from models.user_model import db, Predictions, OutbreakAlert
from models.user_model import OutbreakNotification as Notification
from datetime import datetime, timedelta
from sqlalchemy import func
import json

outbreak_bp = Blueprint('outbreak', __name__)

# Initialize predictor
predictor = OutbreakPredictor()

@outbreak_bp.route('/outbreak-prediction')
def outbreak_dashboard():
    """Render outbreak prediction dashboard"""
    # Get all unique disease-location combinations
    combinations = db.session.query(
        Predictions.predicted_disease,
        Predictions.location
    ).distinct().all()
    
    diseases = list(set([c[0] for c in combinations]))
    locations = list(set([c[1] for c in combinations]))
    
    return render_template('outbreak_dashboard.html',
                         diseases=diseases,
                         locations=locations)


@outbreak_bp.route('/api/outbreak/predict', methods=['POST'])
def predict_outbreak_api():
    """
    API endpoint to get outbreak prediction
    
    POST body:
    {
        "disease": "Malaria",
        "location": "Nairobi",
        "days_ahead": 7
    }
    """
    try:
        data = request.json
        disease = data.get('disease')
        location = data.get('location')
        days_ahead = data.get('days_ahead', 7)
        
        if not disease or not location:
            return jsonify({"error": "Disease and location required"}), 400
        
        # Get prediction
        result = predictor.predict_outbreak(disease, location, days_ahead)
        
        if "error" in result:
            return jsonify(result), 400
        
        # Save prediction to database
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
        db.session.commit()
        
        # Send notifications if high risk
        if result['risk_level'] in ['HIGH', 'CRITICAL']:
            send_outbreak_notifications(disease, location, result)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error in predict_outbreak_api: {e}")
        return jsonify({"error": str(e)}), 500


@outbreak_bp.route('/api/outbreak/all-predictions')
def get_all_predictions():
    """Get predictions for all disease-location combinations"""
    try:
        # Get all combinations with sufficient data
        combinations = db.session.query(
            Predictions.predicted_disease,
            Predictions.location,
            func.count(Predictions.id).label('case_count')
        ).group_by(
            Predictions.predicted_disease,
            Predictions.location
        ).having(func.count(Predictions.id) >= 10).all()
        
        predictions = []
        
        for disease, location, case_count in combinations:
            try:
                result = predictor.predict_outbreak(disease, location)
                if "error" not in result:
                    predictions.append(result)
            except Exception as e:
                print(f"⚠️ Could not predict {disease} in {location}: {e}")
                continue
        
        # Sort by risk level
        risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        predictions.sort(key=lambda x: risk_order.get(x['risk_level'], 4))
        
        return jsonify({
            "predictions": predictions,
            "total": len(predictions),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Error in get_all_predictions: {e}")
        return jsonify({"error": str(e)}), 500


@outbreak_bp.route('/api/outbreak/history/<disease>/<location>')
def get_prediction_history(disease, location):
    """Get historical predictions for a disease-location pair"""
    try:
        alerts = OutbreakAlert.query.filter_by(
            disease=disease,
            location=location
        ).order_by(OutbreakAlert.timestamp.desc()).limit(30).all()
        
        history = [{
            "date": alert.timestamp.strftime("%Y-%m-%d"),
            "risk_level": alert.risk_level,
            "predicted_cases": alert.predicted_cases,
            "confidence": alert.confidence
        } for alert in alerts]
        
        return jsonify({
            "disease": disease,
            "location": location,
            "history": history
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outbreak_bp.route('/api/outbreak/trending')
def get_trending_diseases():
    """Get diseases with increasing trends"""
    try:
        # Get cases from last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        fifteen_days_ago = datetime.now() - timedelta(days=15)
        
        # Cases in first 15 days
        first_half = db.session.query(
            Predictions.predicted_disease,
            func.count(Predictions.id).label('cases')
        ).filter(
            Predictions.timestamp >= thirty_days_ago,
            Predictions.timestamp < fifteen_days_ago
        ).group_by(Predictions.predicted_disease).all()
        
        # Cases in last 15 days
        second_half = db.session.query(
            Predictions.predicted_disease,
            func.count(Predictions.id).label('cases')
        ).filter(
            Predictions.timestamp >= fifteen_days_ago
        ).group_by(Predictions.predicted_disease).all()
        
        # Calculate trends
        first_dict = {disease: cases for disease, cases in first_half}
        second_dict = {disease: cases for disease, cases in second_half}
        
        trending = []
        for disease in set(list(first_dict.keys()) + list(second_dict.keys())):
            first_cases = first_dict.get(disease, 0)
            second_cases = second_dict.get(disease, 0)
            
            if first_cases > 0:
                change = ((second_cases - first_cases) / first_cases) * 100
            else:
                change = 100 if second_cases > 0 else 0
            
            if change > 20:  # More than 20% increase
                trending.append({
                    "disease": disease,
                    "first_period_cases": first_cases,
                    "second_period_cases": second_cases,
                    "percent_change": round(change, 1),
                    "status": "increasing"
                })
        
        # Sort by percent change
        trending.sort(key=lambda x: x['percent_change'], reverse=True)
        
        return jsonify({
            "trending_diseases": trending,
            "period": "Last 30 days",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@outbreak_bp.route('/api/outbreak/hotspots')
def get_outbreak_hotspots():
    """Identify locations with multiple high-risk diseases"""
    try:
        # Get all locations
        locations = db.session.query(
            Predictions.location
        ).distinct().all()
        
        hotspots = []
        
        for (location,) in locations:
            # Get all diseases in this location
            diseases = db.session.query(
                Predictions.predicted_disease
            ).filter(
                Predictions.location == location
            ).distinct().all()
            
            high_risk_count = 0
            total_risk_score = 0
            disease_risks = []
            
            for (disease,) in diseases:
                try:
                    result = predictor.predict_outbreak(disease, location)
                    
                    if "error" not in result:
                        risk_level = result['risk_level']
                        
                        # Score risks
                        risk_scores = {
                            "CRITICAL": 4,
                            "HIGH": 3,
                            "MEDIUM": 2,
                            "LOW": 1
                        }
                        
                        score = risk_scores.get(risk_level, 0)
                        total_risk_score += score
                        
                        if risk_level in ['HIGH', 'CRITICAL']:
                            high_risk_count += 1
                        
                        disease_risks.append({
                            "disease": disease,
                            "risk_level": risk_level,
                            "predicted_cases": result['predicted_cases_7d']
                        })
                        
                except Exception as e:
                    continue
            
            if high_risk_count > 0:
                hotspots.append({
                    "location": location,
                    "high_risk_diseases": high_risk_count,
                    "total_diseases": len(diseases),
                    "risk_score": total_risk_score,
                    "diseases": disease_risks
                })
        
        # Sort by risk score
        hotspots.sort(key=lambda x: x['risk_score'], reverse=True)
        
        return jsonify({
            "hotspots": hotspots,
            "total_hotspots": len(hotspots),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def send_outbreak_notifications(disease, location, prediction):
    """Send notifications for high-risk outbreaks"""
    # TODO: Integrate with your notification system
    # Examples:
    # - Email notifications to health officials
    # - SMS alerts to community health workers
    # - Push notifications to mobile app users
    # - Dashboard alerts
    
    message = f"""
    ⚠️ OUTBREAK ALERT
    
    Disease: {disease}
    Location: {location}
    Risk Level: {prediction['risk_level']}
    Predicted Cases (7 days): {prediction['predicted_cases_7d']}
    
    Recommendations:
    {chr(10).join(prediction['recommendations'])}
    """
    
    print(f"🚨 ALERT: {message}")
    
    # Save notification to database
    notification = Notification(
        type='outbreak_alert',
        message=message,
        disease=disease,
        location=location,
        timestamp=datetime.now()
    )
    db.session.add(notification)
    db.session.commit()
    
    return True


# Background task to run predictions daily
def run_daily_predictions():
    """
    Run outbreak predictions for all disease-location pairs
    Should be called by a scheduler (e.g., APScheduler, Celery)
    """
    print("🔄 Running daily outbreak predictions...")
    
    combinations = db.session.query(
        Predictions.predicted_disease,
        Predictions.location,
        func.count(Predictions.id).label('case_count')
    ).group_by(
        Predictions.predicted_disease,
        Predictions.location
    ).having(func.count(Predictions.id) >= 10).all()
    
    high_risk_count = 0
    
    for disease, location, case_count in combinations:
        try:
            result = predictor.predict_outbreak(disease, location)
            
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
                
                if result['risk_level'] in ['HIGH', 'CRITICAL']:
                    high_risk_count += 1
                    send_outbreak_notifications(disease, location, result)
                
                print(f"✅ Predicted {disease} in {location}: {result['risk_level']}")
                
        except Exception as e:
            print(f"❌ Error predicting {disease} in {location}: {e}")
            continue
    
    db.session.commit()
    print(f"✅ Daily predictions complete. High-risk alerts: {high_risk_count}")
    
    return high_risk_count