from flask import render_template, redirect, url_for, request, flash, jsonify, send_file, Blueprint
from flask_login import login_required, current_user
from models import db, User  # Assuming models.py contains the User model
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from io import StringIO
from models import JsonFile, User
from utilities import get_json, round_floats, plot_values, set_year, get_user_files, process_data
import os
import shutil
import json

main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=['GET'])
def index():
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    # files = retrive_files()
    files = get_user_files()
    # You can pass dynamic data here for the dashboard
    if request.method == 'POST':
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
    

@main_bp.route('/form', methods=['GET', 'POST'])
@login_required
def form():
    # files = retrive_files()
    files = get_user_files()
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
    

@main_bp.route('/exchange', methods=['GET', 'POST'])
@login_required
def exchange():
    return render_template('exchange.html')