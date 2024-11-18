import sys
sys.path.append('../../')
from flask import Flask, render_template, request, flash, redirect, url_for, abort, send_file, Blueprint
from flask_login import login_required, current_user
from models import User
from extensions import db
import os
import shutil

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash("Access denied. Admins only.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    # Fetch all users from the database
    users = User.query.all()
    return render_template('admin_dashboard.html', users=users)


# User Management Route (Add, Update, Delete users)
@admin_bp.route('/users/<action>', methods=['POST'])
@admin_required
def manage_users(action):
    if action == "delete":
        user_id = request.form.get("user_id")
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
            flash("User deleted successfully.", "success")
        else:
            flash("User not found.", "warning")
    elif action == "add":
        # Implement user addition logic
        pass
    elif action == "update":
        # Implement user update logic
        pass
    return redirect(url_for('admin.admin_dashboard'))

# Export DB Route
@admin_bp.route('/export', methods=['GET'])
@admin_required
def export_db():
    # Define a path for the temporary copy of the database
    export_path = 'temp_export/invasi_export.db'
    
    # Ensure the temporary export directory exists
    os.makedirs('temp_export', exist_ok=True)

    # Copy the database to the export path
    shutil.copy2('var/app-instance/invasi.db', export_path)

    # Send the copied file as a download
    return send_file(export_path, as_attachment=True, download_name="invasi_export.db")
