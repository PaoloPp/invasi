from flask import render_template, redirect, url_for, request, flash, jsonify, send_file, Blueprint
from flask_login import login_required, current_user
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from io import StringIO
import os, shutil, json

from models import db, User, JsonFile
from utilities import get_json, round_floats, plot_values, set_year, get_user_files, get_past_exchange, process_data

main_bp = Blueprint('main', __name__)

def load_json_data(filename):
    """
    Helper to load and parse JSON data.
    Returns a dict on success, or None (with a flash message) on failure.
    """
    try:
        json_data = get_json(filename)
        return json.loads(json_data)
    except json.JSONDecodeError as e:
        flash(f"Error parsing JSON from {filename}: {e}", "danger")
        return None

@main_bp.route('/', methods=['GET'])
def index():
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    files = get_user_files()
    if request.method == 'POST':
        filename = request.form.get("data_select")
        if filename:
            data = load_json_data(filename)
            if not data:
                return redirect(url_for('main_bp.dashboard'))
            data = round_floats(data)
            months = set_year(data.get("Mese di partenza"))
            plot_values(
                ["Aitot*", "Etot*", "W*", "Sf 1*", "D/S 1*", "Winv tot", "Wo"],
                data, "caso1"
            )
            plot_values(
                ["Aitot*", "Etot*", "W*", "Sf 2*", "D/S 2*", "Winv aut", "Wo"],
                data, "caso2"
            )
            return render_template('dashboard.html', data=data, months=months, files=files,
                                   plotA="caso1_plot.png", plotB="caso2_plot.png")
    return render_template('dashboard.html', data=None, files=files)

@main_bp.route('/form', methods=['GET', 'POST'])
@login_required
def form():
    files = get_user_files()
    data = {}
    if request.method == 'POST':
        if 'load' in request.form:
            filename = request.form.get("data_select")
            if filename:
                data = load_json_data(filename)
                return render_template('form.html', files=files, data=data)
        elif 'delete' in request.form:
            filename = request.form.get("data_select")
            if filename:
                file_to_delete = db.session.execute(
                    select(JsonFile).filter(
                        JsonFile.user_id == current_user.id,
                        JsonFile.filename == filename
                    )
                ).scalar()
                if file_to_delete:
                    db.session.delete(file_to_delete)
                    try:
                        db.session.commit()
                        flash(f'File "{filename}" deleted successfully!', 'success')
                    except SQLAlchemyError:
                        db.session.rollback()
                        flash("Database error occurred while deleting file.", "danger")
                else:
                    flash(f'File "{filename}" not found.', 'danger')
            return redirect(url_for('main.form'))
        else:
            if current_user.is_authenticated:
                json_filename = request.form.get('filename')
                data = process_data(request)
                existing_file = db.session.execute(
                    select(JsonFile).filter(
                        JsonFile.user_id == current_user.id,
                        JsonFile.filename == json_filename
                    )
                ).scalar_one_or_none()
                if existing_file:
                    existing_file.json_data = json.dumps(data)
                else:
                    json_file = JsonFile(
                        filename=json_filename,
                        json_data=json.dumps(data),
                        user_id=current_user.id
                    )
                    db.session.add(json_file)
                try:
                    db.session.commit()
                    flash('Form successfully submitted!', 'success')
                except SQLAlchemyError:
                    db.session.rollback()
                    flash("Database error occurred while submitting the form.", "danger")
                return redirect(url_for('main.form'))
    return render_template('form.html', data=data, files=files)

@main_bp.route('/exchange', methods=['GET', 'POST'])
@login_required
def exchange():
    files = get_user_files()
    past_exchange = get_past_exchange()
    data = {}
    surplus_sum = 0
    deficit_sum = 0
    total = 0
    if request.method == 'POST':
        selected_files = request.form.getlist('selected_files')
        if selected_files:
            data, surplus_sum, deficit_sum, total = calculate_exchange(selected_files)
            calculated_data1, calculated_data2 = split_json_by_deficit_surplus(selected_files)
        return render_template('exchange.html', files=files, data=data,
                               surplus_sum=surplus_sum, deficit_sum=deficit_sum, 
                               calculated_data1=calculated_data1, calculated_data2=calculated_data2,
                               total=total)


    return render_template('exchange.html', past_exchange = past_exchange, files=files, data=None,
                           surplus_sum=0, deficit_sum=0, total=0)

