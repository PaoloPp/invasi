from itertools import cycle
from extensions import db
from models import JsonFile, User, PastExchange
from flask_login import current_user
from sqlalchemy import select

import matplotlib.pyplot as plt
import os

def check_entry_existance(_filename, _current_user, _table):
    existing_file = db.session.execute(
                    select(_table).filter(
                        _table.user_id == _current_user.id,
                        _table.filename == _filename
                    )
                ).scalar_one_or_none()
    return existing_file
    
def set_year(_month):
    months = []
    tmp_months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    pool = cycle(tmp_months)
    for item in pool:
        if (item == _month) and (not months):
            months.append(item)
        elif (months) and (item != _month):
            months.append(item)
        elif (months) and (item == _month):
            break
    return months

def round_floats(obj):
    if isinstance(obj, dict):
        return {key: round_floats(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [round_floats(element) for element in obj]
    elif isinstance(obj, float):
        return round(obj, 2)
    else:
        return obj
    

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
            data["D ec j"][i] + data["E pot j"][i] + data["E irr j"][i] + data["E ind j"][i])) ##TO FIX
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
            values_sf2.append(0)
        else:
            values_sf2.append(data["w j"][i])

        values_deficit1.append(float(data["w j"][i] - float(values_sf1[i])))
        values_deficit2.append(float(data["w j"][i] - float(values_sf2[i])))
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
    data["Sf 1 avg"] = sum(values_sf1) / len(values_sf1)
    data["Sf 2 avg"] = sum(values_sf2) / len(values_sf2)
    data["D/S 1 avg"] = sum(values_deficit1) / len(values_deficit1)
    data["D/S 2 avg"] = sum(values_deficit2) / len(values_deficit2)

    return data


def get_user_files():
    return db.session.execute(db.select(JsonFile.filename).filter_by(user_id=current_user.id)).scalars().all()

def get_past_exchange():
    return db.session.execute(db.select(PastExchange.filename).filter_by(user_id=current_user.id)).scalars().all()

def get_json(filename_selected):
    return db.session.execute(db.select(JsonFile.json_data).filter_by(filename=filename_selected)).scalar()

#def plot_values(_label, _data, _name):
#    print("Plotting: " + _name)
#    ldata = _data.copy()
#    
#    # Define full month names and their corresponding indices
#    full_months = [
#        "January", "February", "March", "April", "May", "June", 
#        "July", "August", "September", "October", "November", "December"
#    ]
#    short_months = [m[0] for m in full_months]  # Extract first letter of each month
#    month_index = {m: i for i, m in enumerate(full_months)}
#
#    # Get starting month from "Mese di partenza"
#    start_month = ldata.get("Mese di partenza", "January")  # Default to "January" if missing
#    start_idx = month_index.get(start_month, 0)  # Get index of start month
#
#    # Rotate month labels and initials
#    rotated_short_months = short_months[start_idx:] + short_months[:start_idx]
#    x = range(1, 13)  # Keep x-axis as 1-12
#
#    for d in _label:
#        print(d)
#        print(ldata[d])
#        if isinstance(ldata[d], float):
#            ldata[d] = [ldata[d]] * 12
#        elif isinstance(ldata[d], list) and len(ldata[d]) < 12:
#            ldata[d] += [ldata[d][-1]] * (12 - len(ldata[d]))  # Extend if too short
#
#        # Rotate the data values to match the shifted months
#        rotated_values = ldata[d][start_idx:] + ldata[d][:start_idx]
#        plt.plot(x, rotated_values[:12], label=d)
#
#    plt.xticks(x, rotated_short_months)  # Display only initials
#    plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4)
#    plt.subplots_adjust(bottom=0.25)  # Adjust bottom margin
#    plt.savefig(f"static/{_name}_plot.png", format='png', dpi=150)
#    plt.close()

def plot_values(_label, _data, _name):
    print("Plotting: " + _name)
    ldata = _data.copy()
    
    # Define full month names and their corresponding indices
    full_months = [
        "October", "November", "December", "January", "February", "March", "April", "May", "June", 
        "July", "August", "September",
    ]
    short_months = [m[0] for m in full_months]  # Extract first letter of each month
    month_index = {m: i for i, m in enumerate(full_months)}

    # Get starting month from "Mese di partenza"
    start_month = ldata.get("Mese di partenza", "January")  # Default to "January" if missing
    start_idx = month_index.get(start_month, 0)  # Get index of start month

    # Rotate month labels and initials
    rotated_short_months = short_months[start_idx:] + short_months[:start_idx]
    x = range(1, 13)  # Keep x-axis as 1-12

    for d in _label:
        print(d)
        print(ldata[d])
        if isinstance(ldata[d], float):
            ldata[d] = [ldata[d]] * 12
        elif isinstance(ldata[d], list) and len(ldata[d]) < 12:
            ldata[d] += [ldata[d][-1]] * (12 - len(ldata[d]))  # Extend if too short

        # Rotate the data values to match the shifted months
        rotated_values = ldata[d][start_idx:] + ldata[d][:start_idx]
        plt.plot(x, ldata[d], label=d)
    plt.xticks(x, rotated_short_months)  # Display only initials
    plt.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=4)
    plt.subplots_adjust(bottom=0.25)  # Adjust bottom margin
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