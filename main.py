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

@app.route('/coeff', methods=['GET'])
#def coeff(_nominalValue, _varCoeff): #Ai, A'i, Ditot, Eipot, Eiirr, Eiind
def coeff():
    nominalValue = request.args.get('nominalValue')
    varCoeff = request.args.get('varCoeff')
    coeffValue = float(nominalValue) * float(varCoeff)
    #for i in range(0, 12):
    #    _coeffValue[i] = _nominalValue * _varCoeff[i]
    #return _coeffValue
    return '''
              <h1>The nominal value is: {}</h1>
              <h1>The coefficient value is: {}</h1>
              <h1>The result value is: {}'''.format(nominalValue, varCoeff, coeffValue)

@app.route('/form', methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        keys = ["Cj(A)", "Cj(A')", "Cj(ev)", "Cj(inf)", "Cj(ec)", "Cj(pot)", "Cj(irr)", "Cj(ind)"]
        vol = ["S", "Winv tot", "Winv aut", "Wo", "A", "A'", "D ec", "E pot", "E irr", "E ind", "P ev", "P inf"]
        data = {}

        data["Mese di partenza"] = request.form.get('starting_month')
        
        for v in vol:
            data[v] = request.form.get(f'vol-{vol.index(v) + 1}')

        for k in keys:
            values = []
            for i in range(1, 13):
                values.append(request.form.get(f'coeff-{i}-{keys.index(k) + 1}'))
            data[k] = values

        with open('data.json', 'w') as json_file:
            json.dump(data, json_file, indent=4)

        flash('Form successfully submitted!', 'success')
        return redirect(url_for('form'))
    
    return render_template('form.html')

@app.route('/')
def dashboard():
    # You can pass dynamic data here for the dashboard
    data = {
        'title': 'Simple Dashboard',
        'metrics': [
            {'label': 'Users', 'value': 1500},
            {'label': 'Sales', 'value': 320},
            {'label': 'Visitors', 'value': 4587}
        ]
    }
    return render_template('dashboard.html', data=data)

def main():
    print("Hello World!")


if __name__ == "__main__":
    app.run(debug=True)