def calculate_exchange(file_list):
    """
    Process files to calculate exchange values.
    """
    sf_data = {}
    surplus_sum = 0
    deficit_sum = 0
    for filename in file_list:
        data = load_json_data(filename)
        if not data:
            continue
        key = data.get("Filename", filename)
        sf_data[key] = {
            "Sf 1 avg": data.get("Sf 1 avg"),
            "Sf 2 avg": data.get("Sf 2 avg"),
            "D/S 1 avg": data.get("D/S 1 avg"),
            "D/S 2 avg": data.get("D/S 2 avg")
        }
        ds1_avg = data.get("D/S 1 avg", 0)
        if ds1_avg > 0:
            surplus_sum += ds1_avg
        elif ds1_avg < 0:
            deficit_sum += ds1_avg

    total = round_floats(surplus_sum + deficit_sum)
    return round_floats(sf_data), round_floats(surplus_sum), round_floats(deficit_sum), total

def split_json_by_deficit_surplus(file_list):
    """
    Separates JSON files into positive and negative D/S lists and calls the appropriate outflow.
    """
    positive_entries = []
    negative_entries = []
    sum_positive_ds = 0
    sum_negative_ds = 0
    count_positive = 0
    count_negative = 0

    for filename in file_list:
        data = load_json_data(filename)
        if data and "D/S 1*" in data and isinstance(data["D/S 1*"], list) and data["D/S 1*"]:
            #For each file, get the last value of D/S 1* to determine
            #whether it is a surplus or deficit
            last_value = data["D/S 1*"][-1]
            entry = {"Filename": data.get("Filename", filename), "Data": last_value}
            if last_value > 0:
                positive_entries.append(entry)
                sum_positive_ds += last_value
                count_positive += 1
            elif last_value < 0:
                negative_entries.append(entry)
                sum_negative_ds += last_value
                count_negative += 1

    if count_positive == 0:
        positive_entries.append({"Filename": "No data", "Data": 0})
    if count_negative == 0:
        negative_entries.append({"Filename": "No data", "Data": 0})

    surplus = [positive_entries, sum_positive_ds, count_positive]
    deficit = [negative_entries, sum_negative_ds, count_negative]

    if surplus[1] >= abs(deficit[1]): #Check the sum of surplus is bigger then deficit
        calculated_data1, calculated_data2 = outflowA(surplus, deficit)
    elif surplus[1] < abs(deficit[1]):
        calculated_data1, calculated_data2 = outflowB(surplus, deficit)
    
    return calculated_data1, calculated_data2

def outflowA(surplus, deficit):
    """
    Processes outflow scenario A.
    """

    calculated_data1 = criteria_a1(surplus, deficit)
    calculated_data2 = criteria_a2(surplus, deficit)
    return calculated_data1, calculated_data2

