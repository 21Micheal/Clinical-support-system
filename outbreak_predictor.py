# outbreak_predictor.py
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
from models.user_model import db, Predictions
import pickle
import os

class OutbreakPredictor:
    """
    AI-powered disease outbreak prediction using:
    - Time series analysis
    - Machine learning (Random Forest & Gradient Boosting)
    - Anomaly detection
    - Trend analysis
    """
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        self.model_path = 'models/outbreak_model.pkl'
        
    def fetch_historical_data(self, disease, location, days=90):
        """
        Fetch historical case data for a specific disease and location
        
        Args:
            disease: Disease name
            location: Location name
            days: Number of days of historical data
            
        Returns:
            DataFrame with daily case counts
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Query database for predictions in date range
        cases_query = db.session.query(
            db.func.date(Predictions.timestamp).label('date'),
            db.func.count(Predictions.id).label('cases')
        ).filter(
            Predictions.predicted_disease == disease,
            Predictions.location == location,
            Predictions.timestamp >= start_date,
            Predictions.timestamp <= end_date
        ).group_by(db.func.date(Predictions.timestamp)).all()
        
        if not cases_query:
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(cases_query, columns=['date', 'cases'])
        df['date'] = pd.to_datetime(df['date'])
        
        # Create complete date range (fill missing dates with 0)
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        df_complete = pd.DataFrame({'date': date_range})
        df = df_complete.merge(df, on='date', how='left').fillna(0)
        df['cases'] = df['cases'].astype(int)
        
        return df
    
    def engineer_features(self, df):
        """
        Create time series features for machine learning
        
        Features include:
        - Temporal features (day of week, month, etc.)
        - Rolling statistics (mean, std, min, max)
        - Lag features (previous days)
        - Trend indicators
        """
        df = df.copy()
        
        # Temporal features
        df['day_of_week'] = df['date'].dt.dayofweek
        df['day_of_month'] = df['date'].dt.day
        df['week_of_year'] = df['date'].dt.isocalendar().week
        df['month'] = df['date'].dt.month
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        
        # Rolling statistics (7-day window)
        df['cases_7d_mean'] = df['cases'].rolling(window=7, min_periods=1).mean()
        df['cases_7d_std'] = df['cases'].rolling(window=7, min_periods=1).std().fillna(0)
        df['cases_7d_min'] = df['cases'].rolling(window=7, min_periods=1).min()
        df['cases_7d_max'] = df['cases'].rolling(window=7, min_periods=1).max()
        
        # 14-day statistics
        df['cases_14d_mean'] = df['cases'].rolling(window=14, min_periods=1).mean()
        df['cases_14d_std'] = df['cases'].rolling(window=14, min_periods=1).std().fillna(0)
        
        # Lag features (previous days)
        for lag in [1, 3, 7, 14]:
            df[f'cases_lag_{lag}'] = df['cases'].shift(lag).fillna(0)
        
        # Trend features
        df['cases_trend'] = df['cases'].diff().fillna(0)
        df['cases_acceleration'] = df['cases_trend'].diff().fillna(0)
        
        # Growth rate
        df['growth_rate'] = df['cases'].pct_change().fillna(0)
        df['growth_rate'] = df['growth_rate'].replace([np.inf, -np.inf], 0)
        
        # Cumulative cases
        df['cumulative_cases'] = df['cases'].cumsum()
        
        return df
    
    def prepare_training_data(self, df, prediction_horizon=7):
        """
        Prepare features (X) and target (y) for training
        
        Args:
            df: DataFrame with engineered features
            prediction_horizon: Days ahead to predict
        """
        feature_columns = [
            'day_of_week', 'day_of_month', 'week_of_year', 'month', 'is_weekend',
            'cases_7d_mean', 'cases_7d_std', 'cases_7d_min', 'cases_7d_max',
            'cases_14d_mean', 'cases_14d_std',
            'cases_lag_1', 'cases_lag_3', 'cases_lag_7', 'cases_lag_14',
            'cases_trend', 'cases_acceleration', 'growth_rate', 'cumulative_cases'
        ]
        
        # Create target: cases N days ahead
        df['target'] = df['cases'].shift(-prediction_horizon)
        
        # Remove rows with NaN targets
        df_clean = df.dropna(subset=['target'])
        
        X = df_clean[feature_columns].values
        y = df_clean['target'].values
        
        return X, y, feature_columns
    
    def train_model(self, disease, location, days=90):
        """
        Train the outbreak prediction model
        """
        # Fetch data
        df = self.fetch_historical_data(disease, location, days)
        
        if df is None or len(df) < 30:
            print(f"⚠️ Insufficient data for {disease} in {location}")
            return False
        
        # Engineer features
        df = self.engineer_features(df)
        
        # Prepare training data
        X, y, feature_columns = self.prepare_training_data(df)
        
        if len(X) < 20:
            print(f"⚠️ Not enough samples to train for {disease} in {location}")
            return False
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train ensemble model (Random Forest + Gradient Boosting)
        rf_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42
        )
        
        gb_model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        
        rf_model.fit(X_scaled, y)
        gb_model.fit(X_scaled, y)
        
        # Store both models
        self.model = {
            'rf': rf_model,
            'gb': gb_model,
            'feature_columns': feature_columns
        }
        self.is_trained = True
        
        print(f"✅ Model trained for {disease} in {location}")
        return True
    
    def predict_outbreak(self, disease, location, days_ahead=7):
        """
        Predict outbreak risk for the next N days
        
        Returns:
            dict with prediction results and risk assessment
        """
        # Fetch recent data
        df = self.fetch_historical_data(disease, location, days=90)
        
        if df is None or len(df) < 30:
            return {
                "error": "Insufficient historical data",
                "disease": disease,
                "location": location
            }
        
        # Train model if not trained
        if not self.is_trained:
            success = self.train_model(disease, location)
            if not success:
                return {"error": "Could not train model"}
        
        # Engineer features
        df = self.engineer_features(df)
        
        # Get latest features
        feature_columns = self.model['feature_columns']
        latest_features = df[feature_columns].iloc[-1:].values
        
        # Scale features
        latest_scaled = self.scaler.transform(latest_features)
        
        # Predict with both models
        rf_pred = self.model['rf'].predict(latest_scaled)[0]
        gb_pred = self.model['gb'].predict(latest_scaled)[0]
        
        # Ensemble prediction (average)
        predicted_cases = (rf_pred + gb_pred) / 2
        predicted_cases = max(0, int(predicted_cases))
        
        # Calculate historical baseline
        recent_mean = df['cases'].tail(14).mean()
        recent_std = df['cases'].tail(14).std()
        recent_max = df['cases'].tail(30).max()
        
        # Trend analysis
        recent_trend = df['cases_trend'].tail(7).mean()
        is_increasing = recent_trend > 0
        
        # Risk assessment
        risk_level = self._assess_risk(
            predicted_cases, 
            recent_mean, 
            recent_std, 
            recent_max,
            is_increasing
        )
        
        # Calculate confidence based on data quality
        confidence = self._calculate_confidence(df, recent_std)
        
        # Generate daily predictions for visualization
        daily_predictions = self._generate_daily_predictions(
            df, days_ahead
        )
        
        return {
            "disease": disease,
            "location": location,
            "prediction_date": datetime.now().strftime("%Y-%m-%d"),
            "predicted_cases_7d": predicted_cases,
            "current_cases_14d": int(df['cases'].tail(14).sum()),
            "average_daily_cases": round(recent_mean, 2),
            "risk_level": risk_level,
            "confidence": confidence,
            "trend": "increasing" if is_increasing else "decreasing",
            "trend_value": round(recent_trend, 2),
            "daily_predictions": daily_predictions,
            "alert_threshold": int(recent_mean + 2 * recent_std),
            "recommendations": self._generate_recommendations(risk_level, disease)
        }
    
    def _assess_risk(self, predicted, mean, std, recent_max, is_increasing):
        """Assess outbreak risk level"""
        # Calculate z-score
        if std > 0:
            z_score = (predicted - mean) / std
        else:
            z_score = 0
        
        # Risk thresholds
        if predicted > mean + 2 * std or z_score > 2:
            return "CRITICAL"
        elif predicted > mean + std or (z_score > 1 and is_increasing):
            return "HIGH"
        elif predicted > mean or (z_score > 0.5 and is_increasing):
            return "MEDIUM"
        else:
            return "LOW"
    
    def _calculate_confidence(self, df, recent_std):
        """Calculate prediction confidence"""
        data_points = len(df)
        
        if data_points < 30:
            return "LOW"
        elif data_points < 60 or recent_std > 10:
            return "MEDIUM"
        else:
            return "HIGH"
    
    def _generate_daily_predictions(self, df, days_ahead):
        """Generate day-by-day predictions"""
        predictions = []
        latest_cases = df['cases'].iloc[-1]
        trend = df['cases_trend'].tail(7).mean()
        
        for i in range(1, days_ahead + 1):
            # Simple trend-based prediction
            predicted = max(0, int(latest_cases + (trend * i)))
            predictions.append({
                "day": i,
                "date": (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"),
                "predicted_cases": predicted
            })
        
        return predictions
    
    def _generate_recommendations(self, risk_level, disease):
        """Generate action recommendations based on risk"""
        recommendations = {
            "CRITICAL": [
                f"⚠️ Immediate action required - {disease} outbreak likely",
                "Mobilize emergency response teams",
                "Increase public awareness campaigns",
                "Stock up on medications and medical supplies",
                "Set up additional screening centers",
                "Coordinate with neighboring health facilities"
            ],
            "HIGH": [
                f"🔴 High risk of {disease} outbreak detected",
                "Enhance surveillance systems",
                "Prepare medical supplies and staff",
                "Issue public health advisories",
                "Increase community sensitization",
                "Monitor situation daily"
            ],
            "MEDIUM": [
                f"🟡 Moderate risk - Monitor {disease} cases closely",
                "Continue routine surveillance",
                "Ensure adequate medical supplies",
                "Brief healthcare workers on symptoms",
                "Maintain readiness for potential increase"
            ],
            "LOW": [
                f"🟢 Low risk - {disease} cases stable",
                "Continue standard monitoring",
                "Maintain preventive measures",
                "Keep public informed"
            ]
        }
        
        return recommendations.get(risk_level, [])
    
    def save_model(self, filepath=None):
        """Save trained model to disk"""
        if not self.is_trained:
            print("⚠️ No trained model to save")
            return False
        
        filepath = filepath or self.model_path
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler
            }, f)
        
        print(f"✅ Model saved to {filepath}")
        return True
    
    def load_model(self, filepath=None):
        """Load trained model from disk"""
        filepath = filepath or self.model_path
        
        if not os.path.exists(filepath):
            print("⚠️ Model file not found")
            return False
        
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.scaler = data['scaler']
            self.is_trained = True
        
        print(f"✅ Model loaded from {filepath}")
        return True


# ===================================
# Usage Example
# ===================================

if __name__ == "__main__":
    # Initialize predictor
    predictor = OutbreakPredictor()
    
    # Predict outbreak for Malaria in Nairobi
    result = predictor.predict_outbreak("Malaria", "Nairobi", days_ahead=7)
    
    print("\n" + "="*50)
    print("OUTBREAK PREDICTION RESULTS")
    print("="*50)
    print(f"Disease: {result['disease']}")
    print(f"Location: {result['location']}")
    print(f"Risk Level: {result['risk_level']}")
    print(f"Predicted Cases (7 days): {result['predicted_cases_7d']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Trend: {result['trend']}")
    print("\nRecommendations:")
    for rec in result['recommendations']:
        print(f"  • {rec}")
    print("="*50)