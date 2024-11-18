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
    # serve a preservare nome e docstring della wrapped function (quindi login e registrazione) utile esempio per il debug
    @wraps(function)
    # è la vera funzione wrapper che sostituisce quella originale quando applichiamo il decoratore a una rotta,gli argomenti *args e **kwargs passano qualsiasi parametro dalla funzione originale alla wrapper.
    def check_authentication(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))
        else:
            return function(*args, **kwargs)
    return check_authentication

@auth_bp.route('/register', methods=['GET', 'POST'])
@redirect_authenticated_user
def register():
    if request.method == "POST":
        # prendere username e password dai form
        hash = generate_password_hash(request.form['password'])
        print(hash)
        user = User(
            username = request.form['username'].lower(),
            password = hash
        )
        query_check = db.session.execute(
            select(exists().where(User.username == user.username))).scalar()
        # print(query_check)
        if query_check:
            flash('Username già esistente')
            return redirect(url_for('auth.register'))
        else:
            db.session.add(user)
            db.session.commit()
            #invio_email_di_verifica(user.username)
        return render_template('signup.html')

    return render_template('signup.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
@redirect_authenticated_user
def login():
    if request.method == "POST":
        username = request.form['username'].lower()
        password = request.form['password']

        # restituisce il primo risultato trovato, se non vi è alcun risultato genera un errore 404
        user = db.first_or_404(db.select(User).filter_by(username=username))
        validate = check_password_hash(user.password, password)
        print(validate)
        print(user.is_active)
        if validate == True and user.is_active == True:
            login_user(user)
            return redirect(url_for('main.dashboard'))
        else:
            flash('Email o password non valide')
            redirect(url_for('auth.login'))

    return render_template('signin.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/auth/login')


@auth_bp.route('/verify/<token>')  # GET
def verify_email(token):
    email = conferma_token(token)  # Decodifico il token per ottenere l'email
    
    if not email:
        return redirect(url_for('auth.register'))
    # Recupera l'utente dal database usando l'email decodificata da conferma_token
    user = db.session.execute(select(User).filter_by(
        username=email)).scalar_one_or_none()

    if user is None:
        # flash("Utente non trovato.", "danger")
        print('utente non trovato')
        return redirect(url_for('auth.register'))

    if user.is_active:
        # flash("Account già verificato. Puoi effettuare il login.", "info")
        print('account già verificato')
    else:
        # Imposto is_active a True e committo
        user.is_active = True
        db.session.commit()
        # flash("Account verificato con successo! Ora puoi effettuare il login.", "success")
        print('Account verificato con successo! Ora puoi effettuare il login.')

    return redirect(url_for('login'))

s = URLSafeTimedSerializer("secret-key")

def genera_token_di_verifica(email):
    return s.dumps(email, salt='email-confirmation')


def conferma_token(token, expiration=600):
    try:
        email = s.loads(token, salt='email-confirmation', max_age=expiration)
    except Exception as e:
        return False
    return email

#def invio_email_di_verifica(user_email):
#    token = genera_token_di_verifica(user_email)
#    url_di_verifica = url_for('verify_email', token=token, _external=True)
#    subject = "Conferma email"
#    html_body = render_template(
#        'verifica_email.html', url_di_verifica=url_di_verifica)
#    msg = Message(subject=subject, sender='antoniolakee13@gmail.com',
#                  recipients=[user_email], html=html_body)
#    mail.send(msg)