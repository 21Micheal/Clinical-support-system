# Fixed smart_recommendations.py - handles missing created_at field
from datetime import datetime, timedelta
from models.user_model import db, Predictions, User
from sqlalchemy import func, and_

class SmartRecommendationEngine:
    """
    Generates personalized recommendations based on:
    - Disease type
    - User demographics (age, gender)
    - Location-based outbreak patterns
    - Historical user actions
    - Severity indicators from symptoms
    """
    
    # Disease severity levels based on symptoms count and type
    SEVERITY_THRESHOLDS = {
        'high': 8,      # 8+ symptoms
        'moderate': 5,  # 5-7 symptoms
        'low': 3        # 3-4 symptoms
    }
    
    # High-risk diseases requiring immediate attention
    CRITICAL_DISEASES = [
        'Heart attack', 'Stroke', 'Pneumonia', 'Tuberculosis',
        'Dengue', 'Malaria', 'Typhoid', 'COVID-19', 'Hepatitis B',
        'Hepatitis C', 'Hepatitis D', 'Hepatitis E', 'Alcoholic hepatitis'
    ]
    
    def __init__(self, user_id, predicted_disease, symptoms_count, gender, age, location):
        self.user_id = user_id
        self.predicted_disease = predicted_disease
        self.symptoms_count = symptoms_count
        self.gender = gender
        self.age = int(age) if age else 0
        self.location = location
        self.severity = self._calculate_severity()
        
    def _calculate_severity(self):
        """Determine severity level based on symptoms count and disease type"""
        if self.predicted_disease in self.CRITICAL_DISEASES:
            return 'high'
        elif self.symptoms_count >= self.SEVERITY_THRESHOLDS['high']:
            return 'high'
        elif self.symptoms_count >= self.SEVERITY_THRESHOLDS['moderate']:
            return 'moderate'
        else:
            return 'low'
    
    def generate_recommendations(self):
        """Generate comprehensive smart recommendations"""
        recommendations = {
            'urgency_level': self.severity,
            'primary_actions': self._get_primary_actions(),
            'demographic_specific': self._get_demographic_recommendations(),
            'location_alerts': self._get_location_alerts(),
            'timeline': self._get_action_timeline(),
            'follow_up_questions': self._generate_follow_up_questions(),
            'risk_factors': self._identify_risk_factors(),
            'when_to_seek_help': self._get_emergency_indicators()
        }
        return recommendations
    
    def _get_primary_actions(self):
        """Get immediate actions based on severity and disease"""
        actions = []
        
        if self.severity == 'high':
            actions.append({
                'priority': 1,
                'action': 'Seek immediate medical attention',
                'reason': f'{self.predicted_disease} requires prompt professional evaluation',
                'urgency': 'URGENT - Within 24 hours'
            })
            actions.append({
                'priority': 2,
                'action': 'Visit nearest hospital or clinic',
                'reason': 'Professional diagnosis and treatment needed',
                'urgency': 'URGENT'
            })
        elif self.severity == 'moderate':
            actions.append({
                'priority': 1,
                'action': 'Schedule a doctor appointment within 2-3 days',
                'reason': 'Medical consultation recommended for proper diagnosis',
                'urgency': 'Important'
            })
            actions.append({
                'priority': 2,
                'action': 'Monitor symptoms closely',
                'reason': 'Track any changes or worsening of condition',
                'urgency': 'Important'
            })
        else:
            actions.append({
                'priority': 1,
                'action': 'Rest and self-care',
                'reason': 'Allow your body to recover naturally',
                'urgency': 'Recommended'
            })
            actions.append({
                'priority': 2,
                'action': 'Monitor for 48-72 hours',
                'reason': 'Ensure symptoms improve with home care',
                'urgency': 'Recommended'
            })
        
        return actions
    
    def _get_demographic_recommendations(self):
        """Personalized recommendations based on age and gender"""
        recommendations = []
        
        # Age-based recommendations
        if self.age < 5:
            recommendations.append({
                'category': 'Pediatric Care',
                'advice': 'Children under 5 require special attention. Consult a pediatrician.',
                'reason': 'Young children may deteriorate quickly'
            })
        elif self.age >= 60:
            recommendations.append({
                'category': 'Senior Care',
                'advice': 'Older adults should seek medical evaluation sooner due to higher risk.',
                'reason': 'Age increases vulnerability to complications'
            })
        elif 18 <= self.age <= 35:
            recommendations.append({
                'category': 'Young Adult',
                'advice': 'Maintain hydration and adequate rest. Work stress may worsen recovery.',
                'reason': 'Active lifestyle may mask severity'
            })
        
        # Gender-specific recommendations
        if self.gender.lower() == 'female':
            if 15 <= self.age <= 49:
                recommendations.append({
                    'category': 'Women\'s Health',
                    'advice': 'If pregnant or planning pregnancy, inform your healthcare provider immediately.',
                    'reason': 'Some treatments may affect reproductive health'
                })
        
        # Disease-specific demographic risks
        if self.predicted_disease == 'Diabetes' and self.age > 40:
            recommendations.append({
                'category': 'Diabetes Risk',
                'advice': 'Regular blood sugar monitoring essential. Consider HbA1c test.',
                'reason': 'Age is a significant risk factor for diabetes complications'
            })
        
        return recommendations
    
    def _get_location_alerts(self):
        """Check for disease outbreaks in user's location - WITHOUT created_at"""
        alerts = []
        
        try:
            # Check ALL cases in user's location (no date filter since we don't have created_at)
            location_cases = db.session.query(
                func.count(Predictions.id)
            ).filter(
                Predictions.location == self.location,
                Predictions.predicted_disease == self.predicted_disease
            ).scalar() or 0
            
            if location_cases >= 5:
                alerts.append({
                    'type': 'outbreak_alert',
                    'severity': 'high',
                    'message': f'Elevated cases of {self.predicted_disease} detected in {self.location}',
                    'count': location_cases,
                    'advice': 'Exercise extra caution. Follow all preventive measures strictly.'
                })
            
            # Check for related diseases in the area
            disease_locations = db.session.query(
                Predictions.location
            ).filter(
                Predictions.predicted_disease == self.predicted_disease
            ).distinct().all()
            
            disease_location_list = [loc[0] for loc in disease_locations]
            
            if self.location in disease_location_list:
                related_diseases = db.session.query(
                    Predictions.predicted_disease,
                    func.count(Predictions.id).label('count')
                ).filter(
                    Predictions.predicted_disease != self.predicted_disease,
                    Predictions.location == self.location
                ).group_by(Predictions.predicted_disease).having(
                    func.count(Predictions.id) >= 3
                ).all()
                
                if related_diseases:
                    alerts.append({
                        'type': 'area_health_alert',
                        'severity': 'moderate',
                        'message': f'Other diseases active in {self.location}',
                        'diseases': [{'name': d[0], 'cases': d[1]} for d in related_diseases],
                        'advice': 'Maintain good hygiene and preventive practices'
                    })
        
        except Exception as e:
            print(f"⚠️ Warning: Could not fetch location alerts: {str(e)}")
            # Return empty alerts if there's an error
            pass
        
        return alerts
    
    def _get_action_timeline(self):
        """Create a timeline of recommended actions"""
        timeline = []
        
        if self.severity == 'high':
            timeline = [
                {'timeframe': 'Immediately', 'action': 'Contact healthcare provider or go to emergency'},
                {'timeframe': 'Within 24 hours', 'action': 'Get professional medical evaluation'},
                {'timeframe': 'Day 2-3', 'action': 'Follow prescribed treatment plan'},
                {'timeframe': 'Day 7', 'action': 'Follow-up appointment if symptoms persist'}
            ]
        elif self.severity == 'moderate':
            timeline = [
                {'timeframe': 'Today', 'action': 'Start recommended precautions and rest'},
                {'timeframe': 'Within 2-3 days', 'action': 'Schedule doctor appointment'},
                {'timeframe': 'Day 5-7', 'action': 'Reassess symptoms. Seek help if worse'},
                {'timeframe': 'After recovery', 'action': 'Review preventive measures'}
            ]
        else:
            timeline = [
                {'timeframe': 'Today', 'action': 'Begin home care and rest'},
                {'timeframe': 'Days 1-3', 'action': 'Monitor symptoms daily'},
                {'timeframe': 'Day 3-5', 'action': 'If no improvement, consult doctor'},
                {'timeframe': 'After recovery', 'action': 'Maintain healthy habits'}
            ]
        
        return timeline
    
    def _generate_follow_up_questions(self):
        """Generate relevant follow-up questions for better assessment"""
        questions = {
            'severity_assessment': [],
            'lifestyle': [],
            'medical_history': [],
        }
        
        # Severity assessment questions
        questions['severity_assessment'] = [
            {
                'question': 'How long have you been experiencing these symptoms?',
                'options': ['Less than 24 hours', '1-3 days', '4-7 days', 'More than a week'],
                'importance': 'high',
                'helps_determine': 'Whether condition is acute or chronic'
            },
            {
                'question': 'Are your symptoms getting worse, staying the same, or improving?',
                'options': ['Getting worse', 'Staying the same', 'Improving', 'Fluctuating'],
                'importance': 'high',
                'helps_determine': 'Disease progression and urgency'
            },
            {
                'question': 'On a scale of 1-10, how much do these symptoms affect your daily activities?',
                'options': ['1-3 (Mild)', '4-6 (Moderate)', '7-9 (Severe)', '10 (Unable to function)'],
                'importance': 'high',
                'helps_determine': 'Impact on quality of life'
            }
        ]
        
        # Lifestyle questions
        questions['lifestyle'] = [
            {
                'question': 'Have you traveled recently (in the last 2 weeks)?',
                'options': ['Yes, within country', 'Yes, internationally', 'No'],
                'importance': 'medium',
                'helps_determine': 'Exposure to regional diseases'
            },
            {
                'question': 'Are you currently taking any medications or supplements?',
                'options': ['Yes, prescription medications', 'Yes, over-the-counter', 'Yes, herbal/traditional', 'No'],
                'importance': 'high',
                'helps_determine': 'Potential drug interactions or contraindications'
            }
        ]
        
        # Medical history
        questions['medical_history'] = [
            {
                'question': 'Do you have any chronic health conditions?',
                'options': ['Diabetes', 'Hypertension', 'Heart disease', 'Asthma', 'None'],
                'importance': 'high',
                'helps_determine': 'Comorbidities that may complicate treatment'
            },
            {
                'question': 'Has anyone in your household or close contacts had similar symptoms?',
                'options': ['Yes, currently', 'Yes, recently', 'No'],
                'importance': 'medium',
                'helps_determine': 'Contagious disease spread risk'
            }
        ]
        
        # Disease-specific questions
        disease_specific = self._get_disease_specific_questions()
        if disease_specific:
            questions['disease_specific'] = disease_specific
        
        return questions
    
    def _get_disease_specific_questions(self):
        """Get questions specific to the predicted disease"""
        disease_questions = {
            'Diabetes': [
                {
                    'question': 'Have you noticed increased thirst or frequent urination?',
                    'options': ['Yes, both', 'Yes, thirst only', 'Yes, urination only', 'No'],
                    'importance': 'high'
                }
            ],
            'Hypertension': [
                {
                    'question': 'Have you measured your blood pressure recently?',
                    'options': ['Yes, it was high', 'Yes, it was normal', 'No'],
                    'importance': 'high'
                }
            ],
            'Malaria': [
                {
                    'question': 'Are you experiencing fever with chills?',
                    'options': ['Yes, with shaking', 'Yes, mild chills', 'Fever only', 'No fever'],
                    'importance': 'high'
                }
            ],
            'Hepatitis B': [
                {
                    'question': 'Have you noticed yellowing of your skin or eyes?',
                    'options': ['Yes, both', 'Yes, eyes only', 'Yes, skin only', 'No'],
                    'importance': 'high'
                }
            ]
        }
        
        return disease_questions.get(self.predicted_disease, [])
    
    def _identify_risk_factors(self):
        """Identify specific risk factors for the user"""
        risk_factors = []
        
        # Age-related risks
        if self.age < 5 or self.age >= 65:
            risk_factors.append({
                'factor': 'Age',
                'level': 'high',
                'description': 'Age increases risk of complications',
                'mitigation': 'Closer medical monitoring recommended'
            })
        
        try:
            # Check user's previous conditions - WITHOUT created_at
            user_history = db.session.query(
                Predictions.predicted_disease,
                func.count(Predictions.id).label('count')
            ).filter(
                Predictions.user_id == self.user_id
            ).group_by(Predictions.predicted_disease).all()
            
            if len(user_history) >= 3:
                risk_factors.append({
                    'factor': 'Recurrent Health Issues',
                    'level': 'medium',
                    'description': 'Multiple health concerns detected in your history',
                    'mitigation': 'Consider comprehensive health checkup'
                })
        except Exception as e:
            print(f"⚠️ Warning: Could not fetch user history: {str(e)}")
        
        # Severity-based risk
        if self.severity == 'high':
            risk_factors.append({
                'factor': 'Symptom Severity',
                'level': 'high',
                'description': 'High number of symptoms indicates serious condition',
                'mitigation': 'Immediate medical attention required'
            })
        
        return risk_factors
    
    def _get_emergency_indicators(self):
        """Define when to seek immediate emergency help"""
        emergency_signs = {
            'general': [
                'Difficulty breathing or shortness of breath',
                'Chest pain or pressure',
                'Severe abdominal pain',
                'Sudden confusion or difficulty staying awake',
                'High fever (above 103°F/39.4°C) that doesn\'t respond to medication',
                'Severe headache with stiff neck',
                'Uncontrolled bleeding',
                'Signs of severe dehydration'
            ]
        }
        
        # Disease-specific emergency signs
        disease_emergencies = {
            'Diabetes': [
                'Blood sugar below 70 mg/dL or above 300 mg/dL',
                'Loss of consciousness',
                'Severe confusion or unusual behavior'
            ],
            'Heart attack': [
                'Any chest discomfort - CALL EMERGENCY IMMEDIATELY',
                'Pain spreading to arm, jaw, or back',
                'Cold sweat'
            ],
            'Hepatitis B': [
                'Severe jaundice (yellowing)',
                'Confusion or drowsiness',
                'Bleeding or bruising easily',
                'Swollen abdomen'
            ],
            'Malaria': [
                'Severe headache with high fever',
                'Persistent vomiting',
                'Difficulty breathing'
            ]
        }
        
        specific_signs = disease_emergencies.get(self.predicted_disease, [])
        
        return {
            'general_warning_signs': emergency_signs['general'],
            'disease_specific_signs': specific_signs,
            'emergency_action': 'If you experience ANY of these signs, seek emergency medical help immediately or call emergency services.'
        }


