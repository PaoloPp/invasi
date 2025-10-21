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
    precomputed=None,
    blend_weight=None,
):
    donors_total = sum(donor["available"] for donor in donors_info)
    adjustments = {}
    donors_output = []
    donors_checks = []

    precomputed = precomputed or {}
    monthly_allocations = {}

    if distribution_type == 3:
        blend_weight = 0.5 if blend_weight is None else max(min(blend_weight, 1.0), 0.0)

    for donor in donors_info:
        if donor["name"] in precomputed:
            monthly_values = precomputed[donor["name"]]
        elif distribution_type == 3:
            uniform_values = distribute_amount(donor["available"], 1, alpha_one)
            modulated_values = distribute_amount(donor["available"], 2, alpha_one)
            monthly_values = [
                (1.0 - blend_weight) * uniform_values[index]
                + blend_weight * modulated_values[index]
                for index in range(12)
            ]
        else:
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
        monthly_allocations[donor["name"]] = monthly_values

    receivers_output = []
    receivers_checks = []
    external_contributions = external_contributions or {}

    for receiver in receivers_info:
        external_monthly = external_contributions.get(
            receiver["name"], [0.0] * 12)
        if receiver["name"] in precomputed:
            total_monthly = precomputed[receiver["name"]]
        elif distribution_type == 3:
            uniform_values = distribute_amount(
                receiver["from_donors"], 1, alpha_one)
            modulated_values = distribute_amount(
                receiver["from_donors"], 2, alpha_one)
            total_monthly = [
                (1.0 - blend_weight)
                * (uniform_values[index] + external_monthly[index])
                + blend_weight
                * (modulated_values[index] + external_monthly[index])
                for index in range(12)
            ]
        else:
            donor_monthly = distribute_amount(
                receiver["from_donors"], distribution_type, alpha_one)
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
        monthly_allocations[receiver["name"]] = total_monthly

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
    return round_floats(output), satisfied, round_floats(comparison), monthly_allocations


def _apply_model_a(all_entries, donors, receivers, alpha_one, blend_weight):
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
    criterion1, satisfied1, comparison1, monthly1 = _build_criterion_results(
        all_entries, donors_info, receivers_info, alpha_one, 1, external)
    criterion2, satisfied2, comparison2, monthly2 = _build_criterion_results(
        all_entries, donors_info, receivers_info, alpha_one, 2, external)

    precomputed = {}
    blend_weight = max(min(blend_weight, 1.0), 0.0)
    for name in set(list(monthly1.keys()) + list(monthly2.keys())):
        values1 = monthly1.get(name, [0.0] * 12)
        values2 = monthly2.get(name, [0.0] * 12)
        blended = [
            (1.0 - blend_weight) * values1[index]
            + blend_weight * values2[index]
            for index in range(12)
        ]
        precomputed[name] = blended

    criterion3, satisfied3, comparison3, _ = _build_criterion_results(
        all_entries,
        donors_info,
        receivers_info,
        alpha_one,
        3,
        external,
        precomputed,
        blend_weight,
    )

    comparison = [comparison1, comparison2, comparison3]
    return criterion1, satisfied1, criterion2, satisfied2, criterion3, comparison, []


def _apply_model_b(
    all_entries,
    donors,
    receivers,
    resources,
    total_resource,
    alpha_one,
    blend_weight,
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

    criterion1, satisfied1, comparison1, monthly1 = _build_criterion_results(
        all_entries, donors_info, receivers_info, alpha_one, 1, external_contributions)
    criterion2, satisfied2, comparison2, monthly2 = _build_criterion_results(
        all_entries, donors_info, receivers_info, alpha_one, 2, external_contributions)

    precomputed = {}
    blend_weight = max(min(blend_weight, 1.0), 0.0)
    for name in set(list(monthly1.keys()) + list(monthly2.keys())):
        values1 = monthly1.get(name, [0.0] * 12)
        values2 = monthly2.get(name, [0.0] * 12)
        blended = [
            (1.0 - blend_weight) * values1[index]
            + blend_weight * values2[index]
            for index in range(12)
        ]
        precomputed[name] = blended

    criterion3, satisfied3, comparison3, _ = _build_criterion_results(
        all_entries,
        donors_info,
        receivers_info,
        alpha_one,
        3,
        external_contributions,
        precomputed,
        blend_weight,
    )

    comparison = [comparison1, comparison2, comparison3]
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
        lambda_raw = float(lambda_value)
    except (TypeError, ValueError):
        lambda_raw = 0.7

    alpha_one = max(min(lambda_raw, 1.0), 0.0)
    blend_weight = max(min(lambda_raw, 1.0), 0.0)

    stot = sum(d["balance"]["surplus_net"] for d in donors)
    dtot = sum(r["balance"]["deficit_net"] for r in receivers)

    if not donors and not receivers:
        empty_comparison = [[], [], []]
        return [], True, [], True, [], empty_comparison, []

    if stot >= dtot:
        return _apply_model_a(entries, donors, receivers, alpha_one, blend_weight)

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
