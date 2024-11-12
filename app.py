# import numpy as np
import os
import matplotlib
import matplotlib.pyplot as plt
# import pandas as pd
import simplejson as json
from http import HTTPStatus
from flask import Flask, render_template, request, flash, redirect, url_for, abort
from itertools import cycle
from decimal import Decimal, getcontext
from set_year import set_year
from round_floats import round_floats
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Integer, String, Column, exists, select, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from flask_login import LoginManager, login_user, UserMixin, login_required, logout_user, current_user
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from functools import wraps
import secret as s

matplotlib.use('Agg')
app = Flask(__name__)
app.secret_key = 'supersecretkey'

################
# configuro flask mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = s.MAIL_USERNAME
app.config['MAIL_PASSWORD'] = s.MAIL_PASSWORD
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)
# configuro sqlalchemy e creo l'ogetto db

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///invasi.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


class Base(DeclarativeBase):
    pass


# Gestione connessione DB
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.unauthorized_handler
def unauthorized():
    if request.blueprint == 'api':
        abort(HTTPStatus.UNAUTHORIZED)
    return redirect(url_for('login'))


# creo i modelli del database
class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String(25), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)


class JsonFile(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(
        String(120), nullable=True, unique=True)
    json_data: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), nullable=False)


@login_manager.user_loader
def loader_user(user_id):
    return User.query.get(user_id)


s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# Invia mail di verifica


def genera_token_di_verifica(email):
    return s.dumps(email, salt='email-confirmation')


def conferma_token(token, expiration=600):
    try:
        email = s.loads(token, salt='email-confirmation', max_age=expiration)
    except Exception as e:
        return False
    return email


def invio_email_di_verifica(user_email):
    token = genera_token_di_verifica(user_email)
    url_di_verifica = url_for('verify_email', token=token, _external=True)
    subject = "Conferma email"
    html_body = render_template(
        'verifica_email.html', url_di_verifica=url_di_verifica)
    msg = Message(subject=subject, sender='antoniolakee13@gmail.com',
                  recipients=[user_email], html=html_body)
    mail.send(msg)

################


def plot_values(_label, _data, _name):
    ldata = _data.copy()
    x = range(1, 13)
    for d in _label:
        if (isinstance(ldata[d], float) == True):
            ldata[d] = [ldata[d]]*12
        plt.plot(x, ldata[d], label=d)
    # `ncol` controls the number of columns in the legend
    plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4)
    plt.subplots_adjust(bottom=0.25)  # Add space at the bottom for the legend
    plt.savefig(f"static/{_name}_plot.png", format='png', dpi=150)
    plt.close()


def somma_cumulata(_var):
    cumulata = []
    somma = 0
    for i in range(0, len(_var)):
        somma += float(_var[i])
        cumulata.append(somma)
    return cumulata


def coeff(_nominalValue, _varCoeff):  # Ai, A'i, Ditot, Eipot, Eiirr, Eiind
    coeffValue = float(_nominalValue) * float(_varCoeff)
    return coeffValue


def retrive_files():
    files = os.listdir("elaborazioni")
    files = [f for f in files if f.endswith('.json')]
    return files

# Recupera i file associati all'utente in sessione dal DB


def get_user_files():
    return db.session.execute(db.select(JsonFile.filename).filter_by(user_id=current_user.id)).scalars().all()

# recupera il contenuto ndel campo json__data utilizzando il nome del file


def get_json(filename_selected):
    return db.session.execute(db.select(JsonFile.json_data).filter_by(filename=filename_selected)).scalar()


