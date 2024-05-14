from flask import Flask, request, render_template, redirect, url_for, session, send_file
import random
import requests
import sqlite3, datetime
# import pandas as pd
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go
import json
from werkzeug.debug import DebuggedApplication #bring in debugging library

# SERVER CODE!
POST_FREQ = 60
RHT_DB = "server_db_4.db"

GOOGLE_MAPS_API = 'AIzaSyAN7H9v-qOpWw2yscOovxJ8j89WQq8pE9E'
    
app = Flask(__name__)
app.secret_key = "69001231gaurabd"
app.debug=True #enable some debugging
app.wsgi_app = DebuggedApplication(app.wsgi_app, True) #make this a debuggable application

def strip_time(time):
    return datetime.datetime(time.year, time.month, time.day, time.hour, time.minute)

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

def get_stop_time(stop_name):
    df = pd.read_csv('stops.txt')
    stop_id = df[df["stop_name"] == stop_name]['stop_id']
    if len(stop_id) == 0:
        return 'None'
    else:
        try:
            URL = f'https://www.miamidade.gov/transit/WebServices/BusTracker/?RouteID=&Dir=&StopID={str(min(stop_id))}&Sequence='
            response_text = requests.get(url=URL).text
            arrival_time = response_text.split('<Time1>')[1].split('</Time1>')[0]
            if arrival_time[-2:] == ' *':
                arrival_time = arrival_time[:-2]
            return "Next bus arrives in " + arrival_time + "."
        except:
            return 'None'

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] not in ['MIT', 'Miami'] or request.form['password'] != 'admin':
            error = 'Invalid Credentials. Please try again.'
        else:
            session["logged_in"] = request.form['username']
            return redirect('/profile')
    return render_template('login.html', error=error)    

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect("/")

