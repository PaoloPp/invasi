#import numpy as np
#import matplotlib.pyplot as plt
#import pandas as pd
import simplejson as json
from flask import Flask, render_template, request, flash, redirect, url_for
from itertools import cycle
from decimal import Decimal, getcontext
from set_year import set_year

app = Flask(__name__)
app.secret_key = 'supersecretkey'

def somma_cumulata(_var):
    cumulata = []
    somma = 0
    for i in range(0, len(_var)):
        somma += _var[i]
        cumulata.append(round(somma,2))
    return cumulata

def coeff(_nominalValue, _varCoeff): #Ai, A'i, Ditot, Eipot, Eiirr, Eiind
    coeffValue = float(_nominalValue) * float(_varCoeff)
    return coeffValue

@app.route('/form', methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        vol = ["S", "Winv tot", "Winv aut", "Wo", "A", "A'", "P ev", "P inf", "D ec", "E pot", "E irr", "E ind", "E tra"]
        keys = ["Cj(A)", "Cj(A')", "Cj(ev)", "Cj(inf)", "Cj(ec)", "Cj(pot)", "Cj(irr)", "Cj(ind)", "Cj(tra)"]
        outj = ["A", "A'", "P ev", "P inf", "D ec", "E pot", "E irr", "E ind", "E tra"]
        out = ["A*", "A'*", "P ev*", "P inf*", "D ec*", "E pot*", "E irr*", "E ind*", "E tra*"]
        data = {}
        values_tot = []
        values_aitot = []
        values_wi = []
        values_Wi = []
        values_Wistar = []
        values_Wia = []
        values_Wib = []
        values_sfa = []
        values_sfb = []
        values_deficitA = []
        values_deficitB = []

        getcontext().prec = 2

        data["Mese di partenza"] = request.form.get('starting_month')
        
        for v in vol:
            data[v] = round(float(request.form.get(f'vol-{vol.index(v) + 1}')),2)

        for k in keys:
            values = []
            for i in range(1, 13):
                values.append(round(float(request.form.get(f'coeff-{i}-{keys.index(k) + 1}')), 2))
            data[k] = values

        for k, o in zip(keys, outj):
            values = []
            for i in range(0, 12):
                values.append(round(coeff(data[o], data[k][i]),2))
            data[o + " j"] = values

        for o, oj in zip(out, outj):
            data[o] = somma_cumulata(data[oj + " j"])

        for i in range(0, 12):
            values_tot.append(round(float(data["D ec j"][i] + data["E pot j"][i] + data["E irr j"][i] + data["E ind j"][i]),2))
        data["Etot j"] = values_tot
        data["Etot*"] = somma_cumulata(data["Etot j"])

        for i in range(0, 12):
            values_aitot.append(round(float(data["A j"][i] + data["A' j"][i]),2))
        data["Aitot j"] = values_aitot
        data["Aitot*"] = somma_cumulata(data["Aitot j"])

        for i in range(0, 12):
            wi = round(float(data["Aitot j"][i] - data["Etot j"][i]),2)
            Wi = round(float(wi + float(data["Wo"])),2)
            values_wi.append(wi)
            values_Wi.append(Wi)
        data["w j"] = values_wi
        data["W j"] = values_Wi
        data["w*"] = somma_cumulata(data["w j"])

        for i in range(0, 12):
            values_Wistar.append(round(float(data["w j"][i] + data["Wo"]),2))
        data["W*"] = values_Wistar

        for i in range(0, 12):
            if(data["W*"][i] < data["Winv tot"]):
                values_Wia.append(data["W*"][i])
            else: values_Wia.append(data["Winv tot"])

            if(values_Wia[i] < data["Winv tot"]):
                values_sfa.append('0')
            else: values_sfa.append(data["w j"][i])

            if(data["W*"][i] < data["Winv aut"]):
                values_Wib.append(data["W*"][i])
            else: values_Wib.append(data["Winv aut"])

            if(values_Wib[i] < data["Winv aut"]):
                values_sfb.append('0')
            else: values_sfb.append(data["w j"][i])
            values_deficitA.append(round(float(data["w j"][i] - values_sfa[i]),2))
            values_deficitB.append(round(float(data["w j"][i] - values_sfb[i]),2))
        data["Wi A*"] = values_Wia
        data["Wi B*"] = values_Wib
        data["Sf A"] = values_sfa
        data["Sf B"] = values_sfb
        data["Sf A*"] = somma_cumulata(data["Sf A"])
        data["Sf B*"] = somma_cumulata(data["Sf B"])
        data["D/S A j"] = values_deficitA
        data["D/S B j"] = values_deficitB
        data["D/S A*"] = somma_cumulata(data["D/S A j"])
        data["D/S B*"] = somma_cumulata(data["D/S B j"])
        



        with open('data.json', 'w') as json_file:
            json.dump(data, json_file, indent=4, use_decimal=True)

        flash('Form successfully submitted!', 'success')
        return redirect(url_for('form'))
    
    return render_template('form.html')

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    # You can pass dynamic data here for the dashboard
    if request.method == 'POST':
        with open(request.form.get('data_select'), 'r') as json_file:
            data = json.load(json_file)
            print("File opened")
        months = set_year(data["Mese di partenza"])
        print("Starting month set")
        return render_template('dashboard.html', data=data, months=months)
    elif request.method == 'GET':
        return render_template('dashboard.html', data=None)

def main():
    print("Hello World!")


if __name__ == "__main__":
    app.run(debug=True, port=8080)