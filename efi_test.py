from flask import Flask, request, render_template, redirect, url_for, session, send_file
import random
import requests
import sqlite3, datetime
# import pandas as pd
import pandas as pd
import plotly
import plotly.express as px
import json
from werkzeug.debug import DebuggedApplication #bring in debugging library


RHT_DB = "server_db_4.db"
    
app = Flask(__name__)
app.secret_key = "69001231gaurabd"
app.debug=True #enable some debugging
app.wsgi_app = DebuggedApplication(app.wsgi_app, True) #make this a debuggable application


def compute_heat_index(RH, T): 
    HI = -42.379 + 2.04901523*T + 10.14333127*RH - 0.22475541*T*RH - 0.00683783*T*T - 0.05481717*RH*RH + 0.00122874*T*T*RH + 0.00085282*T*RH*RH - 0.00000199*T*T*RH*RH 
    return round(HI)

def get_temperature_api(latitude, longitude):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={str(latitude)}&longitude={str(longitude)}&temperature_unit=fahrenheit&current=temperature_2m"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return float(data['current']['temperature_2m'])
    else:
        return 'None'

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] != 'admin' or request.form['password'] != 'admin':
            error = 'Invalid Credentials. Please try again.'
        else:
            session["logged_in"] = True
            return redirect('/')
    return render_template('login.html', error=error)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect("/")

@app.route("/heat_index", methods=['POST','GET'])
def heat_index_function():
    args = request.args
    if request.method == "POST":
        try:
            rh = float(args['rh'])
            t = float(args['t'])
            soc = float(args['soc'])
            kerberos = args['kerberos']
            if (kerberos != 'gaurabd'):
                return "Sorry, Invalid Access!"
            heat_index = round(compute_heat_index(rh,t))
            conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
            c = conn.cursor()  # move cursor into database (allows us to execute commands)
            c.execute('''CREATE TABLE IF NOT EXISTS rht_table (timing timestamp, rh real,t real, heat_index real, soc real);''') #jodalyst test
            c.execute('''INSERT into rht_table VALUES (?,?,?,?,?);''', (datetime.datetime.now(),rh,t,heat_index, soc))
            conn.commit() # commit commands
            conn.close() # close connection to database
            return 'posted!'
        except Exception as e:
            return str(e)
    else:
        try:
            time = float(args['time'])
            kerberos = args['kerberos']
            conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
            c = conn.cursor()  # move cursor into database (allows us to execute commands)
            c.execute('''CREATE TABLE IF NOT EXISTS rht_table (timing timestamp, rh real,t real, heat_index real, soc real);''') #jodalyst test
            variable_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes = time)
            prev_data = c.execute('''SELECT timing, rh, t, heat_index, soc FROM rht_table WHERE timing > ? ORDER BY rowid DESC;''', (variable_minutes_ago,)).fetchall()

            outs = ""
            for t in prev_data:
                outs += f"time: {t[0]}, rh: {t[1]}, t: {t[2]}, heat_index: {t[3]}, soc: {t[4]}! <br>"
            return outs
        except Exception as e:
            return 'lol' +str(e)

@app.route('/humidity_plot')
def plotter2():
    if ("logged_in" not in session or not session["logged_in"]):
        return redirect('login')
    try:
        conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
        c = conn.cursor()  # move cursor into database (allows us to execute commands)
        c.execute('''CREATE TABLE IF NOT EXISTS rht_table (timing timestamp, rh real,t real, heat_index real, soc real);''')
        df = pd.read_sql_query("SELECT timing, rh FROM rht_table ORDER BY rowid DESC;", conn)
        df.rename(columns={'timing': 'Datetime'}, inplace=True)
    except Exception as e:
        return str(e)
    #make a line plot using pandas:
    fig = px.line(df, x='Datetime', y='rh', title="Change of Humidity with Time")
    # turn into json object for export and embedding in template:
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    humidity_obj = dict()
    humidity_obj["Curr Sensor Reading"] = min(df[df['Datetime'] == max(df['Datetime'])]['rh'])
    humidity_obj["Minimum Humidity"] = min(df['rh'])
    humidity_obj["Maximum Humidity"] = max(df['rh'])
    humidity_obj["Reported Humiidty"] = 78
    return render_template('plot.html', graphJSON=graphJSON, title="Relative Humidity Data", dates=str(datetime.date.today()))

