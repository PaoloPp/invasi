#import numpy as np
#import matplotlib.pyplot as plt
#import pandas as pd
from flask import Flask, render_template, request, flash, redirect, url_for
from itertools import cycle
import json
from set_year import set_year

app = Flask(__name__)
app.secret_key = 'supersecretkey'

def somma_cumulata(_var):
    cumulata = []
    somma = 0
    for i in range(0, len(_var)):
        somma += _var[i]
        #cumulata.append(somma)
    #return cumulata
    return somma

def coeff(_nominalValue, _varCoeff): #Ai, A'i, Ditot, Eipot, Eiirr, Eiind
    coeffValue = float(_nominalValue) * float(_varCoeff)
    return coeffValue

@app.route('/form', methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        vol = ["S", "Winv tot", "Winv aut", "Wo", "A", "A'", "P ev", "P inf", "D ec", "E pot", "E irr", "E ind"]
        keys = ["Cj(A)", "Cj(A')", "Cj(ev)", "Cj(inf)", "Cj(ec)", "Cj(pot)", "Cj(irr)", "Cj(ind)"]
        outj = ["A", "A'", "P ev", "P inf", "D ec", "E pot", "E irr", "E ind"]
        out = ["A*", "A'*", "P ev*", "P inf*", "D ec*", "E pot*", "E irr*", "E ind*"]
        data = {}
        values_tot = []
        values_aitot = []
        values_wi = []

        data["Mese di partenza"] = request.form.get('starting_month')
        
        for v in vol:
            data[v] = request.form.get(f'vol-{vol.index(v) + 1}')

        for k in keys:
            values = []
            for i in range(1, 13):
                values.append(request.form.get(f'coeff-{i}-{keys.index(k) + 1}'))
            data[k] = values

        for k, o in zip(keys, outj):
            values = []
            for i in range(0, 12):
                values.append(coeff(data[o], data[k][i]))
            data[o + " j"] = values

        for o, oj in zip(out, outj):
            data[o] = somma_cumulata(data[oj + " j"])

        for i in range(0, 12):
            values_tot.append(data["D ec j"][i] + data["E pot j"][i] + data["E irr j"][i] + data["E ind j"][i])
        data["Etot j"] = values_tot
        data["Etot*"] = somma_cumulata(data["Etot j"])

        for i in range(0, 12):
            values_aitot.append(data["A j"][i] + data["A' j"][i])
        data["Aitot j"] = values_aitot
        data["Aitot*"] = somma_cumulata(data["Aitot j"])

        for i in range(0, 12):
            values_wi.append(data["Aitot j"][i] - data["Etot j"][i])
        data["w j"] = values_wi
        data["w*"] = somma_cumulata(data["w j"])



        with open('data.json', 'w') as json_file:
            json.dump(data, json_file, indent=4)

        flash('Form successfully submitted!', 'success')
        return redirect(url_for('form'))
    
    return render_template('form.html')

@app.route('/', methods=['GET', 'POST'])
def dashboard():
    # You can pass dynamic data here for the dashboard
    if request.method == 'POST':
        with open('data.json', 'r') as json_file:
            data = json.load(json_file)
    
        months = set_year(data["Mese di partenza"])
        return render_template('dashboard.html', data=data, months=months)
    elif request.method == 'GET':
        return render_template('dashboard.html', data=None)

def main():
    print("Hello World!")


if __name__ == "__main__":
    app.run(debug=True)