import streamlit as st
import requests
from datetime import datetime, timedelta
from datetime import date
import plotly.express as px
import pandas as pd
from streamlit_folium import st_folium
import folium



# Data conenction stuff
Api_key = "b512ece5d83613e319c1c55a2055f5be"
switch_unit = st.sidebar.radio("Select Temperature Unit", ["Celsius (°C)", "Fahrenheit (°F)"])
default_lat, default_lon = 27.8, -97.4
user_input = st.sidebar.text_input("Enter a city", value = "Corpus Christi")
var_select = st.sidebar.multiselect("Select to display",
                ["Temperature", "Humidity", "Wind", "Precipitation","Soil Temp", "UV Index"], default =["Temperature"])




#Tabs
first_tab, second_tab = st.tabs(["🌤️ Weather Overview", "💧 Data from soil moisture sensor"])
with first_tab:
    st.header("Environmental Monitor")



# For graph filtering
    filtering = {
        "Temperature":f"Temp ({"F" if switch_unit == 'Fahrenheit (°F)' else "°C"})",
        "Humidity" : "Humidity (%)",
        "Wind" : "Wind Speed (mph)",
        "Precipitation" : "Precipitation (in)",
        "Soil Temp" : "Soil Temp (C)",
        "UV Index" : "UV Index"
                }

