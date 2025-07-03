import streamlit as st
import requests
from datetime import datetime, timedelta
from datetime import date
import plotly.express as px
import pandas as pd
from streamlit_folium import st_folium
import folium



# API key for the open weather data
Api_key = "b512ece5d83613e319c1c55a2055f5be"
default_lat, default_lon = 27.8, -97.4

#Universal toggles for both tabs
switch_unit = st.sidebar.radio("Temperature Unit", ["Fahrenheit (°F)", "Celsius (°C)"])
today = date.today()
default_start = today - timedelta(days=0)
default_end = today + timedelta(days=3)
#layout_toggle = st.sidebar.radio("Layout Mode", ["Horizontal", "Vertical"])

start_date, end_date = st.sidebar.date_input(
    "📅 Date Range:",
    [default_start, default_end],
    min_value=today - timedelta(days=30),
    max_value=today + timedelta(days=30)
)



#Creates the tabs
first_tab, second_tab = st.tabs(["Soil Moisture Sensor", "Nearby Weather and Forecast"])


with first_tab:
    # Google sheet connection
    spread_sheet_id  ="1VUOP7tjQrJBf7oOxeQkOrZoTav6AHeA6E1mkv-ZWJGM"
    spread_sheet_range = "Data!A1:Z"
    sheet_api = "AIzaSyAgJbMa5-_pG9ZP5mIahPNddcOOxqSP1IA"
    sheet_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spread_sheet_id}/values/{spread_sheet_range}?key={sheet_api}"
    spread_res = requests.get(sheet_url)
    spread_data = spread_res.json()



    #Converts to dataframe from spreadsheet
    if "values" in spread_data:
        header=spread_data["values"][0]
        rows = spread_data["values"][1:]
        df = pd.DataFrame(rows, columns = header)
        df.columns = df.columns.str.strip()
        df = pd.DataFrame(rows, columns=header)


    # Cleans Value1 to Value9
        for i in range(1, 9):
            col = f"Value{i}"
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace("+", "", regex=False).astype(float)


            #Splits the temperature and moisture rows
            moist_df = df[df["Type"] == "Moist"].copy().reset_index(drop = True)
            temp_df = df[df["Type"] == "Temp"].copy().reset_index(drop = True)
            

        # Functions for the time string
        def fix_time(time_str):
            if len(time_str) >= 3 and (time_str[-3] == "+" or time_str[-3] == "-"):
                return time_str[:-3] + time_str[-3:] + "00"
            return time_str
        def fix_year(time_str):
            try:
                date_part, time_part = time_str.split(",")
                yy, month, day = date_part.strip().split("/")
                year_int = int(yy)
                full_year = 2000 + year_int  # works for 00–99 = 2000–2099
                return f"{full_year}-{month.zfill(2)}-{day.zfill(2)},{time_part.strip()}"
            except:
                return time_str



        # Fixes timezone and converts the timestamps into python datetime objects
        moist_df["Time"] = moist_df["Time"].apply(fix_time).apply(fix_year)
        temp_df["Time"]  =temp_df["Time"].apply(fix_time).apply(fix_year)

        moist_df["Time"] = pd.to_datetime(moist_df["Time"], format="%Y-%m-%d,%H:%M:%S%z", errors='coerce')
        temp_df["Time"] = pd.to_datetime(temp_df["Time"], format="%Y-%m-%d,%H:%M:%S%z", errors='coerce')


        # Converts the celsius into farenheit
        def convert_temp(celsius, to_fahrenheit=True):
            return celsius * 1.8 + 32 if to_fahrenheit else celsius
        to_fahrenheit = switch_unit == "Fahrenheit (°F)"

        # Gets average reading of the values (left to right)
        def avg(df, a, b):
            return (df[a] + df[b]) / 2
        

        # Builds a final table
        fnl_table =  pd.DataFrame()
        fnl_table["Time"] = moist_df["Time"]
        fnl_table["10cm Moisture (%)"] = avg(moist_df, "Value1", "Value2")
        fnl_table["20cm Moisture (%)"] = avg(moist_df, "Value3", "Value4")
        fnl_table["30cm Moisture (%)"] = avg(moist_df, "Value5", "Value6")
        fnl_table["40cm Moisture (%)"] = avg(moist_df, "Value7", "Value8")

        # Applies the temperature unit conversion
        fnl_table["10cm Temp"] = avg(temp_df, "Value1", "Value2").apply(lambda x: convert_temp(x, to_fahrenheit))
        fnl_table["20cm Temp"] = avg(temp_df, "Value3", "Value4").apply(lambda x: convert_temp(x, to_fahrenheit))
        fnl_table["30cm Temp"] = avg(temp_df, "Value5", "Value6").apply(lambda x: convert_temp(x, to_fahrenheit))
        fnl_table["40cm Temp"] = avg(temp_df, "Value7", "Value8").apply(lambda x: convert_temp(x, to_fahrenheit))
        temp_unit = "°F" if to_fahrenheit else "°C"
        fnl_table.rename(columns={
            "10cm Temp": f"10cm Temp ({temp_unit})",
            "20cm Temp": f"20cm Temp ({temp_unit})",
            "30cm Temp": f"30cm Temp ({temp_unit})",
            "40cm Temp": f"40cm Temp ({temp_unit})",
            }, inplace=True)

        #Allows user to choose what to display
        st.subheader("Soil Moisture and Temperature")

        col1, col2, =st.columns(2)
        with col1:
                view = st.radio("Select view:", ["Moisture", "Temperature"])
        with col2:
                display = st.radio('Display as:', ["Graph", "Table"])


        #Turns the multiple depth columns into one
        if view == "Moisture":
            melted = fnl_table.melt(
                id_vars="Time",
                value_vars=[col for col in fnl_table.columns if "Moisture" in col],
                var_name="Sensor Reading",
                value_name="Moisture (%)"
            )
            melted["Depth"] = melted["Sensor Reading"].str.extract(r"(\d+cm)")
            y_axis = "Moisture (%)"
        else:
            value_name = f"Temperature ({temp_unit})"
            melted = fnl_table.melt(
                id_vars="Time",
                value_vars=[col for col in fnl_table.columns if "Temp" in col],
                var_name="Sensor Reading",
                value_name=value_name
            )
            melted["Depth"] = melted["Sensor Reading"].str.extract(r"(\d+cm)")
            y_axis = value_name
      

        # Allow user to select depths to view
        available_depths = ["10cm", "20cm", "30cm", "40cm"]
        if "selected_depths" not in st.session_state:
            st.session_state.selected_depths = []
        selected_depths = st.multiselect("Select depths to display",
            available_depths,
            default=st.session_state.selected_depths,
            key ="depth_picker")
        st.session_state.selected_depths = selected_depths
        melted = melted[melted["Depth"].isin(selected_depths)]

        with st.sidebar.expander("⚠️ Soil Moisture Alerts", expanded=False):
            recent_row = fnl_table.sort_values("Time").dropna().iloc[-1]
            for depth in available_depths:
                col_name = f"{depth} Moisture (%)"
                if col_name in recent_row:
                    moisture_val = recent_row[col_name]
                    if moisture_val < 15:
                        st.error(f"Low moisture at {depth}: {moisture_val:.1f}% - Cotton under stress")
                    elif moisture_val > 40:
                        st.error(f"Excessive moisture at {depth}: {moisture_val:.1f}% - Risk of root rot and poor aeration")
                    elif 20 <= moisture_val <= 35:
                        st.success(f"Optimal moisture at {depth}: {moisture_val:.1f}%")
                    else:
                        st.info(f"Borderline moisture at {depth}: {moisture_val:.1f}% - Monitor closely")


        # Displays the corresponding data depending on whether the user selected moisture or temperature
        if view == "Moisture":
            active_df = moist_df
        else:
            active_df = temp_df

        # Gets the most earliest and latest dates from the time column of the dataset and filters
        min_date = active_df["Time"].min().date()
        max_date = active_df["Time"].max().date()
        start, end = start_date, end_date


        # Sets the y-axis label for the graph
        if view == "Moisture":
            y_axis = "Moisture (%)"
        else:
            y_axis = f"Temperature ({temp_unit})"


        # Filter data by selected date range
        melted = melted[(melted["Time"].dt.date >= start_date) & (melted["Time"].dt.date <= end_date)]

        if selected_depths:
            melted = melted[melted["Depth"].isin(selected_depths)]            
            # Displays the graph
            if display == "Graph":
                fig = px.line(
                    melted,
                    x = "Time",
                    y=y_axis,                        
                    color  ="Depth",
                    markers = True,
                    title = f"Soil {view} Over Time")
                st.plotly_chart(fig, use_container_width= True)
            else:
                st.dataframe(melted)
        else:
            st.info("Select at least one depth from the dropdown above to display data.")
























