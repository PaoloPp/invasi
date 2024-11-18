from itertools import cycle
from extensions import db
from models import JsonFile, User
from flask_login import current_user

import matplotlib.pyplot as plt
import os


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


def get_user_files():
    return db.session.execute(db.select(JsonFile.filename).filter_by(user_id=current_user.id)).scalars().all()

def get_json(filename_selected):
    return db.session.execute(db.select(JsonFile.json_data).filter_by(filename=filename_selected)).scalar()

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