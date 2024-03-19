from flask import Flask, request, render_template, redirect, url_for, session
import random
import sqlite3, datetime
# import pandas as pd
import pandas as pd
import plotly
import plotly.express as px
import json
from werkzeug.debug import DebuggedApplication #bring in debugging library


RHT_DB = "/home/gaurabd/efi_test/server_db_4.db"
    
app = Flask(__name__)
app.secret_key = "69001231gaurabd"
app.debug=True #enable some debugging
app.wsgi_app = DebuggedApplication(app.wsgi_app, True) #make this a debuggable application


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

def compute_heat_index(RH, T): 
    HI = -42.379 + 2.04901523*T + 10.14333127*RH - 0.22475541*T*RH - 0.00683783*T*T - 0.05481717*RH*RH + 0.00122874*T*T*RH + 0.00085282*T*RH*RH - 0.00000199*T*T*RH*RH 
    return round(HI)

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

@app.route("/template_test")
def tt():
    now = datetime.datetime.now()
    return render_template('template.html', time_stamp = now)

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
    return render_template('plot.html', graphJSON=graphJSON, title="Relative Humidity Plot")

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
        return render_template('plot.html', graphJSON=graphJSON, title="Temperature Plot")
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
    return render_template('plot.html', graphJSON=graphJSON, title="Soc Plot")



    
if __name__ == "__main__":
    app.run(host='0.0.0.0')
