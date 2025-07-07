import streamlit as st
import requests
from datetime import datetime, timedelta
from datetime import date
import plotly.express as px
import pandas as pd
from streamlit_folium import st_folium
import folium



# API key for accessing OpenWeather
Api_key = "b512ece5d83613e319c1c55a2055f5be"

# To change once we have actually deployed it in the field
default_lat, default_lon = 27.8, -97.4

#Universal temp unit toggle for both tabs
switch_unit = st.sidebar.radio("Temperature Unit", ["Fahrenheit (°F)", "Celsius (°C)"])

#Still debating whether to integrate this layout: layout_toggle = st.sidebar.radio("Layout Mode", ["Horizontal", "Vertical"])


# Allows user to choose a date range in which the soil moisture is displayed in the graph
today = date.today()
default_start = today - timedelta(days=0)
default_end = today + timedelta(days=3)
sensor_graph_start, sensor_graph_end = st.sidebar.date_input(
"📅 Date Range for Soil Sensor Data:",
[default_start, default_end],
min_value=today - timedelta(days=30),
max_value=today + timedelta(days=30),
key = "graph_range"
)


# Allows user to input the date of which the cotton was planted
planting_date = st.sidebar.date_input(
"🌱 Enter Planting Date:",
min_value = date(2024, 1, 1),
max_value = date.today(),
key = "plant_picker")



#Creates the tabs
first_tab, second_tab = st.tabs(["💧 Soil Moisture Data", "🌤️ Weather & GDD Tracker"])



# All the code for the "Soil Moisture Data" tab
with first_tab:

    # Google sheet connection for data extraction
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

        # Gets average reading of the soil moisture values
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
                display = st.radio('Display as:', ["Graph", "Table"])
        with col2:
                view = st.radio("Display on Graph:", ["Moisture", "Temperature"])



        # Melt moisture
        moist_melt = fnl_table.melt(
            id_vars="Time",
            value_vars=[col for col in fnl_table.columns if "Moisture" in col],
            var_name="Sensor",
            value_name="Moisture (%)"
        )
        moist_melt["Depth"] = moist_melt["Sensor"].str.extract(r"(\d+cm)")

        # Melt temperature
        temp_melt = fnl_table.melt(
            id_vars="Time",
            value_vars=[col for col in fnl_table.columns if "Temp" in col],
            var_name="Sensor",
            value_name=f"Temperature ({temp_unit})"
        )
        temp_melt["Depth"] = temp_melt["Sensor"].str.extract(r"(\d+cm)")

        # Merge on Time and Depth
        melted = pd.merge(
            moist_melt[["Time", "Depth", "Moisture (%)"]],
            temp_melt[["Time", "Depth", f"Temperature ({temp_unit})"]],
            on=["Time", "Depth"],
            how="inner"
        )

            

        # Allow user to select depths to view
        available_depths = ["10cm", "20cm", "30cm", "40cm"]
        if "selected_depths" not in st.session_state:
            st.session_state.selected_depths = []
        selected_depths = st.multiselect("Select depths to display",
            available_depths,
            default=available_depths,
            key ="depth_picker")
        st.session_state.selected_depths = selected_depths
        melted = melted[melted["Depth"].isin(selected_depths)]


        # Creates an alert system that depends on the soil moisture level
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


        # Sets the y-axis label for the graph
        if view == "Moisture":
            y_axis = "Moisture (%)"
        else:
            y_axis = f"Temperature ({temp_unit})"


        # Filter data by selected date range
        melted = melted[(melted["Time"].dt.date >= sensor_graph_start) & (melted["Time"].dt.date <= sensor_graph_end)]

        # Drop the "Sensor Reading" column to simplify the table
        if "Sensor Reading" in melted.columns:
            melted = melted.drop(columns=["Sensor Reading"])

        # Displays the graph depending on the depth selected
        if selected_depths:
            melted = melted[melted["Depth"].isin(selected_depths)]            
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
                 melted["Time"] = melted["Time"].dt.strftime("%b %d, %Y %H:%M")
                 st.dataframe(melted, use_container_width=True, hide_index=True)




        else:
            st.info("Select at least one depth from the dropdown above to display data.")

        # Allows user to download csv file of all the soil moisture data collected by sensors        
        import io

        with st.expander("📥 Download CSV by Depth"):
            col1, col2, col3 = st.columns(3)
            depths = ["All", "10cm", "20cm", "30cm", "40cm"]

            for i, depth in enumerate(depths):
                with [col1, col2, col3][i % 3]:
                    if st.button(depth):
                        # Select columns to include
                        if depth == "All":
                            depth_cols = []
                            for d in ["10cm", "20cm", "30cm", "40cm"]:
                                moist_col = f"{d} Moisture (%)"
                                temp_col = f"{d} Temp ({temp_unit})"
                                if moist_col in fnl_table:
                                    depth_cols.append(moist_col)
                                if temp_col in fnl_table:
                                    depth_cols.append(temp_col)
                        else:
                            moist_col = f"{depth} Moisture (%)"
                            temp_col = f"{depth} Temp ({temp_unit})"
                            depth_cols = []
                            if moist_col in fnl_table:
                                depth_cols.append(moist_col)
                            if temp_col in fnl_table:
                                depth_cols.append(temp_col)

                        # Create and download CSV
                        depth_filtered_df = fnl_table[["Time"] + depth_cols]
                        csv_buffer = io.StringIO()
                        depth_filtered_df.to_csv(csv_buffer, index=False)
                        st.download_button(
                            label=f"⬇ Download {depth} CSV",
                            data=csv_buffer.getvalue(),
                            file_name=f"soil_data_{depth.lower()}.csv",
                            mime="text/csv",
                            key=f"dl_{depth}"
                        )

       