def process_data(request):
    vol = ["S", "Winv tot", "Winv aut", "Wo", "A", "A'", "P ev",
           "P inf", "D ec", "E pot", "E irr", "E ind", "E tra"]
    keys = ["Cj(A)", "Cj(A')", "Cj(ev)", "Cj(inf)", "Cj(ec)",
            "Cj(pot)", "Cj(irr)", "Cj(ind)", "Cj(tra)"]
    outj = ["A", "A'", "P ev", "P inf", "D ec",
            "E pot", "E irr", "E ind", "E tra"]
    out = ["A*", "A'*", "P ev*", "P inf*", "D ec*",
           "E pot*", "E irr*", "E ind*", "E tra*"]
    data = {}
    values_tot = []
    values_aitot = []
    values_wi = []
    values_Wi = []
    values_Wistar = []
    values_Wi1 = []
    values_Wi2 = []
    values_sf1 = []
    values_sf2 = []
    values_deficit1 = []
    values_deficit2 = []
    data["Filename"] = request.form.get("filename")
    data["Mese di partenza"] = request.form.get('starting_month')
    data["A tra"] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    data["A* tra"] = somma_cumulata(data["A tra"])

    for v in vol:
        data[v] = float(request.form.get(f'vol-{vol.index(v) + 1}'))
    for k in keys:
        values = []
        for i in range(1, 13):
            values.append(float(request.form.get(
                f'coeff-{i}-{keys.index(k) + 1}')))
        data[k] = values
    for k, o in zip(keys, outj):
        values = []
        for i in range(0, 12):
            values.append(coeff(data[o], data[k][i]))
        data[o + " j"] = values
    for o, oj in zip(out, outj):
        data[o] = somma_cumulata(data[oj + " j"])
    for i in range(0, 12):
        values_tot.append(float(
            data["D ec j"][i] + data["E pot j"][i] + data["E irr j"][i] + data["E ind j"][i]))
    data["Etot j"] = values_tot
    data["Etot*"] = somma_cumulata(data["Etot j"])
    for i in range(0, 12):
        values_aitot.append(float(data["A j"][i] + data["A' j"][i]))
    data["Aitot j"] = values_aitot
    data["Aitot*"] = somma_cumulata(data["Aitot j"])
    for i in range(0, 12):
        wi = float(data["Aitot j"][i] - data["Etot j"][i])
        Wi = float(wi + float(data["Wo"]))
        values_wi.append(wi)
        values_Wi.append(Wi)
    data["w j"] = values_wi
    data["W j"] = values_Wi
    data["w*"] = somma_cumulata(data["w j"])
    for i in range(0, 12):
        values_Wistar.append(float(data["w*"][i] + data["Wo"]))
    data["W*"] = values_Wistar
    for i in range(0, 12):
        if (data["W*"][i] < data["Winv tot"]):
            values_Wi1.append(data["W*"][i])
        else:
            values_Wi1.append(data["Winv tot"])

        if (values_Wi1[i] < data["Winv tot"]) or (data["w j"][i] < 0):
            values_sf1.append(0)
        else:
            values_sf1.append(data["w j"][i])

        if (data["W*"][i] < data["Winv aut"]):
            values_Wi2.append(data["W*"][i])
        else:
            values_Wi2.append(data["Winv aut"])

        if (values_Wi2[i] < data["Winv aut"]) or (data["w j"][i] < 0):
            values_sf2.append('0')
        else:
            values_sf2.append(data["w j"][i])

        values_deficit1.append(float(data["w j"][i] - float(values_sf1[i])))
        values_deficit2.append(float(data["w j"][i] - float(values_sf1[i])))
    data["Wi 1*"] = values_Wi1
    data["Wi 2*"] = values_Wi2
    data["Sf 1"] = values_sf1
    data["Sf 2"] = values_sf2
    data["Sf 1*"] = somma_cumulata(data["Sf 1"])
    data["Sf 2*"] = somma_cumulata(data["Sf 2"])
    data["D/S 1 j"] = values_deficit1
    data["D/S 2 j"] = values_deficit2
    data["D/S 1*"] = somma_cumulata(data["D/S 1 j"])
    data["D/S 2*"] = somma_cumulata(data["D/S 2 j"])

    return data

# definisco il decorator che utilizzerò per evitare che un utente loggato (quindi in sessione) visualizzi pagine di login e registrazione


# wrapper function (wrapped function)
def redirect_authenticated_user(function):
    # serve a preservare nome e docstring della wrapped function (quindi login e registrazione) utile esempio per il debug
    @wraps(function)
    # è la vera funzione wrapper che sostituisce quella originale quando applichiamo il decoratore a una rotta,gli argomenti *args e **kwargs passano qualsiasi parametro dalla funzione originale alla wrapper.
    def check_authentication(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        else:
            return function(*args, **kwargs)
    return check_authentication

################


@app.route('/', methods=['GET', 'POST'])
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
            select(exists().where(User.username.lower() == user.username))).scalar()
        # print(query_check)
        if query_check:
            flash('Username già esistente')
            return redirect(url_for('register'))
        else:
            db.session.add(user)
            db.session.commit()
            invio_email_di_verifica(user.username)
        return render_template('signup.html')

    return render_template('signup.html')


@app.route('/verify/<token>')  # GET
def verify_email(token):

    email = conferma_token(token)  # Decodifico il token per ottenere l'email

    if not email:
        # flash("Il link di verifica è non valido o scaduto.", "danger")
        print('Il link di verifica è non valido o scaduto')
        return redirect(url_for('register'))

    user = db.session.execute(select(User).filter_by(
        username=email)).scalar_one_or_none()
    # Recupera l'utente dal database usando l'email decodificata da conferma_token

    if user is None:
        # flash("Utente non trovato.", "danger")
        print('utente non trovato')
        return redirect(url_for('register'))

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


