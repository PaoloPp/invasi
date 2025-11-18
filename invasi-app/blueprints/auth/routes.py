# auth/routes.py
from flask import render_template, redirect, url_for, flash, request, Blueprint
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import exists, select
from itsdangerous import URLSafeTimedSerializer
from models import User
from extensions import db

auth_bp = Blueprint('auth', __name__, template_folder='../../templates')


def redirect_authenticated_user(function):
    """
    Decorator to redirect already authenticated users to the dashboard.
    """
    @wraps(function)
    def check_authentication(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))
        return function(*args, **kwargs)
    return check_authentication


@auth_bp.route('/register', methods=['GET', 'POST'])
@redirect_authenticated_user
def register():
    if request.method == "POST":
        # Get username and password from form, and hash the password
        password_hash = generate_password_hash(request.form['password'])
        user = User(
            username=request.form['username'].lower(),
            password=password_hash,
            is_active=True
        )
        # Check if username already exists
        query_check = db.session.execute(
            select(exists().where(User.username == user.username))
        ).scalar()
        if query_check:
            flash('Username already exists', 'warning')
            return redirect(url_for('auth.register'))
        else:
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('auth.login'))
    return render_template('signup.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
@redirect_authenticated_user
def login():
    if request.method == "POST":
        username = request.form['username'].lower()
        password = request.form['password']

        # Retrieve the user; first_or_404 will abort if not found
        user = db.first_or_404(db.select(User).filter_by(username=username))
        if check_password_hash(user.password, password) and user.is_active:
            login_user(user)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
    return render_template('signin.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/verify/<token>')
def verify_email(token):
    # Decode token to get the email
    email = conferma_token(token)
    if not email:
        flash('Verification link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.register'))
    
    # Retrieve the user using the email (here username is used to store the email)
    user = db.session.execute(select(User).filter_by(username=email)).scalar_one_or_none()
    if user is None:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.register'))

    if user.is_active:
        flash('Account already verified. Please log in.', 'info')
    else:
        user.is_active = True
        db.session.commit()
        flash('Account verified successfully! You can now log in.', 'success')
    
    return redirect(url_for('auth.login'))


# Token serializer setup (ideally use a configuration variable for the secret key)
s = URLSafeTimedSerializer("secret-key")


def genera_token_di_verifica(email):
    """Generates a verification token for the given email."""
    return s.dumps(email, salt='email-confirmation')


def conferma_token(token, expiration=600):
    """Confirms the token and returns the email if valid; otherwise, returns False."""
    try:
        email = s.loads(token, salt='email-confirmation', max_age=expiration)
    except Exception:
        return False
    return email

# def invio_email_di_verifica(user_email):
#     token = genera_token_di_verifica(user_email)
#     url_di_verifica = url_for('verify_email', token=token, _external=True)
#     subject = "Email Confirmation"
#     html_body = render_template('verifica_email.html', url_di_verifica=url_di_verifica)
#     msg = Message(subject=subject, sender='your_email@example.com',
#                   recipients=[user_email], html=html_body)
#     mail.send(msg)