@app.route('/humidity_plot')
def plotter2():
    if ("logged_in" not in session):
        return redirect('login')
    try:
        device_id = str(request.args["id"])
        conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
        c = conn.cursor()  # move cursor into database (allows us to execute commands)
        c.execute('''CREATE TABLE IF NOT EXISTS test_rht_table2 (time timestamp, device real, temp real, humidity real, surface real, device_id varchar(300));''')
        df = pd.read_sql_query("SELECT time, humidity, temp FROM test_rht_table2 WHERE device_id = ? ORDER BY rowid DESC;", conn, params=(device_id,))
        df.rename(columns={'time': 'Datetime'}, inplace=True)
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        if df.shape[0] == 0:
                return 'Not a valid device id :('
    except Exception as e:
        return str(e)
    #make a line plot using pandas:
    fig = px.line(df, x='Datetime', y='humidity', title="Change of Humidity with Time")
    # turn into json object for export and embedding in template:
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    latest_humidity = round(min(df[df['Datetime'] == max(df['Datetime'])]['humidity']), 2)
    latest_temp = min(df[df['Datetime'] == max(df['Datetime'])]['temp'])
    humidity_obj = dict()
    humidity_obj["Current Humidity (in %)"] = latest_humidity
    humidity_obj["Minimum Humidity today (in %)"] = round(min(df['humidity']), 2)
    humidity_obj["Maximum Humidity today (in %)"] = round(max(df['humidity']), 2)
    humidity_obj["Current Heat Index"] = compute_heat_index(latest_humidity, latest_temp)
    return render_template('plot.html', graphJSON=graphJSON, title="Relative Humidity Data", device_id=device_id, temp_obj=humidity_obj, dates=str(int((datetime.datetime.now() - max(df['Datetime'])).total_seconds()//60)))

@app.route('/temp_plot')
def plotter1():
    if "logged_in" in session:
        try:
            device_id = str(request.args["id"])
            conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
            c = conn.cursor()  # move cursor into database (allows us to execute commands)
            c.execute('''CREATE TABLE IF NOT EXISTS test_rht_table2 (time timestamp, device real, temp real, humidity real, surface real, device_id varchar(300));''')
            df = pd.read_sql_query("SELECT time, temp, surface FROM test_rht_table2 WHERE device_id = ? ORDER BY rowid DESC;", conn, params=(device_id,))
            if df.shape[0] == 0:
                return 'Not a valid device id :('
            df.rename(columns={'time': 'Datetime'}, inplace=True)
            df['Datetime'] = pd.to_datetime(df['Datetime'])
            temp_df = df[df['temp'] > -49]
            surface_df = df[df['surface'] > 0]
        except Exception as e:
            return str(e)
        #make a line plot using pandas:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=temp_df['Datetime'], y=temp_df['temp'], mode='lines', name="Air Temperature"))
        fig.add_trace(go.Scatter(x=surface_df['Datetime'], y=surface_df['surface'], mode='lines', name="Surface Temperature"))
        fig.update_xaxes(title_text="Datetime")
        fig.update_yaxes(title_text="Temperature (in F)")
        fig.update_layout(
            title=dict(text="Air and Surface Temperature Plots", font=dict(size=30), automargin=True, yref='paper')
        )
        fig.update_yaxes()
        # turn into json object for export and embedding in template:
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        temp_obj = dict()

        current_date = datetime.datetime.now().date()
        df_curr_day = df[df['Datetime'].dt.date == current_date]
        temp_obj["Current Air Temperature (in F)"] = round(min(df[df['Datetime'] == max(df['Datetime'])]['temp']), 2)

        if (surface_df.shape[0] != 0):
            temp_obj["Current Surface Temperature (in F)"] = round(min(df[df['Datetime'] == max(df['Datetime'])]['surface']), 2)
        if df_curr_day.shape[0] != 0:
            temp_obj["Minimum Temperature Reported Today (in F)"] = round(min(df_curr_day['temp']), 2)
            temp_obj["Maximum Temperature Reported Today (in F)"] = round(max(df_curr_day['temp']), 2)
        else:
            temp_obj["Minimum Temperature Reported Today (in F)"] = '-'
            temp_obj["Maximum Temperature Reported Today (in F)"] = '-'
        if session["logged_in"] == 'MIT':
            temp_obj["Local Temperature Forecasted (in F)"] = get_temperature_api(42.360001, -71.092003)
        elif session["logged_in"] == 'Miami':
            temp_obj["Local Temperature Forecasted (in F)"] = get_temperature_api(25.55, -80.6327)

        return render_template('plot.html', graphJSON=graphJSON, title="Temperature Data", temp_obj=temp_obj, device_id=device_id, dates=str(int((datetime.datetime.now() - max(df['Datetime'])).total_seconds()//60)))
    else:
        return redirect('login')


@app.route('/lux_plot')
def lux_plotter():
    if ("logged_in" not in session):
        return redirect('login')
    try:
        device_id = str(request.args["id"])
        conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
        c = conn.cursor()  # move cursor into database (allows us to execute commands)
        c.execute('''CREATE TABLE IF NOT EXISTS test_lux_table2 (time timestamp, device real, lux real, device_id varchar(300));''')
        df = pd.read_sql_query("SELECT time, lux FROM test_lux_table2 WHERE device_id = ? ORDER BY rowid DESC;", conn, params=(device_id,))
        df.rename(columns={'time': 'Datetime'}, inplace=True)
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        if df.shape[0] == 0:
            return 'Not a valid device id :('
    except Exception as e:
        return str(e)
    #make a line plot using pandas:
    fig = px.line(df, x='Datetime', y='lux', title="Change of Lux with Time")
    # turn into json object for export and embedding in template:
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    current_date = datetime.datetime.now().date()
    today_lux_readings = df[df['Datetime'].dt.date == current_date]
    try:
        highest_lux_datetime = min(today_lux_readings[today_lux_readings['lux'] == max(today_lux_readings['lux'])]['Datetime'])
    except:
        highest_lux_datetime = '-'
    lux_obj = dict()
    lux_obj["Current Lux Reading"] = round(min(df[df['Datetime'] == max(df['Datetime'])]['lux']), 2)
    lux_obj["Time of Maximum Sunlight today"] = str(highest_lux_datetime.hour).zfill(2) + ':' + str(highest_lux_datetime.minute).zfill(2) if highest_lux_datetime != '-' else '-'

    return render_template('plot.html', graphJSON=graphJSON, title="Sunlight Lux Data", temp_obj=lux_obj, device_id=device_id, dates=str(int((datetime.datetime.now() - max(df['Datetime'])).total_seconds()//60)))

@app.route('/occupancy_plot')
def occupancy_plotter():
    if ("logged_in" not in session):
        return redirect('login')
    try:
        device_id = str(request.args["id"])
        conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
        c = conn.cursor()  # move cursor into database (allows us to execute commands)
        c.execute('''CREATE TABLE IF NOT EXISTS test_occupancy_table2 (time timestamp, device real, occupancy real, device_id varchar(300));''')
        df = pd.read_sql_query("SELECT time, occupancy FROM test_occupancy_table2 WHERE device_id = ? ORDER BY rowid DESC;", conn, params=(device_id,))
        df.rename(columns={'time': 'Datetime'}, inplace=True)
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        if df.shape[0] == 0:
            return 'Not a valid device id :('
    except Exception as e:
        return str(e)
    #make a line plot using pandas:
    fig = px.line(df, x='Datetime', y='occupancy', title="Number of People Near Device")
    # turn into json object for export and embedding in template:
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    current_date = datetime.datetime.now().date()
    today_occupancy_readings = df[df['Datetime'].dt.date == current_date]
    try:
        highest_occupancy_datetime = min(today_occupancy_readings[today_occupancy_readings['occupancy'] == max(today_occupancy_readings['occupancy'])]['Datetime'])
    except:
        highest_occupancy_datetime = '-'
    occupancy_obj = dict()
    occupancy_obj["Current Number of People"] = str(int(min(df[df['Datetime'] == max(df['Datetime'])]['occupancy'])))
    occupancy_obj["Time of Highest Occupancy today"] = str(highest_occupancy_datetime.hour).zfill(2) + ':' + str(highest_occupancy_datetime.minute).zfill(2) if highest_occupancy_datetime != '-' else '-'
    occupancy_obj["Number of People during Highest Occupancy"] = str(int(min(df[df['Datetime'] == highest_occupancy_datetime]['occupancy']))) if highest_occupancy_datetime != '-' else '-'
    occupancy_obj["Fraction of Times with more than 10 people around"] = str(int(df[df['occupancy'] > 10].shape[0]/df.shape[0]*100)) + "%"

    return render_template('plot.html', graphJSON=graphJSON, title="Occupancy Data", device_id=device_id, temp_obj=occupancy_obj, dates=str(int((datetime.datetime.now() - max(df['Datetime'])).total_seconds()//60)))

@app.route('/get_data', methods=['POST'])
def send_info():
    data_type = request.form['data_type']
    device_id = request.form['id']
    if data_type == 'Temperature Data':
        conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
        c = conn.cursor()  # move cursor into database (allows us to execute commands)
        c.execute('''CREATE TABLE IF NOT EXISTS test_rht_table2 (time timestamp, device real, temp real, humidity real, surface real, device_id varchar(300));''')
        df = pd.read_sql_query("SELECT time, temp, surface FROM test_rht_table2 WHERE device_id = ? ORDER BY rowid DESC;", conn, params=(device_id,))
        df.rename(columns={'time': 'Datetime'}, inplace=True)
        df.to_csv('temperature.csv', index=False)
        return send_file('temperature.csv')
    elif data_type == 'Relative Humidity Data':
        conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
        c = conn.cursor()  # move cursor into database (allows us to execute commands)
        c.execute('''CREATE TABLE IF NOT EXISTS test_rht_table2 (time timestamp, device real, temp real, humidity real, surface real, device_id varchar(300));''')
        df = pd.read_sql_query("SELECT time, humidity FROM test_rht_table2 WHERE device_id = ? ORDER BY rowid DESC;", conn, params=(device_id,))
        df.rename(columns={'time': 'Datetime'}, inplace=True)
        df.to_csv('humidity.csv', index=False)
        return send_file('humidity.csv')
    elif data_type == 'Sunlight Lux Data':
        conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
        c = conn.cursor()  # move cursor into database (allows us to execute commands)
        c.execute('''CREATE TABLE IF NOT EXISTS test_lux_table2 (time timestamp, device real, lux real, device_id varchar(300));''')
        df = pd.read_sql_query("SELECT time, lux FROM test_lux_table2 WHERE device_id = ? ORDER BY rowid DESC;", conn, params=(device_id,))
        df.rename(columns={'time': 'Datetime'}, inplace=True)
        df.to_csv('soc.csv', index=False)
        return send_file('soc.csv')
    elif data_type == 'Occupancy Data':
        conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
        c = conn.cursor()  # move cursor into database (allows us to execute commands)
        c.execute('''CREATE TABLE IF NOT EXISTS test_occupancy_table2 (time timestamp, device real, occupancy real, device_id varchar(300));''')
        df = pd.read_sql_query("SELECT time, occupancy FROM test_occupancy_table2 WHERE device_id = ? ORDER BY rowid DESC;", conn, params=(device_id,))
        df.rename(columns={'time': 'Datetime'}, inplace=True)
        df.to_csv('occupancy.csv', index=False)
        return send_file('occupancy.csv')
    else:
        return "Oops, csv file does not exist"
    

@app.route('/profile')
def profile():
    if "logged_in" not in session:
        return redirect('login')
    conn = sqlite3.connect(RHT_DB) 
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS device_test3 (id real, name text, user text, tilted text);''') 
    prev_data = c.execute('''SELECT id, name, tilted FROM device_test3 WHERE user = ? ORDER BY rowid DESC ;''', (session["logged_in"],)).fetchall()
    conn.close()
    devices = [{'id': int(data[0]), 'name': data[1], 'tilted': data[2]} for data in prev_data]

    if (session["logged_in"] == 'Miami'):
        for device in devices:
            stop_time = get_stop_time(device['name'])
            print(stop_time)
            if stop_time != 'None':
                device["arrival"] = stop_time

    return render_template('profile.html', devices=devices, user=session["logged_in"], API_KEY=GOOGLE_MAPS_API)

@app.route('/change_name', methods=['POST'])
def change_device_name():
    device_id = float(request.args['device_id'])
    conn = sqlite3.connect(RHT_DB) 
    c = conn.cursor()
    c.execute('''UPDATE device_test3 SET name = ? WHERE (id = ? AND user = ?);''', (request.form["device_name"], device_id,session["logged_in"])) 
    conn.commit()
    conn.close()
    return redirect('/profile')

@app.route('/delete_device', methods=['POST'])
def delete_device():
    device_id = float(request.args['device_id'])
    conn = sqlite3.connect(RHT_DB) 
    c = conn.cursor()
    c.execute('''DELETE FROM device_test3 WHERE (id = ? AND user = ?);''', (device_id,session["logged_in"],)) 
    conn.commit()
    conn.close()
    return redirect('/profile')

@app.route('/add_device', methods=['POST'])
def add_device():
    device_name = request.form["device_name"]
    device_id = float(request.form["device_id"])
    conn = sqlite3.connect(RHT_DB) 
    c = conn.cursor()
    c.execute('''INSERT INTO device_test3 VALUES (?, ?, ?, ?);''', (device_id, device_name, session["logged_in"], 'false')) 
    conn.commit()
    conn.close()
    return redirect('/profile')

@app.route("/posty", methods=["POST", "GET"])
def alternate_testing():
    if request.method == 'POST':
        try:
            json_dict = request.get_json()
            device_id = json_dict["id"]
            temp_arr = json_dict["temp"]
            humidity_arr = json_dict["humidity"]
            lux_arr = json_dict["lux"]
            current_time = datetime.datetime.now()

            conn = sqlite3.connect(RHT_DB)  
            c = conn.cursor()  
            c.execute('''CREATE TABLE IF NOT EXISTS test_rht_table (time timestamp, device real, temp real, humidity real, device_id varchar(300));''')
            c.execute('''CREATE TABLE IF NOT EXISTS test_lux_table (time timestamp, device real, lux real, device_id varchar(300));''')
            for i in range(len(temp_arr)):
                c.execute('''INSERT into test_rht_table VALUES (?,?,?,?,?);''', (current_time - datetime.timedelta(minutes=POST_FREQ - POST_FREQ*1//len(temp_arr)) + datetime.timedelta(minutes=(POST_FREQ*i)//len(temp_arr)), 0, temp_arr[i], humidity_arr[i],str(device_id),))
            for i in range(len(lux_arr)):
                c.execute('''INSERT into test_lux_table VALUES (?,?,?,?);''', (current_time - datetime.timedelta(minutes=POST_FREQ) + datetime.timedelta(minutes=(POST_FREQ*i)//len(lux_arr)), 0, lux_arr[i], str(device_id),))
            conn.commit()
            conn.close()
            return str(datetime.datetime.now().hour)
        except Exception as error:
            return error
    else:
        try:
            conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
            c = conn.cursor()  # move cursor into database (allows us to execute commands)
            c.execute('''CREATE TABLE IF NOT EXISTS test_rht_table (time timestamp, device real, temp real, humidity real);''') 
            c.execute('''CREATE TABLE IF NOT EXISTS test_lux_table (time timestamp, device real, lux real);''') 
            prev_temp_data = c.execute('''SELECT time, device_id, temp, humidity FROM test_rht_table ORDER BY rowid DESC;''').fetchall()
            prev_lux_data = c.execute('''SELECT time, device_id, lux FROM test_lux_table ORDER BY rowid DESC;''').fetchall()
            outs = "Existing Temp Data: <br>"
            for t in prev_temp_data:
                outs += f"time: {t[0]}, device: {t[1]}, temp: {t[2]}, humidity: {t[3]}! <br>"
            outs += "Existing Lux Data: <br>"
            for t in prev_lux_data:
                outs += f"time: {t[0]}, device: {t[1]}, lux: {t[2]}! <br>"
            return outs
        except Exception as e:
            return 'Error: ' +str(e)

@app.route("/post_test2", methods=["POST", "GET"])
def testing2():
    if request.method == 'POST':
        try:
            current_time = datetime.datetime.now()
            json_dict = request.get_json()
            device_id = json_dict["id"]
            temp_arr = json_dict["temp"]
            humidity_arr = json_dict["humidity"]
            lux_arr = json_dict["lux"]
            occupancy_arr = json_dict["occupancy"]
            pressure_arr = json_dict["pressure"]
            surface_arr = json_dict["surface"]
            try:
                tilt_info = int(json_dict["isTilted"])
                tilted = 'true' if (tilt_info == 1) else 'false'
                c = conn.cursor()
                c.execute('''UPDATE device_test3 SET tilted = ? WHERE id = ?;''', (tilted, int(device_id),)) 
                conn.commit()
                conn.close()
            except:
                pass
            conn = sqlite3.connect(RHT_DB)  
            c = conn.cursor()  
            c.execute('''CREATE TABLE IF NOT EXISTS test_occupancy_table2 (time timestamp, device real, occupancy real, device_id varchar(300));''')
            c.execute('''CREATE TABLE IF NOT EXISTS test_rht_table2 (time timestamp, device real, temp real, humidity real, surface real, device_id varchar(300));''')
            c.execute('''CREATE TABLE IF NOT EXISTS test_lux_table2 (time timestamp, device real, lux real, device_id varchar(300));''')
            c.execute('''CREATE TABLE IF NOT EXISTS test_pressure_table2 (time timestamp, device real, pressure real, device_id varchar(300));''')
            for i in range(len(occupancy_arr)):
                c.execute('''INSERT into test_occupancy_table2 VALUES (?,?,?,?);''', (current_time - datetime.timedelta(minutes=POST_FREQ - POST_FREQ*1//len(occupancy_arr)) + datetime.timedelta(minutes=(POST_FREQ*i)/len(occupancy_arr)), 0, occupancy_arr[i], str(int(str(device_id).split(':')[-1], 16)),))
            for i in range(len(temp_arr)):
                c.execute('''INSERT into test_rht_table2 VALUES (?,?,?,?,?,?);''', (current_time - datetime.timedelta(minutes=POST_FREQ - POST_FREQ*1//len(temp_arr)) + datetime.timedelta(minutes=(POST_FREQ*i)/len(temp_arr)), 0, temp_arr[i], humidity_arr[i], surface_arr[i],str(int(str(device_id).split(':')[-1], 16)),))
            for i in range(len(lux_arr)):
                c.execute('''INSERT into test_lux_table2 VALUES (?,?,?,?);''', (current_time - datetime.timedelta(minutes=POST_FREQ - POST_FREQ*1//len(lux_arr)) + datetime.timedelta(minutes=(POST_FREQ*i)/len(lux_arr)), 0, lux_arr[i],str(int(str(device_id).split(':')[-1], 16)),))
            for i in range(len(pressure_arr)):
                c.execute('''INSERT into test_pressure_table2 VALUES (?,?,?,?);''', (current_time - datetime.timedelta(minutes=POST_FREQ - POST_FREQ*1//len(pressure_arr)) + datetime.timedelta(minutes=(POST_FREQ*i)/len(pressure_arr)), 0, pressure_arr[i],str(int(str(device_id).split(':')[-1], 16)),))
            conn.commit()
            conn.close()
            return str(datetime.datetime.now().hour)
        except Exception as error:
            return error
    else:
        try:
            conn = sqlite3.connect(RHT_DB)  # connect to that database (will create if it doesn't already exist)
            c = conn.cursor()  # move cursor into database (allows us to execute commands)
            c.execute('''CREATE TABLE IF NOT EXISTS test_occupancy_table2 (time timestamp, device real, occupancy real, device_id varchar(300));''')
            c.execute('''CREATE TABLE IF NOT EXISTS test_rht_table2 (time timestamp, device real, temp real, humidity real, surface real, device_id varchar(300));''')
            c.execute('''CREATE TABLE IF NOT EXISTS test_lux_table2 (time timestamp, device real, lux real, device_id varchar(300));''')
            c.execute('''CREATE TABLE IF NOT EXISTS test_pressure_table2 (time timestamp, device real, pressure real, device_id varchar(300));''')
            prev_occupancy_data = c.execute('''SELECT time, device_id, occupancy FROM test_occupancy_table2 ORDER BY rowid DESC;''').fetchall()
            prev_temp_data = c.execute('''SELECT time, device_id, temp, humidity, surface FROM test_rht_table2 ORDER BY rowid DESC;''').fetchall()
            prev_lux_data = c.execute('''SELECT time, device_id, lux FROM test_lux_table2 ORDER BY rowid DESC;''').fetchall()
            prev_pressure_data = c.execute('''SELECT time, device_id, pressure FROM test_pressure_table2 ORDER BY rowid DESC;''').fetchall()
            outs = "Existing Occupancy Data: <br>"
            for t in prev_occupancy_data:
                outs += f"time: {t[0]}, device: {t[1]}, occupancy: {t[2]}! <br>"
            outs += "Existing Temp Data: <br>"
            for t in prev_temp_data:
                outs += f"time: {t[0]}, device: {t[1]}, temp: {t[2]}, humidity: {t[3]}, surface: {t[4]}! <br>"
            outs += "Existing Lux Data: <br>"
            for t in prev_lux_data:
                outs += f"time: {t[0]}, device: {t[1]}, lux: {t[2]}! <br>"
            outs += "Existing Pressure Data: <br>"
            for t in prev_pressure_data:
                outs += f"time: {t[0]}, device: {t[1]}, pressure: {t[2]}! <br>"
            return outs
        except Exception as e:
            return 'Error: ' +str(e)

@app.route('/firmware.json', methods=['GET'])
def send_firmware_json():
    return send_file('firmware.json')

@app.route('/firmware.bin', methods=['GET'])
def send_firmware_binary():
    return send_file('firmware.bin')

@app.route('/firmware_cellular.json', methods=['GET'])
def send_firmware_cellular_json():
    return send_file('firmware_cellular.json')

@app.route('/firmware_cellular.bin', methods=['GET'])
def send_firmware_cellular_binary():
    return send_file('firmware_cellular.bin')

@app.route('/logo.png', methods=['GET'])
def send_image():
    return send_file('logo.png')

if __name__ == "__main__":
    app.run(host='0.0.0.0')