@app.route("/login", methods=['GET', 'POST'])
@redirect_authenticated_user
def login():
    if request.method == "POST":
        username = request.form['username'].lower()
        password = request.form['password']

        # restituisce il primo risultato trovato, se non vi è alcun risultato genera un errore 404
        user = db.first_or_404(db.select(User).filter_by(username=username))
        validate = check_password_hash(user.password, password)
        print(validate)
        if validate == True and user.is_active == True:
            login_user(user)

            return redirect(url_for('dashboard'))
        else:
            flash('email o password non valide')
            redirect(url_for('login'))

    return render_template('signin.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

################


@app.route('/form', methods=['GET', 'POST'])
@login_required
def form():
    # files = retrive_files()
    files = get_user_files()
    getcontext().prec = 2
    data = {}
    if request.method == 'POST':
        if 'load' in request.form:
            filename = request.form.get("data_select")
            if filename:
                # with open(f"elaborazioni/{filename}", 'r') as json_file:
                #    data = json.load(json_file)
                json_data = get_json(filename)
                data = json.loads(json_data)
                # Render form with loaded data
                return render_template('form.html', files=files, data=data)
        elif 'delete' in request.form:
            # Eliminazione del file
            filename = request.form.get("data_select")
            if filename:
                # Recupera il file dal database e verifica se esiste
                file_to_delete = db.session.execute(select(JsonFile).filter(
                    JsonFile.user_id == current_user.id, JsonFile.filename == filename)).scalar()

                if file_to_delete:
                    db.session.delete(file_to_delete)
                    db.session.commit()
                    flash(
                        f'File "{filename}" eliminato con successo!', 'success')
                else:
                    flash(f'File "{filename}" non trovato.', 'danger')
                return redirect('form')
        else:
            # Creazione del file json all'interno della cartella elaborazioni
            # data = process_data(request)
            # with open("elaborazioni/" + request.form.get("filename") + ".json", 'w') as json_file:
            #    json.dump(data, json_file, indent=4)
            if current_user.is_authenticated:
                json_filename = request.form.get('filename')
                data = process_data(request)
                check_filename = db.session.execute(select(JsonFile).filter(
                    JsonFile.user_id == current_user.id, JsonFile.filename == json_filename)).scalar_one_or_none()
                if check_filename:

                    check_filename.json_data = json.dumps(data)
                    db.session.commit()
                    return redirect('form')
                else:
                    json_file = JsonFile(
                        filename=json_filename,
                        json_data=json.dumps(data),
                        user_id=current_user.id)
                    db.session.add(json_file)
                    db.session.commit()
                    flash('Form successfully submitted!', 'success')
                    return redirect('form')
    elif request.method == 'GET':
        return render_template('form.html', data=data, files=files)


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    # files = retrive_files()
    files = get_user_files()
    # You can pass dynamic data here for the dashboard
    if request.method == 'POST':
        # with open("elaborazioni/" + request.form.get('data_select'), 'r') as json_file:
        #    data = json.load(json_file)
        # data = round_floats(data)
        # months = set_year(data["Mese di partenza"])

        # plot_values(["Aitot*", "Etot*", "W*", "Sf 1*",
        #            "D/S 1*", "Winv tot", "Wo"], data, "caso1")
        # plot_values(["Aitot*", "Etot*", "W*", "Sf 2*",
        #            "D/S 2*", "Winv tot", "Wo"], data, "caso2")

        filename = request.form.get("data_select")
        if filename:
            json_data = get_json(filename)
            data = json.loads(json_data)
            data = round_floats(data)
            months = set_year(data["Mese di partenza"])
            print(data)

            plot_values(["Aitot*", "Etot*", "W*", "Sf 1*",
                        "D/S 1*", "Winv tot", "Wo"], data, "caso1")
            plot_values(["Aitot*", "Etot*", "W*", "Sf 2*",
                        "D/S 2*", "Winv tot", "Wo"], data, "caso1")
        return render_template('dashboard.html', data=data, months=months, files=files, plotA="caso1_plot.png", plotB="caso2_plot.png")
    elif request.method == 'GET':
        return render_template('dashboard.html', data=None, files=files)


def main():
    print("Hello World!")


if __name__ == "__main__":
    db.init_app(app)
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", debug=False)
    #app.run(debug=True)
