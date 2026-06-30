from flask import Flask, request, jsonify, send_from_directory
import pandas as pd
import numpy as np
import json
import datetime
import os

app = Flask(__name__, static_folder='static')

BASE_DATE = datetime.date(1899, 12, 30)
MONTHS = ['2026-05','2026-06','2026-07','2026-08','2026-09','2026-10','2026-11','2026-12']

def serial_to_date(val):
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime('%Y-%m-%d')
    try:
        v = float(val)
        if 40000 < v < 55000:
            return (BASE_DATE + datetime.timedelta(days=int(v))).strftime('%Y-%m-%d')
    except:
        pass
    return None

def extract_sheet(df):
    # Find date columns (row 0 or row 1)
    date_cols = {}
    for row_idx in [0, 1]:
        for j in range(2, df.shape[1]):
            val = df.iloc[row_idx, j]
            d = serial_to_date(val)
            if d:
                date_cols[j] = d
        if date_cols:
            break

    clients = {}
    costs = {}
    cost_section = False

    for i in range(df.shape[0]):
        raw = df.iloc[i, 1]
        if pd.isna(raw):
            continue
        name = str(raw).strip()
        if not name:
            continue

        if name in ['CLIENTE', 'TOTAL', 'CONTROL REVENUE', 'CONTROL EXPENSES',
                    'CONTROL SALDO FINAL', 'Saldo Final', 'Consolidado', 'Control']:
            continue
        if name == 'COST':
            cost_section = True
            continue

        monthly = {}
        weekly = {}
        for j, date in date_cols.items():
            v = df.iloc[i, j]
            try:
                fv = float(v)
                if fv == 0 or np.isnan(fv):
                    continue
            except:
                continue

            month = date[:7]
            monthly[month] = monthly.get(month, 0) + fv

            d = datetime.date.fromisoformat(date)
            week_start = (d - datetime.timedelta(days=d.weekday())).strftime('%Y-%m-%d')
            weekly[week_start] = weekly.get(week_start, 0) + fv

        if cost_section:
            if monthly:
                costs[name] = {'monthly': monthly, 'weekly': weekly}
        else:
            if monthly:
                clients[name] = {'monthly': monthly, 'weekly': weekly}

    return {'clients': clients, 'costs': costs}

def process_excel(filepath):
    result = {}
    sheet_map = {
        'RESUMEN MEX': 'Mexico',
        'RESUMEN USA': 'USA',
        'RESUMEN ARG': 'Argentina'
    }
    xl = pd.ExcelFile(filepath)
    for sheet_name, country in sheet_map.items():
        if sheet_name in xl.sheet_names:
            df = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
            result[country] = extract_sheet(df)
    return result

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No se recibió archivo'}), 400
    file = request.files['file']
    if not file.filename.endswith('.xlsx'):
        return jsonify({'error': 'Solo se aceptan archivos .xlsx'}), 400

    path = '/tmp/uploaded.xlsx'
    file.save(path)

    try:
        data = process_excel(path)
        return jsonify({'ok': True, 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