# Integration function for the predict route
def get_smart_recommendations(user_id, predicted_disease, symptoms_count, gender, age, location):
    """
    Main function to call from predict route
    """
    try:
        engine = SmartRecommendationEngine(
            user_id=user_id,
            predicted_disease=predicted_disease,
            symptoms_count=symptoms_count,
            gender=gender,
            age=age,
            location=location
        )
        
        return engine.generate_recommendations()
    except Exception as e:
        print(f"❌ Error generating recommendations: {str(e)}")
        # Return basic fallback recommendations
        return {
            'urgency_level': 'moderate',
            'primary_actions': [{
                'priority': 1,
                'action': 'Consult a healthcare provider',
                'reason': 'For proper diagnosis and treatment',
                'urgency': 'Recommended'
            }],
            'demographic_specific': [],
            'location_alerts': [],
            'timeline': [
                {'timeframe': 'Today', 'action': 'Start recommended precautions'},
                {'timeframe': 'Within 2-3 days', 'action': 'Schedule doctor appointment'}
            ],
            'follow_up_questions': {
                'severity_assessment': [],
                'lifestyle': [],
                'medical_history': []
            },
            'risk_factors': [],
            'when_to_seek_help': {
                'general_warning_signs': ['Difficulty breathing', 'Severe pain', 'High fever'],
                'disease_specific_signs': [],
                'emergency_action': 'Seek emergency medical help if symptoms worsen.'
            }
        }


# Database model for storing follow-up responses
try:
    from models.user_model import db
    
    class FollowUpResponses(db.Model):
        __tablename__ = 'followup_responses'
        
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
        prediction_id = db.Column(db.Integer, db.ForeignKey('predictions.id'), nullable=False)
        question = db.Column(db.String(500), nullable=False)
        answer = db.Column(db.String(500), nullable=False)
        category = db.Column(db.String(100))
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        
        user = db.relationship('User', backref='followup_responses')
        prediction = db.relationship('Predictions', backref='followup_responses')
except Exception as e:
    print(f"⚠️ Warning: Could not create FollowUpResponses model: {str(e)}")