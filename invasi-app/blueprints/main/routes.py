from flask import render_template, redirect, url_for, request, flash, jsonify, send_file, Blueprint
from flask_login import login_required, current_user
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from io import StringIO
from collections import defaultdict
import copy
import json

# Import os for clearing the console just for debugging purposes
import os

from models import db, User, JsonFile, PastExchange
from utilities import *

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


def load_json_data_traverse(filename):
    """
    Helper to load and parse JSON data.
    Returns a dict on success, or None (with a flash message) on failure.
    """
    try:
        json_data = get_json_traverse(filename)
        return json.loads(json_data)
    except json.JSONDecodeError as e:
        flash(f"Error parsing JSON from {filename}: {e}", "danger")
        return None


def load_past_json_data(filename):
    """
    Helper to load and parse JSON data.
    Returns a dict on success, or None (with a flash message) on failure.
    """
    try:
        json_data = get_past_json(filename)
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
            return render_template('dashboard.html', filename=filename, data=data, months=months, files=files,
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
                        flash(
                            f'File "{filename}" deleted successfully!', 'success')
                    except SQLAlchemyError:
                        db.session.rollback()
                        flash(
                            "Database error occurred while deleting file.", "danger")
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
                    flash(
                        "Database error occurred while submitting the form.", "danger")

                return redirect(url_for('main.form'))
    return render_template('form.html', data=data, files=files)


@main_bp.route('/form_traverse', methods=['GET', 'POST'])
@login_required
def manage_traverse():
    files = get_user_files_traverse()
    data = {}
    if request.method == 'POST':
        if 'load' in request.form:
            filename = request.form.get("data_select")
            if filename:
                data = load_json_data_traverse(filename)
                return render_template('form_traverse.html', data=data, files=files)

        elif 'delete' in request.form:
            filename = request.form.get("data_select")
            if filename:
                file_to_delete = db.session.execute(
                    select(JsonFileTraverse).filter(
                        JsonFileTraverse.user_id == current_user.id,
                        JsonFileTraverse.filename == filename
                    )
                ).scalar()
                if file_to_delete:
                    db.session.delete(file_to_delete)
                    try:
                        db.session.commit()
                        flash(
                            f'File "{filename}" deleted successfully!', 'success')
                    except SQLAlchemyError:
                        db.session.rollback()
                        flash(
                            "Database error occurred while deleting file.", "danger")
                else:
                    flash(f'File "{filename}" not found.', 'danger')
            return redirect(url_for('main.manage_traverse'))
        else:
            if current_user.is_authenticated:
                json_filename = request.form.get('filename')
                data = process_data_traverse(request)

                existing_file = db.session.execute(
                    select(JsonFileTraverse).filter(
                        JsonFileTraverse.user_id == current_user.id,
                        JsonFileTraverse.filename == json_filename
                    )
                ).scalar_one_or_none()
                if existing_file:
                    existing_file.json_data = json.dumps(data)
                else:
                    json_file = JsonFileTraverse(
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
                    flash(
                        "Database error occurred while submitting the form.", "danger")

                return redirect(url_for('main.manage_traverse'))

    return render_template('form_traverse.html', data=data, files=files)


@main_bp.route('/exchange', methods=['GET', 'POST'])
@login_required
def exchange():
    files = get_user_files()
    traverse_files = get_user_files_traverse()
    past_exchange = get_past_exchange()
    data = {}
    surplus_sum = 0
    deficit_sum = 0
    total = 0
    if request.method == 'POST':
        if 'load' in request.form:
            filename = request.form.get("past_select")
            if filename:
                data = load_past_json_data(filename)
                print(data)
            calculated_data1 = data["calculated_data1"]
            calculated_data2 = data["calculated_data2"]
            calculated_data3 = data["calculated_data3"]
            comparison = data["comparison"]
            surplus_sum = data["surplus_sum"]
            deficit_sum = data["deficit_sum"]
            total = data["total"]
            traverse_data = data["traverse"]
            traverse_amount = data.get("traverse_amount", 0)
            data1 = data["data"]
            satisfiedA = data.get("satisfiedA", None)
            satisfiedB = data.get("satisfiedB", None)

            return render_template('exchange.html', filename=filename, data=data1,
                                   past_exchange=past_exchange, files=files, traverse_files=traverse_files,
                                   surplus_sum=surplus_sum, deficit_sum=deficit_sum,
                                   calculated_data1=calculated_data1, calculated_data2=calculated_data2,
                                   calculated_data3=calculated_data3, total=total,
                                   comparison1=comparison[0], comparison2=comparison[1], comparison3=comparison[2],
                                   traverse=traverse_data, traverse_tot=traverse_amount,
                                   satisfiedA=satisfiedA, satisfiedB=satisfiedB)
        if 'delete' in request.form:
            filename = request.form.get("past_select")
            if filename:
                file_to_delete = db.session.execute(
                    select(PastExchange).filter(
                        PastExchange.user_id == current_user.id,
                        PastExchange.filename == filename
                    )
                ).scalar()
                if file_to_delete:
                    db.session.delete(file_to_delete)
                    try:
                        db.session.commit()
                        flash(
                            f'File "{filename}" deleted successfully!', 'success')
                    except SQLAlchemyError:
                        db.session.rollback()
                        flash(
                            "Database error occurred while deleting file.", "danger")
                else:
                    flash(f'File "{filename}" not found.', 'danger')
            return redirect(url_for('main.exchange'))

        selected_files = request.form.getlist('selected_files')
        selected_traverse = request.form.getlist('selected_traverse')
        # print(selected_files, selected_traverse)
        lambda_value = float(request.form.get('lambda'))

        if selected_files:
            data, surplus_sum, deficit_sum, traverse_amount, total = calculate_exchange(
                selected_files, selected_traverse)

            calculated_data1, satisfiedA, calculated_data2, satisfiedB, calculated_data3, comparison, traverse_data = split_json_by_deficit_surplus(
                selected_files, selected_traverse, lambda_value)
            db_data = []

            traverse_data = round_floats(traverse_data)

            exchange_name = nameExchange(calculated_data1, traverse_data)

            db_data = {
                "exchange_name": exchange_name,
                "calculated_data1": calculated_data1,
                "calculated_data2": calculated_data2,
                "calculated_data3": calculated_data3,
                "comparison": comparison,
                "data": data,
                "surplus_sum": surplus_sum,
                "deficit_sum": deficit_sum,
                "traverse": traverse_data,  # review
                "traverse_amount": traverse_amount,
                "total": total,
                "satisfiedA": satisfiedA,
                "satisfiedB": satisfiedB
            }
            # print()
            # print("DB Data:")
            # print(db_data)

            if check_entry_existance(db_data["exchange_name"], current_user, PastExchange):
                flash("Entry already exists", "danger")
                # Overwrite the existing entry
                entry = db.session.execute(
                    select(PastExchange).filter(
                        PastExchange.user_id == current_user.id,
                        PastExchange.filename == db_data["exchange_name"]
                    )
                ).scalar_one_or_none()
                if entry:
                    entry.json_data = json.dumps(db_data)
                    entry.user_id = current_user.id
            else:
                entry = PastExchange(
                    filename=db_data["exchange_name"],
                    json_data=json.dumps(db_data),  # Store as JSON string
                    user_id=current_user.id
                )
                db.session.add(entry)
            try:
                db.session.commit()
                flash('Form successfully submitted!', 'success')
            except SQLAlchemyError:
                db.session.rollback()
                flash("Database error occurred while submitting the form.", "danger")
        past_exchange = get_past_exchange()
        return render_template('exchange.html',
                               filename=exchange_name, data=data,
                               past_exchange=past_exchange, files=files, traverse_files=traverse_files,
                               surplus_sum=surplus_sum, deficit_sum=deficit_sum,
                               calculated_data1=calculated_data1, calculated_data2=calculated_data2, calculated_data3=calculated_data3,
                               comparison1=comparison[0], comparison2=comparison[1], comparison3=comparison[2],
                               traverse=traverse_data, total=total, traverse_tot=traverse_amount,
                               satisfiedA=satisfiedA, satisfiedB=satisfiedB)

    return render_template('exchange.html', data=None,
                           past_exchange=past_exchange, files=files, traverse_files=traverse_files,
                           surplus_sum=0, deficit_sum=0, traverse=0, total=0)


def nameExchange(calculated_data, selected_traverse):
    name = ''
    for i in range(len(calculated_data)):
        if calculated_data[i].get("Filename"):
            name += calculated_data[i].get("Filename")
        else:
            continue
        if (i < len(calculated_data) - 1):
            name = name + '-'
    for i in range(len(selected_traverse)):
        if selected_traverse[i]:
            name += '-' + selected_traverse[i].get("Filename")
        else:
            continue
    return name


def calculate_exchange(file_list, traverse_list):
    """
    Process files to calculate exchange values.
    """
    sf_data = {}
    surplus_sum = 0
    deficit_sum = 0
    traverse_amount = 0
    for filename in file_list:
        try:
            data = load_json_data(filename)
        except FileNotFoundError:
            flash(f"File {filename} not found.", "danger")
            continue

        if not data:
            continue
        key = data.get("Filename", filename)
        sf_data[key] = {
            # "Sf 1 avg": data.get("Sf 1 avg"),
            # "Sf 2 avg": data.get("Sf 2 avg"),
            # "D/S 1 avg": data.get("D/S 1 avg"),
            # "D/S 2 avg": data.get("D/S 2 avg")
            "D/S 1 yearly": data.get("D/S 1*")[11],
            "Sf 1 yearly": data.get("Sf 1*")[11],
            "D/S 2 yearly": data.get("D/S 2*")[11],
            "Sf 2 yearly": data.get("Sf 2*")[11]
        }

        if data.get("D/S 1*")[11]:
            ds1_avg = data.get("D/S 1*")[11]
        else:
            ds1_avg = 0
        # ds1_avg = data.get("D/S 1 avg", 0)
        if ds1_avg > 0:
            surplus_sum += ds1_avg
        elif ds1_avg < 0:
            deficit_sum += ds1_avg

    for filename in traverse_list:
        try:
            data = load_json_data_traverse(filename)
        except FileNotFoundError:
            flash(f"File {filename} not found.", "danger")
            continue

        if not data:
            continue
        for i in range(12):
            traverse_amount += data["Pj"][i] - \
                data["Pj(eco)"][i] - data["Pij"][i]

    total = round_floats(surplus_sum + deficit_sum + traverse_amount)
    return round_floats(sf_data), round_floats(surplus_sum), round_floats(deficit_sum), round_floats(traverse_amount), total


def split_json_by_deficit_surplus(file_list, traverse_list, lambda_value):
    """
    Separates JSON files into positive and negative D/S lists and calls the appropriate outflow.
    """
    positive_entries = []
    negative_entries = []
    traverse_data = []
    sum_positive_ds = 0
    sum_negative_ds = 0
    count_positive = 0
    count_negative = 0

    for filename in file_list:
        data = load_json_data(filename)
        if data and "D/S 1*" in data and isinstance(data["D/S 1*"], list) and data["D/S 1*"]:
            # For each file, get the last value of D/S 1* to determine
            # whether it is a surplus or deficit
            last_value = data["D/S 1*"][-1]
            entry = {"Filename": data.get(
                "Filename", filename), "Data": last_value}
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

    # Check the sum of surplus is bigger then deficit
    if surplus[1] >= abs(deficit[1]):
        calculated_data1, satisfiedA, calculated_data2, satisfiedB, calculated_data3, comparison = outflowA(
            surplus, deficit, lambda_value)
    elif surplus[1] < abs(deficit[1]):
        calculated_data1, satisfiedA, calculated_data2, satisfiedB, calculated_data3, comparison, traverse_data = outflowB(
            surplus, deficit, lambda_value, traverse_list)
    else:
        return [], [], []  # fallback in case something unexpected happens

    return calculated_data1, satisfiedA,  calculated_data2, satisfiedB, calculated_data3, comparison, traverse_data


def outflowA(surplus, deficit, lambda_value):
    """
    Processes outflow scenario A.
    """

    calculated_data1, satisfiedA, comparison1 = criteria_a1(surplus, deficit)
    calculated_data2, satisfiedB, comparison2 = criteria_a2(surplus, deficit)
    calculated_data3, comparison3 = criterio_a3(surplus, deficit, lambda_value)
    comparison = []
    comparison.append(comparison1)
    comparison.append(comparison2)
    comparison.append(comparison3)
    return calculated_data1, satisfiedA, calculated_data2, satisfiedB, calculated_data3, comparison


def criteria_a1(surplus, deficit):
    # Assuming surplus[0] is a list of dictionaries each containing a "Filename" key
    k_a = [0] * 12
    edj = [0] * 12
    satisfied_a = True
    satisfied_b = True
    edj_tot = 0
    surplus_tmp = surplus
    deficit_tmp = deficit
    calculated_data1 = []

    if len(surplus_tmp) > 3 and surplus_tmp[3]:
        delta_month = surplus[3]
    else:
        delta_month = [0] * 12

    if surplus_tmp[2] > 0:
        # print("Surplus entries:")
        # print(surplus_tmp[0])
        for entry in surplus_tmp[0]:
            # print(entry)
            if entry.get("Filename") and not entry.get("Type"):
                try:
                    json_data = load_json_data(entry.get("Filename"))
                except FileNotFoundError:
                    flash(f"File {entry.get('Filename')} not found.", "danger")
                    continue
                if json_data:
                    # Calculate sum of positive values in "D/S 1 j" for 12 months
                    sum_surplus = sum(
                        json_data["D/S 1 j"][i] for i in range(12) if json_data["D/S 1 j"][i] > 0
                    )
                    try:
                        alpha_value = json_data["D/S 1*"][11] / sum_surplus
                    except (IndexError, ZeroDivisionError):
                        alpha_value = 0

                    # Store computed alpha value and the monthly computed values in the dictionary
                    entry["alpha"] = alpha_value
                    entry["alpha_surplus"] = []
                    for i in range(12):
                        if json_data["D/S 1 j"][i] > 0:
                            entry["alpha_surplus"].append(
                                json_data["D/S 1 j"][i] * alpha_value)
                            edj[i] += json_data["D/S 1 j"][i] * alpha_value
                            # edj_tot += json_data["D/S 1 j"][i] * alpha_value
                            k_a[i] = 1
                        else:
                            entry["alpha_surplus"].append(0)
                    calculated_data1.append(entry)

                    # Check if the two conditions are met
                    for i in range(12):
                        # Donor
                        check = json_data.get("W j")[i] + json_data.get("A j")[i] - \
                            (json_data.get("E pot j")[i] + json_data.get("E irr j")[i] +
                             json_data.get("E ind j")[i] + entry["alpha_surplus"][i])

                        if not (check >= json_data.get("Wo") and k_a[i] == 1):
                            satisfied_a = False
                            break

        # print("Calculated data 1:")
        # print(calculated_data1)
        calculated_data1.append({"Edj tot": edj_tot, "k_a": k_a})

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
                        #alpha_value = abs(json_data["D/S 1*"][11] / deficit[1])
                        # When using a wier, the defict should scale down to the 
                        # amount that is not supported by the weir itself
                        alpha_value = abs(json_data["D/S 1*"][11] / deficit[1])
                    except (IndexError, ZeroDivisionError):
                        alpha_value = 0

                    # Store computed alpha value and the monthly computed values in the dictionary
                    entry["alpha"] = alpha_value
                    entry["alpha_deficit"] = [
                        (edj[i] + delta_month[i]) * alpha_value for i in range(12)
                        # (edj[i]) * alpha_value for i in range(12)
                    ]

                    # Check if the two conditions are met
                    for i in range(12):
                        # Receiver
                        check = json_data.get("W j")[i] + entry["alpha_deficit"][i] + json_data.get("A j")[i] - \
                            (json_data.get("E pot j")[i] + json_data.get("E irr j")[i] +
                             json_data.get("E ind j")[i])

                        if not (check <= json_data.get("Winv tot") and k_a[i] == 1):
                            satisfied_b = False
                            break

                    calculated_data1.append(entry)

    comparison1 = exchange_comparison(calculated_data1, 1)
    calculated_data1 = round_floats(calculated_data1)
    satisfied = satisfied_a and satisfied_b

    return calculated_data1, satisfied, comparison1


def criteria_a2(surplus, deficit):
    # Assuming surplus[0] is a list of dictionaries each containing a "Filename" key
    k_b = [0] * 12
    adj = [0] * 12
    adj_tot = 0
    surplus_tmp = surplus
    deficit_tmp = deficit
    calculated_data2 = []

    if len(surplus_tmp) > 3 and surplus_tmp[3]:
        delta_month = surplus[3]
    else:
        delta_month = [0] * 12

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
                            entry["alpha_deficit"].append(
                                abs(json_data["D/S 1 j"][i] * alpha_value))
                            adj[i] = abs(json_data["D/S 1 j"][i] * alpha_value)
                            # adj_tot = abs(
                            #    json_data["D/S 1 j"][i] * alpha_value)
                            k_b[i] = 1
                        else:
                            entry["alpha_deficit"].append(0)

                    calculated_data2.append(entry)

                    # Check if the two conditions are met
                    for i in range(12):
                        # Receiver
                        check = json_data.get("W j")[i] + entry["alpha_deficit"][i] + json_data.get("A j")[i] - \
                            (json_data.get("E pot j")[i] + json_data.get("E irr j")[i] +
                             json_data.get("E ind j")[i])

                        if not (check <= json_data.get("Winv tot") and k_b[i] == 1):
                            satisfied_b = False
                            break

        # print("Calculated data 2:")
        # print(calculated_data2)
        calculated_data2.append({"Adj tot": adj_tot, "k_b": k_b})

    if surplus_tmp[2] > 0:
        for entry in surplus_tmp[0]:
            if entry.get("Filename") and not entry.get("Type"):
                try:
                    json_data = load_json_data(entry.get("Filename"))
                except FileNotFoundError:
                    flash(f"File {entry.get('Filename')} not found.", "danger")
                    continue
                if json_data:
                    # Calculate sum of positive values in "D/S 1 j" for 12 months
                    sum_surplus = sum(
                        json_data["D/S 1 j"][i] for i in range(12) if json_data["D/S 1 j"][i] > 0
                    )
                    try:
                        alpha_value = json_data["D/S 1*"][11] / surplus[1]
                    except (IndexError, ZeroDivisionError):
                        alpha_value = 0

                    # Store computed alpha value and the monthly computed values in the dictionary
                    entry["alpha"] = alpha_value
                    entry["alpha_surplus"] = [
                        (adj[i] + delta_month[i]) * alpha_value for i in range(12)
                    ]
                    calculated_data2.append(entry)

                    # Check if the two conditions are met
                    for i in range(12):
                        # Donor
                        check = json_data.get("W j")[i] + json_data.get("A j")[i] - \
                            (json_data.get("E pot j")[i] + json_data.get("E irr j")[i] +
                             json_data.get("E ind j")[i] + entry["alpha_surplus"][i])

                        if not (check >= json_data.get("Wo") and k_b[i] == 1):
                            satisfied_a = False
                            break

    comparison2 = exchange_comparison(calculated_data2, 2)
    calculated_data2 = round_floats(calculated_data2)
    satisfied = satisfied_a and satisfied_b
    return calculated_data2, satisfied, comparison2


def criterio_a3(surplus, deficit, lambda_value):
    calculated_data_3 = []
    calculated_data_31 = []
    calculated_data_32 = []
    k_a = [0] * 12
    k_b = [0] * 12
    edj = [0] * 12
    adj = [0] * 12
    edj_tot = 0
    adj_tot = 0
    surplus_tmp = surplus
    deficit_tmp = deficit
    lambda_surplus = lambda_value
    lambda_deficit = 1 - lambda_value

    if len(surplus_tmp) > 3 and surplus_tmp[3]:
        delta_month = surplus[3]
    else:
        delta_month = [0] * 12

    # Criterio A1
    if surplus_tmp[2] > 0:
        for entry in surplus_tmp[0]:
            if entry.get("Filename") and not entry.get("Type"):
                # Load JSON data for the surplus entry
                try:
                    json_data = load_json_data(entry.get("Filename"))
                except FileNotFoundError:
                    flash(f"File {entry.get('Filename')} not found.", "danger")
                    continue

                if json_data:
                    # Calculate sum of positive values in "D/S 1 j" for 12 months
                    sum_surplus = sum(
                        json_data["D/S 1 j"][i] for i in range(12) if json_data["D/S 1 j"][i] > 0
                    )
                    try:
                        alpha_value = json_data["D/S 1*"][11] / sum_surplus
                    except (IndexError, ZeroDivisionError):
                        alpha_value = 0
                    # Store computed alpha value and the monthly computed values in the dictionary
                    entry["alpha"] = alpha_value
                    entry["alpha_surplus"] = []

                    for i in range(12):
                        if json_data["D/S 1 j"][i] > 0:
                            entry["alpha_surplus"].append(
                                json_data["D/S 1 j"][i] * alpha_value * lambda_surplus)
                            # edj_tot += json_data["D/S 1 j"][i] * alpha_value * lambda_surplus ##TO VERIFY
                            edj[i] += json_data["D/S 1 j"][i] * \
                                alpha_value * lambda_surplus
                            k_a[i] = 1
                        else:
                            entry["alpha_surplus"].append(0)
                    calculated_data_31.append(entry)

    if deficit_tmp[2] > 0:
        for entry in deficit_tmp[0]:
            if entry.get("Filename"):
                # Load JSON data for the deficit entry
                try:
                    json_data = load_json_data(entry.get("Filename"))
                except FileNotFoundError:
                    flash(f"File {entry.get('Filename')} not found.", "danger")
                    continue

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
                        (edj[i] + delta_month[i]) * alpha_value for i in range(12)
                    ]
                    calculated_data_31.append(entry)

    # Criterio A2
    deficit_tmp = deficit
    surplus_tmp = surplus
    if deficit_tmp[2] > 0:
        for entry in deficit_tmp[0]:
            if entry.get("Filename"):
                # Load JSON data for the deficit entry
                try:
                    json_data = load_json_data(entry.get("Filename"))
                except FileNotFoundError:
                    flash(f"File {entry.get('Filename')} not found.", "danger")
                    continue

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
                            entry["alpha_deficit"].append(
                                abs(json_data["D/S 1 j"][i] * alpha_value * lambda_deficit))
                            # adj_tot = abs(
                            #    json_data["D/S 1 j"][i] * alpha_value * lambda_deficit)
                            adj[i] = abs(json_data["D/S 1 j"][i]
                                         * alpha_value * lambda_deficit)
                            k_b[i] = 1
                        else:
                            entry["alpha_deficit"].append(0)

                    calculated_data_32.append(entry)

    if surplus_tmp[2] > 0:
        for entry in surplus_tmp[0]:
            if entry.get("Filename") and not entry.get("Type"):
                # Load JSON data for the surplus entry
                try:
                    json_data = load_json_data(entry.get("Filename"))
                except FileNotFoundError:
                    flash(f"File {entry.get('Filename')} not found.", "danger")
                    continue

                if json_data:
                    # Calculate sum of positive values in "D/S 1 j" for 12 months
                    sum_surplus = sum(
                        json_data["D/S 1 j"][i] for i in range(12) if json_data["D/S 1 j"][i] > 0
                    )
                    try:
                        alpha_value = json_data["D/S 1*"][11] / surplus[1]
                    except (IndexError, ZeroDivisionError):
                        alpha_value = 0

                    # Store computed alpha value and the monthly computed values in the dictionary
                    entry["alpha"] = alpha_value
                    entry["alpha_surplus"] = [
                        (adj[i] + delta_month[i]) * alpha_value for i in range(12)
                    ]
                    calculated_data_32.append(entry)

    aggregated_data = {}

    # First, copy all entries from criterio_a3_1
    for entry in calculated_data_31:
        place = entry['Filename']
        aggregated_data[place] = copy.deepcopy(
            entry)  # Keep the original structure

    # Now, update or merge entries from criterio_a3_2
    for entry in calculated_data_32:
        place = entry['Filename']

        if place in aggregated_data:
            # Sum alpha_deficit if present
            if 'alpha_deficit' in entry:
                if 'alpha_deficit' in aggregated_data[place]:
                    aggregated_data[place]['alpha_deficit'] = [
                        aggregated_data[place]['alpha_deficit'][i] +
                        entry['alpha_deficit'][i]
                        for i in range(12)
                    ]
                else:
                    aggregated_data[place]['alpha_deficit'] = entry['alpha_deficit']

            # Sum alpha_surplus if present
            if 'alpha_surplus' in entry:
                if 'alpha_surplus' in aggregated_data[place]:
                    aggregated_data[place]['alpha_surplus'] = [
                        aggregated_data[place]['alpha_surplus'][i] +
                        entry['alpha_surplus'][i]
                        for i in range(12)
                    ]
                else:
                    aggregated_data[place]['alpha_surplus'] = entry['alpha_surplus']
        else:
            # If the place is not already in aggregated_data, add it as is
            aggregated_data[place] = copy.deepcopy(entry)

    # Convert back to a list to match the original format
    calculated_data_3 = list(aggregated_data.values())
    calculated_data_3.append(
        {"Edj tot": edj_tot, "Adj tot": adj_tot, "k_a": k_a, "k_b": k_b})

    # Save past and new surplus/deficit values
    comparison3 = exchange_comparison(calculated_data_3, 3)

    calculated_data_3 = round_floats(calculated_data_3)

    return calculated_data_3, comparison3


def outflowB(surplus, deficit, lambda_value, traverse_list):
    def clear(): return os.system('clear')
    clear()
    print("Outflow B")
    print(
        f"Surplus: {surplus[1]}, Deficit: {deficit[1]}, Traverse List: {traverse_list}")
    traverse_data = []
    Ptot = 0
    delta_p = 0
    delta_tot = abs(deficit[1]) - surplus[1]
    Datot = surplus[1]  # Deficit managed by the surplus
    Dbtot = delta_tot  # Defict managed by the traverse

    print(f"Datot: {Datot}, Dbtot: {Dbtot}, delta_tot: {delta_tot}")
    sufficient = False
    # print(traverse_list)
    for traverse in traverse_list:
        # Retrieve the traverse data
        traverse_data.append(load_json_data_traverse(traverse))

    for i in range(len(traverse_data)):
        tot = 0
        traverse_data[i]["P_util_month"] = [0] * 12
        for j in range(12):
            traverse_data[i]["P_util_month"][j] = traverse_data[i]["Pj"][j] - \
                traverse_data[i]["Pij"][j] - traverse_data[i]["Pj(eco)"][j]
            tot += traverse_data[i]["P_util_month"][j]
            Ptot += traverse_data[i]["P_util_month"][j]
        traverse_data[i]["P_util_tot"] = tot

    # print(f"Ptot: {Ptot}, Datot: {Datot}, Dbtot: {Dbtot}")

    if Ptot >= Dbtot:
        # print("Ptot > Dbtot")
        delta_p = Dbtot  # Amount of surplus that can be covered by the traverse
        sufficient = True
    else:
        print("Ptot < Dbtot")
        # delta_p = Ptot              #Amount of surplus that can be covered by the traverse
        #delta_not = Dbtot - Ptot
        delta_p = Dbtot - Ptot

    try:
        alpha5 = delta_p / Ptot
    except ZeroDivisionError:
        alpha5 = 0

    for i in range(len(traverse_data)):
        traverse_data[i]["delta_r"] = alpha5 * traverse_data[i]["P_util_tot"]

        try:
            alpha6 = traverse_data[i]["delta_r"] / \
                traverse_data[i]["P_util_tot"]
        except ZeroDivisionError:
            alpha6 = 0

        traverse_data[i]["delta_r_month"] = [0] * 12
        for j in range(12):
            # Final monthly contribute of a traverse
            traverse_data[i]["delta_r_month"][j] = alpha6 * \
                traverse_data[i]["P_util_month"][j]
            traverse_data[i]["overall_erogation"] = sum(
                # Total erogation of a traverse
                traverse_data[i]["delta_r_month"])

    delta_tot_monthly = []  # Monthly contribution of all traverses
    for i in range(12):
        delta_tot_monthly.append(
            sum(traverse_data[j]["delta_r_month"][i] for j in range(len(traverse_data))))

    new_deficit = deficit
    new_deficit[1] = -Datot
    new_surplus = surplus
    new_surplus.append(round_floats(delta_tot_monthly))

    print(f"New Deficit: {new_deficit}")
    print()
    print(f"New Surplus: {new_surplus}")
    print()
    print(f"Monthly Delta Tot: {delta_tot_monthly}")

    calculated_data1, satisfiedA, comparison1 = criteria_a1(
        new_surplus, new_deficit)
    calculated_data2, satisfiedB, comparison2 = criteria_a2(
        new_surplus, new_deficit)
    calculated_data3, comparison3 = criterio_a3(
        new_surplus, new_deficit, lambda_value)

    comparison = []
    comparison.append(comparison1)
    comparison.append(comparison2)
    comparison.append(comparison3)

    return calculated_data1, satisfiedA, calculated_data2, satisfiedB, calculated_data3, comparison, traverse_data


def _build_reservoir_entries(file_list):
    entries = []
    summary = {}

    def _last_value(sequence):
        if isinstance(sequence, list) and sequence:
            return sequence[-1]
        return 0.0

    for filename in file_list:
        data = load_json_data(filename)
        if not data:
            continue
        name = data.get("Filename", filename)
        balance = compute_reservoir_balance(data)
        entries.append({
            "name": name,
            "filename": filename,
            "data": data,
            "balance": balance,
        })
        summary[name] = {
            "D/S 1 yearly": _last_value(data.get("D/S 1*", [])),
            "Sf 1 yearly": _last_value(data.get("Sf 1*", [])),
            "D/S 2 yearly": _last_value(data.get("D/S 2*", [])),
            "Sf 2 yearly": _last_value(data.get("Sf 2*", [])),
        }

    return entries, summary


def _build_traverse_resources(traverse_list):
    traverse_entries = []
    for filename in traverse_list:
        data = load_json_data_traverse(filename)
        if not data:
            continue
        if "Filename" not in data:
            data["Filename"] = filename
        traverse_entries.append(data)

    resources, monthly_totals, total_available = compute_additional_resources(traverse_entries)
    return traverse_entries, resources, monthly_totals, total_available


def _build_comparison(all_entries, updated_monthly):
    comparison = []
    for entry in all_entries:
        name = entry["name"]
        original_ds1 = entry["data"].get("D/S 1*", [])
        original_ds2 = entry["data"].get("D/S 2*", [])
        monthly_values = updated_monthly.get(name, entry["balance"]["monthly_net"])
        new_cumulative = somma_cumulata(monthly_values)
        comparison.append({
            "Filename": name,
            "D/S 1*": round_floats(original_ds1),
            "D/S 1* post": round_floats(new_cumulative),
            "D/S 2*": round_floats(original_ds2),
            "D/S 2* post": round_floats(new_cumulative),
        })
    return comparison


def _build_criterion_results(
    all_entries,
    donors_info,
    receivers_info,
    alpha_one,
    distribution_type,
    external_contributions=None,
):
    donors_total = sum(donor["available"] for donor in donors_info)
    adjustments = {}
    donors_output = []
    donors_checks = []

    for donor in donors_info:
        monthly_values = distribute_amount(
            donor["available"], distribution_type, alpha_one)
        donors_output.append({
            "Filename": donor["name"],
            "alpha": donor["available"] / donors_total if donors_total else 0.0,
            "alpha_surplus": round_floats(monthly_values),
        })
        donors_checks.append(
            verify_donor_constraints(donor["data"], monthly_values))
        adjustments[donor["name"]] = [
            donor["balance"]["monthly_net"][index] - monthly_values[index]
            for index in range(12)
        ]

    receivers_output = []
    receivers_checks = []
    external_contributions = external_contributions or {}

    for receiver in receivers_info:
        donor_monthly = distribute_amount(
            receiver["from_donors"], distribution_type, alpha_one)
        external_monthly = external_contributions.get(
            receiver["name"], [0.0] * 12)
        total_monthly = [
            donor_monthly[index] + external_monthly[index]
            for index in range(12)
        ]
        receivers_output.append({
            "Filename": receiver["name"],
            "alpha": receiver["share_ratio"],
            "alpha_deficit": round_floats(total_monthly),
        })
        receivers_checks.append(
            verify_receiver_constraints(receiver["data"], total_monthly))
        adjustments[receiver["name"]] = [
            receiver["balance"]["monthly_net"][index] + total_monthly[index]
            for index in range(12)
        ]

    for entry in all_entries:
        if entry["name"] not in adjustments:
            adjustments[entry["name"]] = entry["balance"]["monthly_net"]

    satisfied = all(donors_checks) and all(receivers_checks)
    summary = {
        "criterion": distribution_type,
        "total_release": round(sum(d["available"] for d in donors_info), 2),
    }
    output = donors_output + receivers_output + [summary]
    comparison = _build_comparison(all_entries, adjustments)
    return round_floats(output), satisfied, round_floats(comparison)


def _apply_model_a(all_entries, donors, receivers, alpha_one):
    stot = sum(d["balance"]["surplus_net"] for d in donors)
    dtot = sum(r["balance"]["deficit_net"] for r in receivers)
    delta = max(stot - dtot, 0.0)
    reduction_ratio = (delta / stot) if stot and delta else 0.0

    donors_info = []
    for donor in donors:
        available = donor["balance"]["surplus_net"]
        if reduction_ratio:
            available -= donor["balance"]["surplus_net"] * reduction_ratio
        donors_info.append({
            "name": donor["name"],
            "data": donor["data"],
            "balance": donor["balance"],
            "available": max(available, 0.0),
        })

    receivers_info = []
    for receiver in receivers:
        deficit = receiver["balance"]["deficit_net"]
        receivers_info.append({
            "name": receiver["name"],
            "data": receiver["data"],
            "balance": receiver["balance"],
            "from_donors": deficit,
            "share_ratio": deficit / dtot if dtot else 0.0,
        })

    external = {}
    criterion1, satisfied1, comparison1 = _build_criterion_results(
        all_entries, donors_info, receivers_info, alpha_one, 1, external)
    criterion2, satisfied2, comparison2 = _build_criterion_results(
        all_entries, donors_info, receivers_info, alpha_one, 2, external)

    criterion3 = copy.deepcopy(criterion2)
    if criterion3:
        summary = criterion3[-1]
        if isinstance(summary, dict):
            summary["criterion"] = 3

    comparison = [comparison1, comparison2, comparison2]
    return criterion1, satisfied1, criterion2, satisfied2, criterion3, comparison, []


def _apply_model_b(
    all_entries,
    donors,
    receivers,
    resources,
    total_resource,
    alpha_one,
):
    stot = sum(d["balance"]["surplus_net"] for d in donors)
    dtot = sum(r["balance"]["deficit_net"] for r in receivers)
    delta = max(dtot - stot, 0.0)

    donors_info = []
    for donor in donors:
        donors_info.append({
            "name": donor["name"],
            "data": donor["data"],
            "balance": donor["balance"],
            "available": max(donor["balance"]["surplus_net"], 0.0),
        })

    covered_deficit = min(delta, total_resource)
    scale_factor = (covered_deficit / total_resource) if total_resource else 0.0

    scaled_resources = []
    monthly_scaled_totals = [0.0] * 12
    for resource in resources:
        scaled_monthly = [value * scale_factor for value in resource["monthly_available"]]
        monthly_scaled_totals = [
            monthly_scaled_totals[index] + scaled_monthly[index]
            for index in range(12)
        ]
        scaled_resources.append({
            "Filename": resource.get("Filename", ""),
            "delta_r_month": round_floats(scaled_monthly),
            "overall_erogation": round(sum(scaled_monthly), 2),
        })

    external_contributions = {}
    receivers_info = []
    for receiver in receivers:
        deficit = receiver["balance"]["deficit_net"]
        donor_share = deficit * (stot / dtot) if dtot else 0.0
        external_share = deficit * (covered_deficit / dtot) if dtot else 0.0
        receivers_info.append({
            "name": receiver["name"],
            "data": receiver["data"],
            "balance": receiver["balance"],
            "from_donors": donor_share,
            "share_ratio": deficit / dtot if dtot else 0.0,
        })
        external_contributions[receiver["name"]] = [
            (deficit / dtot) * monthly_scaled_totals[index] if dtot else 0.0
            for index in range(12)
        ]

    criterion1, satisfied1, comparison1 = _build_criterion_results(
        all_entries, donors_info, receivers_info, alpha_one, 1, external_contributions)
    criterion2, satisfied2, comparison2 = _build_criterion_results(
        all_entries, donors_info, receivers_info, alpha_one, 2, external_contributions)

    criterion3 = copy.deepcopy(criterion2)
    if criterion3:
        summary = criterion3[-1]
        if isinstance(summary, dict):
            summary["criterion"] = 3

    comparison = [comparison1, comparison2, comparison2]
    return criterion1, satisfied1, criterion2, satisfied2, criterion3, comparison, scaled_resources


def calculate_exchange(file_list, traverse_list):
    entries, summary = _build_reservoir_entries(file_list)
    _, resources, _, _ = _build_traverse_resources(traverse_list)

    total_surplus = sum(
        max(entry["balance"]["surplus_net"], 0.0) for entry in entries)
    total_deficit = sum(
        min(entry["balance"]["surplus_net"], 0.0) for entry in entries)
    traverse_amount = sum(resource["total_available"] for resource in resources)
    total = total_surplus + total_deficit + traverse_amount

    return (
        round_floats(summary),
        round_floats(total_surplus),
        round_floats(total_deficit),
        round_floats(traverse_amount),
        round_floats(total),
    )


def split_json_by_deficit_surplus(file_list, traverse_list, lambda_value):
    entries, _ = _build_reservoir_entries(file_list)
    _, resources, _, total_resource = _build_traverse_resources(traverse_list)

    donors = [entry for entry in entries if entry["balance"]["surplus_net"] > 0]
    receivers = [entry for entry in entries if entry["balance"]["deficit_net"] > 0]

    try:
        alpha_one = float(lambda_value)
    except (TypeError, ValueError):
        alpha_one = 0.7

    stot = sum(d["balance"]["surplus_net"] for d in donors)
    dtot = sum(r["balance"]["deficit_net"] for r in receivers)

    if not donors and not receivers:
        empty_comparison = [[], [], []]
        return [], True, [], True, [], empty_comparison, []

    if stot >= dtot:
        return _apply_model_a(entries, donors, receivers, alpha_one)

    return _apply_model_b(
        entries, donors, receivers, resources, total_resource, alpha_one)
