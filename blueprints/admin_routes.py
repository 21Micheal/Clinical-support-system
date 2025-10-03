from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models.user_model import User # Ensure Users model exists
from sqlalchemy import text
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ✅ Middleware to restrict access to admin pages
@admin_bp.before_request
def restrict_to_admin():
    allowed_routes = ['admin.admin_login']
    if request.endpoint not in allowed_routes and not session.get('admin_logged_in'):
        flash("Unauthorized access!", "danger")
        return redirect(url_for('admin.admin_login'))


# ✅ Admin Master Password (store securely in an environment variable)
ADMIN_MASTER_PASSWORD = os.getenv('ADMIN_MASTER_PASSWORD', 'SuperSecret123')


# ✅ Admin Login Page (Uses Master Password)
@admin_bp.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        admin_password = request.form.get('admin_password', '')

        if admin_password == ADMIN_MASTER_PASSWORD:
            session['admin_logged_in'] = True  # ✅ Set admin session
            flash("Welcome Admin!", "success")
            return redirect(url_for('admin.admin_dashboard'))
        else:
            flash("Invalid master password!", "danger")

    return render_template('admin_login.html')


# ✅ Admin Logout
@admin_bp.route('/admin_logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Admin logged out successfully.", "info")
    return redirect(url_for('admin.admin_login'))


# ✅ Admin Dashboard (View All Users)
@admin_bp.route('/')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        flash("Unauthorized access!", "danger")
        return redirect(url_for('admin.admin_login'))

    users = User.query.all()  # Fetch all users
    return render_template('admin.html', users=users)


# ✅ Delete a User
@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if not session.get('admin_logged_in'):
        flash("Unauthorized access!", "danger")
        return redirect(url_for('admin.admin_login'))

    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash("User deleted successfully.", "success")
    else:
        flash("User not found.", "danger")

    return redirect(url_for('admin.admin_dashboard'))
