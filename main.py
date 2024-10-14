#import numpy as np
#import matplotlib.pyplot as plt
#import pandas as pd
from flask import Flask, render_template, request, flash, redirect, url_for
from itertools import cycle
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
        # Extract data from form
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        zipcode = request.form.get('zipcode')
        country = request.form.get('country')

        # Simple validation check
        if not all([name, email, phone, address, city, state, zipcode, country]):
            flash('All fields are required!', 'danger')
            return redirect(url_for('form'))
        
        # Process form data here (e.g., store in a database)
        
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