@app.route('/temp_plot')
def plotter1():
    if "logged_in" in session and session["logged_in"]:
        try:
            conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
            c = conn.cursor()  # move cursor into database (allows us to execute commands)
            c.execute('''CREATE TABLE IF NOT EXISTS rht_table (timing timestamp, rh real,t real, heat_index real, soc real);''')
            df = pd.read_sql_query("SELECT timing, t FROM rht_table ORDER BY rowid DESC;", conn)
            df.rename(columns={'timing': 'Datetime'}, inplace=True)
        except Exception as e:
            return str(e)
        #make a line plot using pandas:
        fig = px.line(df, x='Datetime', y='t', title="Change of Temperature with Time")
        # turn into json object for export and embedding in template:
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        temp_obj = dict()
        temp_obj["Curr Sensor Reading"] = min(df[df['Datetime'] == max(df['Datetime'])]['t'])
        temp_obj["Minimum Temperature"] = min(df['t'])
        temp_obj["Maximum Temperature"] = max(df['t'])
        temp_obj["Reported Temperature"] = get_temperature_api('42.360001', '-71.092003')
        return render_template('plot.html', graphJSON=graphJSON, title="Temperature Data", temp_obj=temp_obj, dates=str(datetime.date.today()))
    else:
        return redirect('login')

@app.route('/soc_plot')
def soc_plotter():
    if ("logged_in" not in session or not session["logged_in"]):
        return redirect('login')
    try:
        conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
        c = conn.cursor()  # move cursor into database (allows us to execute commands)
        c.execute('''CREATE TABLE IF NOT EXISTS rht_table (timing timestamp, rh real,t real, heat_index real, soc real);''')
        df = pd.read_sql_query("SELECT timing, soc FROM rht_table ORDER BY rowid DESC;", conn)
        df.rename(columns={'timing': 'Datetime'}, inplace=True)
    except Exception as e:
        return str(e)
    #make a line plot using pandas:
    fig = px.line(df, x='Datetime', y='soc', title="Change of soc with Time")
    # turn into json object for export and embedding in template:
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    temp_obj = dict()
    temp_obj["Curr Battery Reading"] = min(df[df['Datetime'] == max(df['Datetime'])]['soc'])
    temp_obj["Battery Status"] = "Good"
    return render_template('plot.html', graphJSON=graphJSON, title="Soc Data", temp_obj=temp_obj, dates=str(datetime.date.today()))

@app.route('/get_data', methods=['POST'])
def send_info():
    return send_file(RHT_DB)

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route("/occupancy", methods=['POST','GET'])
def occupancy_function():
    args = request.args
    if request.method == "POST":
        try:
            bytes = str(args['bytes'])
            device = int(args['device']) if 'device' in args else 0
            conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
            c = conn.cursor()  # move cursor into database (allows us to execute commands)
            c.execute('''CREATE TABLE IF NOT EXISTS occupy_table (time timestamp, device real, bytes text);''') 
            c.execute('''INSERT into occupy_table VALUES (?,?,?);''', (datetime.datetime.now(),device,bytes,))
            conn.commit()
            conn.close()
            return 'posted!'
        except Exception as e:
            return str(e)
    else:
        try:
            conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
            c = conn.cursor()  # move cursor into database (allows us to execute commands)
            c.execute('''CREATE TABLE IF NOT EXISTS occupy_table (time timestamp, device real, bytes text);''') 
            prev_data = c.execute('''SELECT time, device, bytes FROM occupy_table ORDER BY rowid DESC;''').fetchall()

            outs = ""
            for t in prev_data:
                outs += f"time: {t[0]}, device: {t[1]}, bytes: {t[2]}! <br>"
            return outs
        except Exception as e:
            return 'Error: ' +str(e)
    
if __name__ == "__main__":
    app.run(host='0.0.0.0')