def criteria_a1(surplus, deficit):
    # Assuming surplus[0] is a list of dictionaries each containing a "Filename" key
    k_a = [0] * 12
    edj_tot = 0
    surplus_tmp = surplus
    deficit_tmp = deficit
    calculated_data1 = []
    if surplus_tmp[2] > 0:
        for entry in surplus_tmp[0]:
            if entry.get("Filename"):
                json_data = load_json_data(entry.get("Filename"))
                if json_data:
                    # Calculate sum of positive values in "D/S 1 j" for 12 months
                    sum_surplus = sum(
                        json_data["D/S 1 j"][i] for i in range(12) if json_data["D/S 1 j"][i] > 0
                    )
                    try:
                        alpha_value =  json_data["D/S 1*"][11] / sum_surplus 
                    except (IndexError, ZeroDivisionError):
                        alpha_value = 0

                    # Store computed alpha value and the monthly computed values in the dictionary
                    entry["alpha"] = alpha_value
                    entry["alpha_surplus"] = []
                    for i in range(12):
                        if json_data["D/S 1 j"][i] > 0:
                            entry["alpha_surplus"].append(json_data["D/S 1 j"][i] * alpha_value)
                            edj_tot += json_data["D/S 1 j"][i] * alpha_value
                            k_a[i] = 1
                        else:
                            entry["alpha_surplus"].append(0)
                    
                    calculated_data1.append(entry)

    if deficit_tmp[2] > 0:
        for entry in deficit_tmp[0]:
            if entry.get("Filename"):
                json_data = load_json_data(entry.get("Filename"))
                if json_data:
                    # Calculate sum of positive values in "D/S 1 j" for 12 months
                    sum_deficit = sum(
                        json_data["D/S 1 j"][i] for i in range(12) if json_data["D/S 1 j"][i] < 0
                    )
                    
                    try:
                        alpha_value = json_data["D/S 1*"][11] / deficit[1]
                    except (IndexError, ZeroDivisionError):
                        alpha_value = 0

                    # Store computed alpha value and the monthly computed values in the dictionary
                    entry["alpha"] = alpha_value
                    entry["alpha_deficit"] = [
                        edj_tot * alpha_value if k_a[i] == 1 else 0 for i in range(12)
                    ]
                    calculated_data1.append(entry)

    calculated_data1 = round_floats(calculated_data1)
    return calculated_data1

def criteria_a2(surplus, deficit):
    # Assuming surplus[0] is a list of dictionaries each containing a "Filename" key
    k_b = [0] * 12
    adj_tot = 0
    surplus_tmp = surplus
    deficit_tmp = deficit
    calculated_data2 = []
    if deficit_tmp[2] > 0:
        for entry in deficit_tmp[0]:
            if entry.get("Filename"):
                json_data = load_json_data(entry.get("Filename"))
                if json_data:
                    # Calculate sum of positive values in "D/S 1 j" for 12 months
                    sum_deficit = sum(
                        json_data["D/S 1 j"][i] for i in range(12) if json_data["D/S 1 j"][i] < 0
                    )
                    
                    try:
                        alpha_value = json_data["D/S 1*"][11] / sum_deficit
                    except (IndexError, ZeroDivisionError):
                        alpha_value = 0

                    # Store computed alpha value and the monthly computed values in the dictionary
                    entry["alpha"] = alpha_value
                    entry["alpha_deficit"] = []
                    for i in range(12):
                        if json_data["D/S 1 j"][i] < 0:
                            entry["alpha_deficit"].append(abs(json_data["D/S 1 j"][i] * alpha_value))
                            adj_tot = abs(json_data["D/S 1 j"][i] * alpha_value)
                            k_b[i] = 1
                        else:
                            entry["alpha_deficit"].append(0)

                    calculated_data2.append(entry)

    if surplus_tmp[2] > 0:
        for entry in surplus_tmp[0]:
            if entry.get("Filename"):
                json_data = load_json_data(entry.get("Filename"))
                if json_data:
                    # Calculate sum of positive values in "D/S 1 j" for 12 months
                    sum_surplus = sum(
                        json_data["D/S 1 j"][i] for i in range(12) if json_data["D/S 1 j"][i] > 0
                    )
                    try:
                        alpha_value =  json_data["D/S 1*"][11] / surplus[1]
                    except (IndexError, ZeroDivisionError):
                        alpha_value = 0

                    # Store computed alpha value and the monthly computed values in the dictionary
                    entry["alpha"] = alpha_value
                    entry["alpha_surplus"] = [
                        adj_tot * alpha_value if k_b[i] == 1 else 0 for i in range(12)
                    ]
                    calculated_data2.append(entry)
    calculated_data2 = round_floats(calculated_data2)
    return calculated_data2
    
def criterio_a3(surplus, deficit, lambda_value):
    calculated_data3 = []
    surplus_tmp = surplus
    deficit_tmp = deficit
    lambda_surplus = lambda_value
    lambda_deficit = 1 - lambda_value

    return calculated_data3

def outflowB(surplus, deficit):
    """
    Processes outflow scenario B.
    """
    print("Outflow B")
    #calculated_data = criteria_a1(surplus, deficit)
    #return calculated_data