# For entering the name in the map
    def coords(location_name):
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={location_name}&limit=1&appid={Api_key}"
        read = requests.get(url)
        if read.status_code == 200 and len(read.json()) > 0:
            result = read.json()[0]
            return result["lat"], result["lon"]
        return None, None
    lat, lon = coords(user_input)
    if lat is None or lon is None:
        st.warning("Please enter a valid name")
        lat, lon = default_lat, default_lon


    # Converts the celsius into farenheit
    def convert_temp(celsius, to_fahrenheit=True):
        return celsius * 9/5 + 32 if to_fahrenheit else celsius


    # Sets time parameters for mateo api
    current = date.today()
    later_time = current + timedelta(days=5)
    start_date = current.strftime("%Y-%m-%d")
    end_date = later_time.strftime("%Y-%m-%d")

    # For accessing open mateo api
    def open_mateo_dat(lat, lon, start_date, end_date):
        mateo_url = "https://api.open-meteo.com/v1/forecast"
        factors = {
            "latitude": lat,
            "longitude": lon,
            "hourly" : "soil_temperature_0cm,uv_index",
            "start_date" : start_date,
            "end_date" : end_date,
            "timezone" : "auto"
        }
        r_mateo = requests.get(mateo_url, params = factors)
        if r_mateo.status_code == 200:
            mateo_data = r_mateo.json()
            if "hourly" in mateo_data:
                mateo_df = pd.DataFrame(mateo_data["hourly"])
                mateo_df["time"] = pd.to_datetime(mateo_df["time"])
                return mateo_df.rename(columns={
                    "time" : "Time",
                    "soil_temperature_0cm" : "Soil Temp (C)",
                    "uv_index" : "UV Index"
            })
        return pd.DataFrame()

    # Current weather
    def rt_weather(lat, lon):
        current_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={Api_key}&units=metric"
        r = requests.get(current_url)
        if r.status_code == 200:
            d = r.json()
            rain = d.get("rain", {}).get("1h", 0)
            snow = d.get("snow", {}).get("1h", 0)
            precip_mm = rain + snow
            precip_in = round(precip_mm / 25.4, 2)

            return {
                "temp_c": d["main"]["temp"],
                "humidity": d["main"]["humidity"],
                "wind_speed_mph": d["wind"]["speed"] * 2.23694,
                "precip_in" : precip_in,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        return None

  #Gives alerts depending on current/forecasted weather
    def alerts (temp_c, wind_speed_mph, uv_index = None, precip_in = 0):
        to_fahrenheit = switch_unit == "Fahrenheit (°F)"
        temp_display = temp_c * 9/5 + 32 if to_fahrenheit else temp_c
        temp_unit = "°F" if to_fahrenheit else "°C"
    
        with st.sidebar.expander("🚨 Current weather condition alerts", expanded = False):
            # Temperature alerts
            if to_fahrenheit:
                if temp_display > 85:
                    st.error(f"🌡️ **High Temp Alert:** {temp_display:.2f}{temp_unit} - Crop stress likely.")
            else:
                if temp_display > 29:
                    st.error(f"🌡️**High Temp Alert:** {temp_display:.2f}{temp_unit} - Crop stress likely.")
            
            # UV alerts
            if uv_index is not None:
                if uv_index >= 8:
                    st.error(f"☀️ **Extreme UV Index:** {uv_index:.2f} - Shade vulnerable crops.")
                elif uv_index >= 6:
                    st.error(f"🕶️ **High UV today**: {uv_index:.2f} - Sun protection advised.")

            # Wind alert
            if wind_speed_mph > 25:
                st.error(f"💨 **Strong winds warning**: {wind_speed_mph:.2f} - May affect young or shallow crops")

            if precip_in >= 0.5:
                st.info(f"🌧️ **Rain detected:** {precip_in:.2f} inches in last hour -    Monitor soil moisture") 


    # Gets the predicted data
    def get_forecast(lat, lon):
        predicted_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={Api_key}&units=metric"
        r = requests.get(predicted_url)
        if r.status_code == 200:
            d = r.json()
            times = []
            temps = []
            humidity = []
            wind = []
            rain_add = []
            for entry in d["list"]:
                times.append(entry["dt_txt"])
                temps.append(entry["main"]["temp"])
                humidity.append(entry["main"]["humidity"])
                wind.append(entry["wind"]["speed"] * 2.23964)
                rain = entry.get("rain", {}).get("3h", 0) * 0.0393701
                rain_add.append(rain)

            return pd.DataFrame({
                "Time": times,
                "Temperature (Celsius)": temps,
                "Humidity" : humidity,
                "Wind" : wind,
                "Precipitation" : rain_add,
                })
        return pd.DataFrame()



    # Makes map and chart evenly spaced
    left_colum, right_column = st.columns([1,1.5])
    layout_toggle = st.sidebar.radio("Layout Mode", ["Horizontal", "Vertical"])


    # Horizontal layout
    if layout_toggle == "Horizontal":
        left_colum, right_column = st.columns([3,4])

        user_lat, user_lon = coords(user_input)
        if user_lat is None or user_lon is None:
            st.warning("Invalid location, using default")
            lat, lon = default_lat, default_lon

        lat, lon = user_lat, user_lon

        with left_colum:
            st.markdown("Interactable Map")
            map = folium.Map(location=[lat, lon], zoom_start=7)
            map.add_child(folium.LatLngPopup())
            map_display = st_folium(map, height = 500)

            if map_display and "last_clicked" in map_display and map_display["last_clicked"]:
                lat = map_display["last_clicked"]["lat"]
                lon = map_display["last_clicked"]["lng"]

        with right_column:
            st.success(f"Showing data for {lat:.3f}, {lon:.3f}")

            weather = rt_weather(lat, lon)
            prediction_df = get_forecast(lat, lon)
            meteo_data = open_mateo_dat(lat, lon, start_date, end_date)

            
            if weather and not prediction_df.empty:
                real_time = weather["timestamp"]
                prediction_df.loc[-1] = {
                    "Time": real_time,
                    "Temperature (Celsius)" : weather["temp_c"],
                    "Humidity" : weather["humidity"],
                    "Wind" : weather["wind_speed_mph"],
                    "Precipitation" : weather["precip_in"]
                    }


                if not meteo_data.empty:
                    prediction_df["Time"] = pd.to_datetime(prediction_df["Time"])
                    meteo_data["Time"] = pd.to_datetime(meteo_data["Time"])
                    prediction_df = prediction_df.sort_values("Time")
                    meteo_data = meteo_data.sort_values("Time")
                    prediction_df = pd.merge_asof(
                        prediction_df,
                        meteo_data,
                        on = "Time",
                        direction = "nearest",
                        tolerance = pd.Timedelta("1H")
                    )
                
                mateo_uv = None
                if not meteo_data.empty and "UV Index" in meteo_data.columns:
                    current_time = pd.to_datetime(weather["timestamp"])
                    recent_uv = meteo_data[meteo_data["Time"] <= current_time]
                    if not recent_uv.empty:
                        mateo_uv = recent_uv.iloc[-1]["UV Index"]

                alerts(
                    temp_c = weather["temp_c"],
                    wind_speed_mph = weather["wind_speed_mph"],
                    uv_index = mateo_uv,
                    precip_in = weather["precip_in"]
                )



                # Temperature toggling data for soil temp and air temp
                to_faren = switch_unit == "Fahrenheit (°F)"
                filtering["Soil Temp"] = "Soil Temp (°F)" if to_faren else "Soil Temp (C)"
                prediction_df["Display Temp"] = prediction_df["Temperature (Celsius)"].apply (lambda x : convert_temp (x, switch_unit == "Fahrenheit (°F)"))
                if "Soil Temp (C)" in prediction_df.columns:
                    prediction_df["Soil Temp Display"] = prediction_df["Soil Temp (C)"].apply(lambda x: convert_temp(x, to_faren))


                avail_column = ["Time", "Display Temp", "Humidity", "Wind", "Precipitation"]
                if "Soil Temp Display" in prediction_df.columns:
                    avail_column.append("Soil Temp Display")
                if "UV Index" in prediction_df.columns:
                    avail_column.append("UV Index")



                prediction_df.index = prediction_df.index + 1
                prediction_df.sort_index(inplace = True)
                horiz_columns = prediction_df[avail_column].rename(columns = {
                    "Display Temp" :filtering["Temperature"],     #[f"Temp ({"F" if switch_unit == "Fahrenheit (°F)" else "°C"})"], 
                    "Humidity" : filtering["Humidity"],
                    "Wind" : filtering["Wind"],                    
                    "Precipitation" : filtering["Precipitation"],
                    "Soil Temp Display" : filtering["Soil Temp"],
                    "UV Index" : filtering["UV Index"]
                    }                                          
                                                                                                        )
                horiz_filter_columun = pd.melt(horiz_columns, id_vars=["Time"], var_name = 'Metric', value_name="Value")
                selected_horiz_data = [filtering[m] for m in var_select]
                actual_horiz_filtered = horiz_filter_columun[horiz_filter_columun["Metric"].isin(selected_horiz_data)]


                graph = px.line(
                    actual_horiz_filtered,
                    x = "Time",                    
                    y = "Value",
                    color = "Metric",   
                    title  = f"Real time and predicted data at ({lat:.2f}, {lon:.2f})",
                    markers = True,
                    line_shape= "spline"
                    )
                st.plotly_chart(graph, use_container_width= True)
            
        


    else:  # Vertical layout
        m = folium.Map(location=[lat, lon], zoom_start=7)
        m.add_child(folium.LatLngPopup())
        map_data = st_folium(m, height=500)

        if map_data and map_data.get("last_clicked"):
            lat = map_data["last_clicked"]["lat"]
            lon = map_data["last_clicked"]["lng"]
            st.success(f"Selected location {lat:.3f}, {lon:.3f}")

            weather = rt_weather(lat, lon)
            prediction_df = get_forecast(lat, lon)
            meteo_data = open_mateo_dat(lat, lon, start_date, end_date)

              #Gives alerts depending on current/forecasted weather
            mateo_uv = None
            if not meteo_data.empty and "UV Index" in meteo_data.columns:
                current_time = pd.to_datetime(weather["timestamp"])
                recent_uv = meteo_data[meteo_data["Time"] <= current_time]
                if not recent_uv.empty:
                    mateo_uv = recent_uv.iloc[-1]["UV Index"]
                
            alerts(
                temp_c=weather["temp_c"],
                wind_speed_mph=weather["wind_speed_mph"],
                uv_index=mateo_uv,
                precip_in=weather["precip_in"]
            )

            
               

            if weather and not prediction_df.empty:
                prediction_df.loc[-1] = {
                    "Time": weather["timestamp"],
                    "Temperature (Celsius)": weather["temp_c"],
                    "Humidity": weather["humidity"],
                    "Wind Speed": weather["wind_speed_mph"],
                    "Precipitation" : weather["precip_in"]
                }

                if not meteo_data.empty:
                    prediction_df["Time"]= pd.to_datetime(prediction_df["Time"])
                    meteo_data["Time"] = pd.to_datetime(meteo_data["Time"])
                    prediction_df = prediction_df.sort_values("Time")
                    meteo_data = meteo_data.sort_values("Time")
                    prediction_df = pd.merge_asof(
                            prediction_df,
                            meteo_data,
                            on = "Time",
                            direction = "nearest",
                            tolerance = pd.Timedelta("1H")
                    )


                mateo_uv = None
                if not meteo_data.empty and "UV Index" in meteo_data.columns:
                    current_time = pd.to_datetime(weather["timestamp"])
                    recent_uv = meteo_data[meteo_data["Time"] <= current_time]
                    if not recent_uv.empty:
                        mateo_uv = recent_uv.iloc[-1]["UV Index"]



                # Temperature toggling data for soil temp and air temp
                to_faren = switch_unit == "Fahrenheit (°F)"
                filtering["Soil Temp"] = "Soil Temp (°F)" if to_faren else "Soil Temp (C)"
                prediction_df["Display Temp"] = prediction_df["Temperature (Celsius)"].apply (lambda x : convert_temp (x, switch_unit == "Fahrenheit (°F)"))
                if "Soil Temp (C)" in prediction_df.columns:
                    prediction_df["Soil Temp Display"] = prediction_df["Soil Temp (C)"].apply(lambda x: convert_temp(x, to_faren))


                avail_column = ["Time", "Display Temp", "Humidity", "Wind", "Precipitation"]
                if "Soil Temp Display" in prediction_df.columns:
                    avail_column.append("Soil Temp Display")
                if "UV Index" in prediction_df.columns:
                    avail_column.append("UV Index")




                prediction_df.index += 1
                prediction_df.sort_index(inplace=True)
                vert_colum = prediction_df[avail_column].rename(columns={
                    "Display Temp": filtering["Temperature"],     #f"Temp ({'F' if switch_unit == 'Fahrenheit (°F)' else '°C'})",
                    "Humidity": filtering["Humidity"],
                    "Wind": filtering["Wind"],
                    "Precipitation" : filtering["Precipitation"],
                    "Soil Temp Display" : filtering["Soil Temp"],
                    "UV Index" : filtering["UV Index"]
                })
                vert_filter_column = pd.melt(vert_colum, id_vars="Time", var_name="Metric", value_name="Value")
                selected_vert_data = [filtering[i] for i in var_select]
                actual_vert_filtered = vert_filter_column[vert_filter_column["Metric"].isin(selected_vert_data)]


                chart = px.line(actual_vert_filtered,
                            x="Time",
                            y="Value", 
                            color="Metric",
                            markers=True,
                            line_shape="spline",
                            title=f"Real-time + Forecast at ({lat:.2f}, {lon:.2f})")
                

                st.plotly_chart(chart, use_container_width=True)



    # For 
with second_tab:

    st.header("Data from soil moisture sensor")
     # Google sheet connection
    spread_sheet_id = "1tOu4JqG_leMAkjYdw7KsU7yo7vjJfQjhw1bjww-XP6I"
    spread_sheet_range = "Data!A1:Z1000"
    sheet_api = "AIzaSyAgJbMa5-_pG9ZP5mIahPNddcOOxqSP1IA"
    sheet_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spread_sheet_id}/values/{spread_sheet_range}?key={sheet_api}"

    #Calls the api
    spread_res = requests.get(sheet_url)
    spread_data = spread_res.json()


    #Converts to dataframe from spreadsheet
    if "values" in spread_data:
        header=spread_data["values"][0]
        rows = spread_data["values"][1:]
        spread_df = pd.DataFrame(rows, columns = header)
        st.subheader("Preview of sheets")
        st.write(spread_df.head())
        print("Data extracted")
    else:
        print("No data found")