# The enviromental monitor of the deployed sensor
with second_tab:

    sensor_loc = [{"name": "Sensor 1", "lat": 27.7706, "lon": -97.5012}]


    # To change once we have actually deployed it in the field
    default_lat, default_lon = 27.7742, -97.5128

    # Shows the data selected and allows user to choose what to displays
    selected_data = ["Air Temperature", "Humidity", "Wind Speed", "Precipitation"]
    filtering = {
                "Air Temperature": f"Temp ({'°F' if switch_unit == 'Fahrenheit (°F)' else '°C'})",
                "Humidity": "Humidity (%)",
                "Wind Speed": "Wind Speed (mph)",
                "Precipitation": "Precipitation (in)",
    }


    # Converts the celsius into farenheit
    def convert_temp(celsius, to_fahrenheit=True):
        return celsius * 9/5 + 32 if to_fahrenheit else celsius



    # Sets time parameters for mateo api
    start_str = today.strftime("%Y-%m-%d")
    end_str = (today + timedelta(days = 5)).strftime("%Y-%m-%d")

    # For accessing open mateo api
    def open_mateo_dat(lat, lon, start_str, end_str):
        mateo_url = "https://api.open-meteo.com/v1/forecast"
        factors = {
            "latitude": lat,
            "longitude": lon,
            "start_date" : start_str,
            "end_date" : end_str,
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


    #Gives alerts depending on the current weather
    def alerts (temp_c, wind_speed_mph, humidity, precip_in = 0):
        to_fahrenheit = switch_unit == "Fahrenheit (°F)"
        temp_display = temp_c * 9/5 + 32 if to_fahrenheit else temp_c
        temp_unit = "°F" if to_fahrenheit else "°C"
        with st.sidebar.expander("🌦️ Current Field Weather and Alerts", expanded = False):
            st.write(f"Temperature: **{temp_display:.1f}{temp_unit}**")
            st.write(f"Wind Speed: **{wind_speed_mph:.1f}** mph")
            st.write(f"Humidity: **{humidity}**%")
            st.write(f"Precipitation: **{precip_in:.1f}** inches")
            st.markdown("---")
            st.markdown("### ⚠️ Alerts")
            alert_trigg = False

            if to_fahrenheit:
                if temp_display > 85:
                    st.error(f"🌡️ **High Temp Alert:** {temp_display:.1f}{temp_unit} - Crop stress likely.")
            else:
                if temp_display > 29:
                    st.error(f"🌡️**High Temp Alert:** {temp_display:.1f}{temp_unit} - Crop stress likely.")
            
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
    

    # Gets the historical min/max data from open meteo for the calculation of GDD
    def historical_data(lat, lon, start_str, end_str, base_temp = 60, max_temp = 95):
        old_data_url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_str,
            "end_date": end_str,
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": "auto"
        }
        response = requests.get(old_data_url, params = params)
        old_data = response.json()
        old_df = pd.DataFrame({
            "Date": old_data["daily"]["time"],
            "Tmax_c": old_data["daily"]["temperature_2m_max"],
            "Tmin_c": old_data["daily"]["temperature_2m_min"]
        })

        old_df["Tmax_F"] = old_df["Tmax_c"] * 1.8 + 32
        old_df["Tmin_F"] = old_df["Tmin_c"] * 1.8 + 32
        old_df["Tmax_F"] = old_df["Tmax_F"].apply(lambda x: min(x, max_temp))
        old_df["Tmin_F"] = old_df["Tmin_F"].apply(lambda x: max(x, base_temp))
        old_df["GDD"] = ((old_df["Tmax_F"]+old_df["Tmin_F"])/2) - base_temp
        old_df["GDD"] = old_df["GDD"].apply(lambda x: max(0, round(x, 1)))

        return old_df




    # Calculates the heat units
    base_temp_f = 60
    def calc_gdd(forecast_df, base_temp = 60, max_temp = 95):
        forecast_df["Time"] = pd.to_datetime(forecast_df["Time"], errors="coerce")
        forecast_df = forecast_df.dropna(subset=["Time"])
        forecast_df["Date"] = forecast_df["Time"].dt.date

        gdd_data = []
        
        for day in forecast_df["Date"].unique():
            daily_data = forecast_df[forecast_df["Date"] == day]
            if not daily_data.empty:
                t_max_f = daily_data["Temperature (Celsius)"].max() * 9/5 + 32
                t_min_f = daily_data["Temperature (Celsius)"].min() * 9/5 + 32
                t_max_f = min(t_max_f, max_temp)
                t_min_f = max(t_min_f, base_temp)
                gdd = max(0, ((t_max_f + t_min_f) / 2) - base_temp)
                gdd_data.append({"Date": day, "GDD": max(0, round(gdd, 1))})
        return pd.DataFrame(gdd_data)


    # 🌦️ Always show current field alerts in sidebar
    default_weather = rt_weather(default_lat, default_lon)
    if default_weather:
        alerts(
            temp_c=default_weather["temp_c"],
            wind_speed_mph=default_weather["wind_speed_mph"],
            humidity=default_weather["humidity"],
            precip_in=default_weather["precip_in"]
    )


    # TBD Horizontal layout
    #if layout_toggle == "Horizontal":


    # Makes the map and graph equal size
    left_column, right_column = st.columns([3,4])



    # Displays location of current sensor(s) in a map
    with left_column:
    # Adds a heading and a bit of vertical spacing to push the map lower
        st.markdown("### 📍 Sensor(s) Map")
        st.markdown("&nbsp;" * 10, unsafe_allow_html=True)  # Adds a small spacer

        # Always show the marker even if it's not clicked
        sensor_1 = sensor_loc[0]
        map = folium.Map(location=[sensor_1["lat"], sensor_1["lon"]], zoom_start=15)
        for sensor in sensor_loc:
            popup_content = f"""
            <b>{sensor['name']}</b><br>
            Lat: {sensor['lat']:.4f}<br>
            Lon: {sensor['lon']:.4f}
            """  # You can add more fields if needed

            folium.Marker(
                location=[sensor["lat"], sensor["lon"]],
                popup=popup_content,
                tooltip="Click to view data",
                icon=folium.Icon(color="green", icon="info-sign")
            ).add_to(map)

        # Render the map and allow clicks
        map_data = st_folium(map, height=500, returned_objects=["last_object_clicked"])




   





    with right_column:
        view_mode = st.radio("Select View:", ["Heat Unit (GDD)", "Real-time Weather & Forecast"], index=0)

        if view_mode == "Heat Unit (GDD)":
            st.subheader("Heat Unit (GDD) Accumulation")

            if planting_date < date.today():
                hist_df = historical_data(default_lat, default_lon, planting_date.strftime("%Y-%m-%d"), date.today().strftime("%Y-%m-%d"))
                hist_df = hist_df[["Date", "GDD"]]
                hist_df["Date"] = pd.to_datetime(hist_df["Date"]).dt.date
            else:
                hist_df = pd.DataFrame()

            forecast_df = get_forecast(default_lat, default_lon)
            if not forecast_df.empty:
                gdd_df = calc_gdd(forecast_df)
                gdd_df = pd.concat([hist_df, gdd_df], ignore_index=True)
                gdd_df = gdd_df[gdd_df["Date"] >= planting_date]
                st.write(f"Total GDD since {planting_date}: **{gdd_df['GDD'].sum():.1f}**")
                fig = px.bar(gdd_df, x="Date", y="GDD", labels={"GDD": "Heat Units"})
                st.plotly_chart(fig, use_container_width=True)

        elif view_mode == "Real-time Weather & Forecast":
            lat = default_lat
            lon = default_lon

            weather = rt_weather(lat, lon)
            prediction_df = get_forecast(lat, lon)
            meteo_data = open_mateo_dat(lat, lon, start_str, end_str)

            if weather and not prediction_df.empty:
                real_time = weather["timestamp"]
                prediction_df.loc[-1] = {
                    "Time": real_time,
                    "Temperature (Celsius)": weather["temp_c"],
                    "Humidity": weather["humidity"],
                    "Wind": weather["wind_speed_mph"],
                    "Precipitation": weather["precip_in"]
                }
                prediction_df.index = prediction_df.index + 1
                prediction_df.sort_index(inplace=True)

                if not meteo_data.empty:
                    prediction_df["Time"] = pd.to_datetime(prediction_df["Time"])
                    meteo_data["Time"] = pd.to_datetime(meteo_data["Time"])
                    prediction_df = pd.merge_asof(
                        prediction_df.sort_values("Time"),
                        meteo_data.sort_values("Time"),
                        on="Time",
                        direction="nearest",
                        tolerance=pd.Timedelta("1H")
                    )

                prediction_df["Time"] = pd.to_datetime(prediction_df["Time"], errors="coerce")
                prediction_df = prediction_df[
                    (prediction_df["Time"].dt.date >= datetime.strptime(start_str, "%Y-%m-%d").date()) &
                    (prediction_df["Time"].dt.date <= datetime.strptime(end_str, "%Y-%m-%d").date())
                ]

                to_fahrenheit = switch_unit == "Fahrenheit (°F)"
                prediction_df["Display Temp"] = prediction_df["Temperature (Celsius)"].apply(lambda x: convert_temp(x, to_fahrenheit))

                filtering = {
                    "Air Temperature": f"Temp ({'°F' if to_fahrenheit else '°C'})",
                    "Humidity": "Humidity (%)",
                    "Wind Speed": "Wind Speed (mph)",
                    "Precipitation": "Precipitation (in)"
                }

                avail_column = ["Time", "Display Temp", "Humidity", "Wind", "Precipitation"]
                rename_dict = {
                    "Display Temp": filtering["Air Temperature"],
                    "Humidity": filtering["Humidity"],
                    "Wind": filtering["Wind Speed"],
                    "Precipitation": filtering["Precipitation"]
                }

                df_renamed = prediction_df[avail_column].rename(columns=rename_dict)
                df_melt = pd.melt(df_renamed, id_vars=["Time"], var_name="Metric", value_name="Value")

                st.subheader("Sensor 1 Conditions")
                fig = px.line(df_melt, x="Time", y="Value", color="Metric", markers=True, line_shape="spline")
                st.plotly_chart(fig, use_container_width=True)