# The enviromental monitor of the deployed sensor
with second_tab:
    default_lat, default_lon = 27.8, -97.4
    var_select = st.multiselect("Select Weather Metrics to display",
            ["Temperature", "Humidity", "Wind", "Precipitation","Soil Temp", "UV Index", "Solar Radiation"], default =[])
    
    filtering = {
                "Temperature": f"Temp ({'F' if switch_unit == 'Fahrenheit (°F)' else '°C'})",
                "Humidity": "Humidity (%)",
                "Wind": "Wind Speed (mph)",
                "Precipitation": "Precipitation (in)",
                "Soil Temp": f"Soil Temp ({'°F' if switch_unit == 'Fahrenheit (°F)' else '°C'})",
                "UV Index": "UV Index",
                "Solar Radiation": "Solar Radiation (W/m^2)"
    }
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
            "hourly" : "soil_temperature_0cm,uv_index,shortwave_radiation",
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
                    "uv_index" : "UV Index",
                    "shortwave_radiation" : "Solar Radiation (W/m^2)"
            })
        return pd.DataFrame()

    # Gives the current weathers data
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
    def alerts (temp_c, wind_speed_mph, humidity, soil_temperature_0cm, uv_index = None, precip_in = 0, solar_radiation = None):
        to_fahrenheit = switch_unit == "Fahrenheit (°F)"
        temp_display = temp_c * 9/5 + 32 if to_fahrenheit else temp_c
        temp_unit = "°F" if to_fahrenheit else "°C"
        with st.sidebar.expander("🌦️ Nearby Weather Conditions and Alerts", expanded = False):
            st.write(f"Temperature: **{temp_display:.1f}{temp_unit}**")
            st.write(f"Wind Speed: **{wind_speed_mph:.1f}** mph")
            st.write(f"Soil Temperature: **{soil_temperature_0cm}{temp_unit}**")
            st.write(f"Humidity: **{humidity}**%")
            if solar_radiation is not None:
                st.write(f"Solar Radiation: **{solar_radiation:.1f}** W/m^2")
            if uv_index is not None:
                st.write(f"UV Index: **{uv_index:.1f}**")
            st.write(f"Precipitation: **{precip_in:.1f}** inches")
            st.markdown("---")
            st.markdown("### ⚠️ Alerts")
            alert_trigg = False


            # Temperature alerts
            if to_fahrenheit:
                if temp_display > 85:
                    st.error(f"🌡️ **High Temp Alert:** {temp_display:.1f}{temp_unit} - Crop stress likely.")
            else:
                if temp_display > 29:
                    st.error(f"🌡️**High Temp Alert:** {temp_display:.1f}{temp_unit} - Crop stress likely.")
            
            # UV alerts
            if uv_index is not None:
                if uv_index >= 8:
                    st.error(f"☀️ **Extreme UV Index:** {uv_index:.1f} - Shade vulnerable crops.")
                elif uv_index >= 6:
                    st.error(f"🕶️ **High UV today**: {uv_index:.1f} - Sun protection advised.")
            # Solar Radiation alert
            if solar_radiation is not None:
                if solar_radiation >=2600:
                    st.error(f"**High Solar Radiation:** {solar_radiation:.1f} W/m^2 - Risk of evapotranspiration stress.")
            # Wind alert
            if wind_speed_mph > 25:
                st.error(f"💨 **Strong winds warning**: {wind_speed_mph:.1f} mph - May affect young or shallow crops")

            if precip_in >= 0.5:
                st.info(f"🌧️ **Rain detected:** {precip_in:.1f} inches in last hour -    Monitor soil moisture") 
            
            if not alert_trigg:
                st.success("No current weather alerts")
    
            


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

    # Horizontal layout
    #if layout_toggle == "Horizontal":
    left_colum, right_column = st.columns([3,4])

    
    lat = 26.2
    lon=27.2
    with left_colum:
        st.markdown("Location of the deployed sensor(s)")
        map = folium.Map(location=[lat, lon], zoom_start=7)
        map.add_child(folium.LatLngPopup())

        map_display = st_folium(map, height = 500)




    with right_column:
        weather = rt_weather(lat, lon)
        prediction_df = get_forecast(lat, lon)
        meteo_data = open_mateo_dat(lat, lon, start_date, end_date)
        prediction_df["Time"] = pd.to_datetime(prediction_df["Time"], errors="coerce")
        prediction_df = prediction_df[
                    (prediction_df["Time"].dt.date >= start) &
                    (prediction_df["Time"].dt.date <= end)]
                
        if weather and not prediction_df.empty:
            real_time = weather["timestamp"]
            prediction_df.loc[-1] = {
                "Time": real_time,
                "Temperature (Celsius)" : weather["temp_c"],
                "Humidity" : weather["humidity"],
                "Wind" : weather["wind_speed_mph"],
                "Precipitation" : weather["precip_in"]
                }
            prediction_df.sort_index(inplace=True)

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
            
            #mateo_uv = None
            if not meteo_data.empty and "UV Index" in meteo_data.columns:
                current_time = pd.to_datetime(weather["timestamp"])
                recent_uv = meteo_data[meteo_data["Time"] <= current_time]
                if not recent_uv.empty:
                    mateo_uv = recent_uv.iloc[-1]["UV Index"]

            #recent_soil_temp = None
            #recent_solar = None

            if not meteo_data.empty and "Soil Temp (C)" in meteo_data.columns:
                current_time = pd.to_datetime(weather["timestamp"])
                recent_soil_df = meteo_data[meteo_data["Time"] <= current_time]
                if not recent_soil_df.empty:
                    recent_soil_temp = recent_soil_df.iloc[-1]["Soil Temp (C)"]

            if not meteo_data.empty and "Solar Radiation (W/m^2)" in meteo_data.columns:
                current_time = pd.to_datetime(weather["timestamp"])
                recent_solar_df = meteo_data[meteo_data["Time"] <= current_time]
                if not recent_solar_df.empty:
                    recent_solar = recent_solar_df.iloc[-1]["Solar Radiation (W/m^2)"]


            alerts(
                temp_c = weather["temp_c"],
                wind_speed_mph = weather["wind_speed_mph"],
                humidity = weather["humidity"],
                soil_temperature_0cm =recent_soil_temp,
                solar_radiation = recent_solar,
                uv_index = mateo_uv,
                precip_in = weather["precip_in"]
            )



            # Temperature toggling data for soil temp and air temp
            to_faren = switch_unit == "Fahrenheit (°F)"
                # For graph filtering
                            
            filtering["Soil Temp"] = "Soil Temp (°F)" if to_faren else "Soil Temp (C)"

            prediction_df["Display Temp"] = prediction_df["Temperature (Celsius)"].apply (lambda x : convert_temp (x, switch_unit == "Fahrenheit (°F)"))
            if "Soil Temp (C)" in prediction_df.columns:
                prediction_df["Soil Temp Display"] = prediction_df["Soil Temp (C)"].apply(lambda x: convert_temp(x, to_faren))


            has_uv = "UV Index" in prediction_df.columns and prediction_df["UV Index"].gt(0).any()
            has_solar = "Solar Radiation (W/m^2)" in prediction_df.columns and prediction_df["Solar Radiation (W/m^2)"].notna().any()

            avail_column = ["Time", "Display Temp", "Humidity", "Wind", "Precipitation"]
            if "Soil Temp Display" in prediction_df.columns:
                avail_column.append("Soil Temp Display")
            if has_uv:
                avail_column.append("UV Index")
            if has_solar:
                avail_column.append("Solar Radiation (W/m^2)")



            prediction_df.index = prediction_df.index + 1
            prediction_df.sort_index(inplace = True)
            rename_dict = {
                "Display Temp": filtering["Temperature"],
                "Humidity": filtering["Humidity"],
                "Wind": filtering["Wind"],
                "Precipitation": filtering["Precipitation"]
            }
            if "Soil Temp Display" in prediction_df.columns:
                rename_dict["Soil Temp Display"] = filtering["Soil Temp"]
            if has_uv:
                rename_dict["UV Index"] = filtering["UV Index"]
            if has_solar:
                rename_dict["Solar Radiation (W/m^2)"] = filtering["Solar Radiation"]

        
            horiz_columns = prediction_df[avail_column].rename(columns=rename_dict)
            horiz_filter_columun = pd.melt(horiz_columns, id_vars=["Time"], var_name="Metric", value_name="Value")
            selected_horiz_data = [filtering[m] for m in var_select if m in filtering]
            actual_horiz_filtered = horiz_filter_columun[horiz_filter_columun["Metric"].isin(selected_horiz_data)]


            if var_select:
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
            else:
                 st.info("Select data from the dropdown above to display the graph.")
