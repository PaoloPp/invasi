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
        cumulata.append(somma)
    return cumulata

def coeff(_nominalValue, _varCoeff): #Ai, A'i, Ditot, Eipot, Eiirr, Eiind
    coeffValue = float(_nominalValue) * float(_varCoeff)
    return coeffValue

@app.route('/form', methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        vol = ["S", "Winv tot", "Winv aut", "Wo", "A", "A'", "D ec", "E pot", "E irr", "E ind", "P ev", "P inf"]
        vol2 = ["A", "A'", "P ev", "P inf", "D ec", "E pot", "E irr", "E ind"]
        keys = ["Cj(A)", "Cj(A')", "Cj(ev)", "Cj(inf)", "Cj(ec)", "Cj(pot)", "Cj(irr)", "Cj(ind)"]
        outj = ["Aj", "A'j", "Pj ev", "Pj inf", "Dj ec", "Ej pot", "Ej irr", "Ej ind"]
        out_star = ["A*", "A'*", "A tot*", "D ec*", "P ev*", "P inf*", "E pot*", "Ej irr*", "E ind*", "E tot*", "w*"]
        
        data = {}

        data["Mese di partenza"] = request.form.get('starting_month')
        
        for v in vol:
            data[v] = request.form.get(f'vol-{vol.index(v) + 1}')

        for k in keys:
            values = []
            values_coeff = []
            for i in range(1, 13):
                tmp = request.form.get(f'coeff-{i}-{keys.index(k) + 1}')
                values.append(tmp)
                values_coeff.append(coeff(data[keys.index(k)], tmp))
            data[k] = values



        with open('data.json', 'w') as json_file:
            json.dump(data, json_file, indent=4)

        flash('Form successfully submitted!', 'success')
        return redirect(url_for('form'))
    
    return render_template('form.html')

@app.route('/')
def dashboard():
    # You can pass dynamic data here for the dashboard

    with open('data.json', 'r') as json_file:
        data = json.load(json_file)
    
    months = set_year(data["Mese di partenza"])


    return render_template('dashboard.html', data=data, months=months)

def main():
    print("Hello World!")


if __name__ == "__main__":
    app.run(debug=True)