from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_bcrypt import Bcrypt

#from models.user_model import register_user_sqlalchemy, authenticate_user_sqlalchemy
from models.user_model import User
from extensions import db
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import secrets
from itsdangerous import URLSafeTimedSerializer

bp = Blueprint('auth', __name__)  # Create a blueprint for authentication routes
bcrypt = Bcrypt()

bcrypt = Bcrypt()

# Register user with basic info (demographics can be added later)
def register_user(username, email, password):
    try:
        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            print(f"❌ User already exists: {existing_user.username} or {existing_user.email}")
            return False
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, email=email, password=hashed_password)
        # Demographic fields (age, gender, location, region) remain null for now
        
        db.session.add(new_user)
        db.session.commit()
        
        print(f"✅ User '{username}' registered successfully!")
        return True
        
    except IntegrityError:
        db.session.rollback()
        print("❌ Integrity error - user already exists")
        return False
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        db.session.rollback()
        print(f"❌ Unexpected error: {e}")
        return False

# Authenticate user
def authenticate_user(email, password):
    try:
        user = User.query.filter_by(email=email).first()
        
        if user:
            print(f"🔍 Found user: {user.username}")
            if bcrypt.check_password_hash(user.password, password):
                print(f"✅ Authentication successful for {user.username}")
                return {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'age': user.age,
                    'gender': user.gender,
                    'location': user.location,
                    'region': user.region
                }
            else:
                print("❌ Password mismatch")
        else:
            print("❌ No user found with that email")
            
        return None
        
    except SQLAlchemyError as e:
        print(f"❌ Database error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

# Update user demographics (can be called after registration)
def update_user_demographics(user_id, age, gender, location, region):
    try:
        user = User.query.get(user_id)
        if not user:
            print(f"❌ User with ID {user_id} not found")
            return False
            
        user.age = age
        user.gender = gender
        user.location = location
        user.region = region
        
        db.session.commit()
        print(f"✅ Demographics updated for user {user.username}")
        return True
        
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"❌ Database error updating demographics: {e}")
        return False
    except Exception as e:
        db.session.rollback()
        print(f"❌ Unexpected error updating demographics: {e}")
        return False

# Get user profile including demographics
def get_user_profile(user_id):
    try:
        user = User.query.get(user_id)
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'age': user.age,
                'gender': user.gender,
                'location': user.location,
                'region': user.region,
                'created_at': user.created_at
            }
        return None
    except Exception as e:
        print(f"❌ Error getting user profile: {e}")
        return None


@bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('dashboard.login'))




# 🔐 Secret key for generating secure tokens
s = URLSafeTimedSerializer("your_secret_key")

# ✅ Step 1: Forgot Password Route
@bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip()
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("No account found with that email.", "danger")
            return redirect(url_for('auth.forgot_password'))

        # Generate reset token
        token = s.dumps(email, salt="reset-password")

        # ✅ Store token in session (Temporary for demo)
        session['reset_token'] = token

        # ✅ Redirect to the reset password page with the token
        return redirect(url_for('auth.reset_password', token=token))

    return render_template('forgot_password.html')


# ✅ Step 2: Reset Password Route
@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt="reset-password", max_age=1800)  # Valid for 30 minutes
    except:
        flash("Invalid or expired token!", "danger")
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password = request.form['password'].strip()
        hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')

        user = User.query.filter_by(email=email).first()
        if user:
            user.password = hashed_password
            db.session.commit()
            flash("Your password has been reset! Please log in.", "success")
            return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)

