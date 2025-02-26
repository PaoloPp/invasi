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
            plot_values(["Aitot*", "Etot*", "W*", "Sf 1*", "D/S 1*", "Winv tot", "Wo"], data, "caso1")
            plot_values(["Aitot*", "Etot*", "W*", "Sf 2*", "D/S 2*", "Winv aut", "Wo"], data, "caso2")
            
            
            

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
    data = {}
    if request.method == 'POST':
        
        surplus_sum = 0
        deficit_sum = 0
        total = 0
        print("Form data:", request.form)
        # Get the list of selected files from the form
        selected_files = request.form.getlist('selected_files')
        if selected_files:
            print("Selected files:", selected_files)  # This will show the selected files in the terminal
            data, surplus_sum, deficit_sum, total = calculate_exchange(selected_files)
            split_json_by_ds(selected_files)
            print(data)

        
        return render_template('exchange.html', files=get_user_files(), data=data, surplus_sum=surplus_sum, deficit_sum=deficit_sum, total=total)
        # Process the selected files or use them as needed
    # Render the template and pass files to the form
    return render_template('exchange.html', files=get_user_files(), data=None, surplus_sum=0, deficit_sum=0, total=0)


def calculate_exchange(_files):
    sf_data = {}
    surplus_sum = 0
    deficit_sum = 0
    total = 0
    for file in _files:
        json_data = get_json(file)
        data = json.loads(json_data)
        key = data["Filename"]
        sf_data[key] = {}
        sf_data[key]["Sf 1 avg"] = data["Sf 1 avg"]
        sf_data[key]["Sf 2 avg"] = data["Sf 2 avg"]
        sf_data[key]["D/S 1 avg"] = data["D/S 1 avg"]
        sf_data[key]["D/S 2 avg"] = data["D/S 2 avg"]
        if data["D/S 1 avg"] > 0:
            surplus_sum += data["D/S 1 avg"]
        elif data["D/S 1 avg"] < 0:
            deficit_sum += data["D/S 1 avg"]
    
    total = round_floats(surplus_sum + deficit_sum)
    surplus_sum = round_floats(surplus_sum)
    deficit_sum = round_floats(deficit_sum)
    sf_data = round_floats(sf_data)
    return sf_data, surplus_sum, deficit_sum, total

def split_json_by_ds(_files):
    surplus = []
    positive_ds = []
    sum_positive_ds = 0
    t = 0
    deficit = []
    negative_ds = []
    sum_negative_ds = 0
    v = 0

    for data in _files:
        json_data = get_json(data)
        data = json.loads(json_data)
        if "D/S 1*" in data and isinstance(data["D/S 1*"], list) and data["D/S 1*"]:
            last_value = data["D/S 1*"][-1]
            filename = data.get("Filename", "Unknown")
            entry = {"Filename": filename, "Data": last_value}
            
            if last_value > 0:
                positive_ds.append(entry)
                sum_positive_ds += last_value
                t += 1
            else:
                negative_ds.append(entry)
                sum_negative_ds += last_value
                v += 1


    if t == 0:
        positive_ds.append({"Filename": "No data", "Data": 0})
    if v == 0:
        negative_ds.append({"Filename": "No data", "Data": 0})
    
    surplus.append(positive_ds)
    surplus.append(sum_positive_ds) #Total sum of Surplus
    surplus.append(t)

    deficit.append(negative_ds)
    deficit.append(sum_negative_ds) #Total sum of Deficit
    deficit.append(v)


    print("Positive DS:", surplus[0])
    print("Negative DS:", deficit[0])

    if surplus[1] > deficit[1]:
        outflowA(surplus, deficit, _files)
    elif surplus[1] < deficit[1]:
        outflowB(surplus, deficit, _files)
    
    return surplus, deficit


def outflowA(_surplus, _deficit, _files):
    print("Outflow A")
    delta = _surplus[1] - _deficit[1]
    print("Delta:", delta)
    diff_monthly = []
    delta_monthly = []
    delta_suplus = []
    
    for surp in _surplus[0]:
        diff = []
        delt = []
        for file in _files:
            if surp["Filename"] == file:
                json_data = get_json(file)
                data = json.loads(json_data)
                
                #Calcolo fattore delta(i)
                delta_suplus = ((data["A*"][11] * data["Aitot*"][11])/delta)
                
                #Afflusso mensile - erogazioni mensili
                for i in range(12):
                    d = data["A j"][i] - data["E pot j"][i] - data["E irr j"][i] - data["E ind j"][i] - data["E tra j"][i]
                    diff.append(d) if d > 0 else diff.append(0)
                
                #Delta(i) "normalizzata"
                for i in range(12):
                    d = data["A j"][i] * diff[i] / delta_suplus
                    delt.append(d)
                
        diff_monthly.append(diff)
        delta_monthly.append(delt)
    print("Diff Monthly:", diff_monthly)
    print("Delta Monthly:", delta_monthly)





    return

def outflowB(_surplus, _deficit, _files):
    print("Outflow B")
    return 