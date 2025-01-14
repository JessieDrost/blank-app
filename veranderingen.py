import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import statsmodels.api as sm
from datetime import datetime
from matplotlib.patches import Patch

st.image("logo_transdev_klein.png", width=200)

pages = [
    st.Page("bus_check.py", title="🚍 Bus Planning Checker"),
    st.Page("how_it_work.py", title="📖 How It Works"),
    st.Page("help.py", title="❓ Help")
]

page = st.navigation(pages)
page.run()

def check_batterij_status(uploaded_file, distance_matrix, start_batterij=270, min_batterij=30):
    errors = []
    
    # Gegevens inladen en DataFrame samenvoegen
    df = pd.merge(uploaded_file, distance_matrix, on=['startlocatie', 'eindlocatie', 'buslijn'], how='left')

    # Consumptie voor kilometers
    consumption_per_km = (0.7 + 2.5) / 2  
    df['consumptie_kWh'] = (df['afstand in meters'] / 1000) * consumption_per_km

    # Consumptie voor idle activiteiten
    df.loc[df['activiteit'] == 'idle', 'consumptie_kWh'] = 0.01

    # Laadsnelheden instellen
    charging_speed_90 = 450 / 60  # kWh per minuut voor opladen tot 90%
    charging_speed_10 = 60 / 60   # kWh per minuut voor opladen van 90% tot 100%

    # Beginwaarden
    battery_level = start_batterij
    vorig_omloopnummer = df['omloop nummer'].iloc[0]
    # Ensure 'starttijd' column is datetime format, then extract only time for continuity check
    uploaded_file['starttijd'] = pd.to_datetime(uploaded_file['starttijd'], format='%H:%M').dt.time
    # Itereren door de DataFrame
    for i, row in df.iterrows():
        next_start_time = uploaded_file.at[i + 1, 'starttijd'] # Haal de starttijd van de volgende route op
        # Controleer of het een nieuwe omloop is
        if row['omloop nummer'] != vorig_omloopnummer:
            # Energieverbruik afhalen vóór het resetten van de batterij
            battery_level -= row['consumptie_kWh']
            
            # Reset de batterij naar start_batterij
            battery_level = start_batterij

        # Opladen
        if row['activiteit'] == 'opladen':
            # Start- en eindtijd ophalen en de duur berekenen
            start_time = row['starttijd']
            end_time = row['eindtijd']
            charging_duration = (end_time - start_time).total_seconds() / 60

            # Bepaal de laadsnelheid
            if battery_level <= 243:
                charge_power = charging_speed_90 * charging_duration
            else:
                charge_power = charging_speed_10 * charging_duration

            # Opladen en aanpassen van de batterijstatus
            battery_level += charge_power

        else:
            # Verminderen met de consumptie
            battery_level -= row['consumptie_kWh']

        # Controleer of de batterijstatus onder het minimum komt
        if battery_level < min_batterij:
            warning_message = f"Battery under {min_batterij} kWh for bus {row['omloop nummer']} at {next_start_time}"
            st.error(warning_message)

        # Bij nieuwe omloop het omloopnummer updaten
        vorig_omloopnummer = row['omloop nummer']
    
    return errors

def check_route_continuity(bus_planning):
        """ Check if the endpoint of route n matches the start point of route n+1.
        Parameters:
            - bus_planning: DataFrame with route data.
        Output: Print messages if there are inconsistencies.
        """
    
        errors = []
        #Controleer op NaN-waarden in 'omloop nummer'
        if bus_planning is None:
            st.error("NaN values found in 'omloop nummer' column.")
            return errors
        required_columns = {'omloop nummer', 'startlocatie', 'eindlocatie', 'starttijd'}
        if not required_columns.issubset(bus_planning.columns):
            missing_columns = required_columns - set(bus_planning.columns)
            st.error(f"Missing columns in 'bus_planning': {missing_columns}")
            return errors

    # Check for NaN values in critical columns
        if bus_planning[['omloop nummer', 'startlocatie', 'eindlocatie', 'starttijd']].isnull().any().any():
            st.error("NaN values found in critical columns of 'bus_planning'.")
            return errors
        
    # Controleer de continuïteit van de routes
        for i in range(len(bus_planning) - 1):
            current_end_location = bus_planning.at[i, 'eindlocatie']
            next_start_location = bus_planning.at[i + 1, 'startlocatie']
            omloop_nummer = bus_planning.at[i, 'omloop nummer']
            next_start_time = bus_planning.at[i + 1, 'starttijd'] # Haal de starttijd van de volgende route op

            if current_end_location != next_start_location:
                st.error(f"Route continuity issue for bus {omloop_nummer:.0f} at {next_start_time}: "
                        f"ends at {current_end_location} and next route starts at {next_start_location}.")
        return errors

def driven_rides(bus_planning):
    clean_bus_planning = bus_planning[['startlocatie', 'starttijd', 'eindlocatie', 'buslijn']]
    clean_bus_planning = clean_bus_planning.dropna(subset=['buslijn']) 
    return clean_bus_planning

def every_ride_covered(bus_planning, time_table):
    errors = []
        # Ensure columns are correctly named
    if 'vertrektijd' in time_table.columns:
        time_table = time_table.rename(columns={'vertrektijd': 'starttijd'})
    
    # Check if 'starttijd' exists in both DataFrames
    if 'starttijd' not in bus_planning.columns or 'starttijd' not in time_table.columns:
        errors.append("Missing 'starttijd' column in either 'bus_planning' or 'time_table'.")
        return False, errors
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], errors='coerce')
    time_table['starttijd'] = pd.to_datetime(time_table['starttijd'], errors='coerce')
    time_table = time_table.rename(columns={'vertrektijd': 'starttijd'})

    bus_planning_sorted = bus_planning.sort_values(by=['startlocatie', 'starttijd', 'eindlocatie', 'buslijn']).reset_index(drop=True)
    time_table_sorted = time_table.sort_values(by=['startlocatie', 'starttijd', 'eindlocatie', 'buslijn']).reset_index(drop=True)

    difference_bus_planning_to_time_table = bus_planning_sorted.merge(
        time_table_sorted, on=['startlocatie', 'starttijd', 'eindlocatie', 'buslijn'], how='outer', indicator=True
    ).query('_merge == "left_only"')

    difference_time_table_to_bus_planning = bus_planning_sorted.merge(
        time_table_sorted, on=['startlocatie', 'starttijd', 'eindlocatie', 'buslijn'], how='outer', indicator=True
    ).query('_merge == "right_only"')

    if not difference_bus_planning_to_time_table.empty:
        errors.append("Rows only contained in bus planning:")
        errors.append(difference_bus_planning_to_time_table.to_string())
       # st.dataframe(difference_bus_planning_to_time_table)  # Show the differences in Streamlit
        return False, errors

    if not difference_time_table_to_bus_planning.empty:
        errors.append("Rows only contained in timetable:")
        errors.append(difference_time_table_to_bus_planning.to_string())
       # st.dataframe(difference_time_table_to_bus_planning)  # Show the differences in Streamlit
        return False, errors

    # If no differences are found, return success
    if difference_bus_planning_to_time_table.empty and difference_time_table_to_bus_planning.empty:
        return "Bus planning is equal to timetable", errors

    return True, errors

def check_travel_time(bus_planning, distance_matrix):
    errors = []
    
    # Check if 'starttijd' and 'eindtijd' columns exist
    if 'starttijd' not in bus_planning.columns or 'eindtijd' not in bus_planning.columns:
        errors.append("Missing 'starttijd' or 'eindtijd' column in bus planning data.")
        return False, errors
    
    # Convert 'starttijd' and 'eindtijd' to datetime, handling errors
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], format='%H:%M:%S', errors='coerce')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], format='%H:%M:%S', errors='coerce')
    
    # Check if there are any NaT (null) values after conversion
    if bus_planning['starttijd'].isna().any() or bus_planning['eindtijd'].isna().any():
        errors.append("Found invalid 'starttijd' or 'eindtijd' entries that could not be converted to time.")
        st.error(errors[-1])
        return False, errors

    # Calculate difference in minutes
    bus_planning['verschil_in_minuten'] = (bus_planning['eindtijd'] - bus_planning['starttijd']).dt.total_seconds() / 60
    
    # Merge with distance_matrix
    merged_df = pd.merge(
        bus_planning,
        distance_matrix,
        on=['startlocatie', 'eindlocatie', 'buslijn'],
        how='inner'
    )

    # Check if travel time falls within the expected range
    for index, row in merged_df.iterrows():
        if not (row['min reistijd in min'] <= row['verschil_in_minuten'] <= row['max reistijd in min']):
            error_message = (f"Row {index}: The difference in minutes ({row['verschil_in_minuten']:.0f}) "
                             f"is not between {row['max reistijd in min']} and {row['min reistijd in min']} "
                             f"for bus route {row['buslijn']} from {row['startlocatie']} to {row['eindlocatie']}.")
            errors.append(error_message)
            st.error(error_message)  # Display error in Streamlit

    # Return results based on whether errors were found
    if errors:
        return False, errors
    else:
        return True, errors


def plot_schedule_from_excel(bus_planning):
    """Plot een Gantt-grafiek voor busplanning op basis van een DataFrame."""

    # Controleer of de vereiste kolommen aanwezig zijn
    required_columns = ['starttijd', 'eindtijd', 'buslijn', 'omloop nummer', 'activiteit']
    if not all(col in bus_planning.columns for col in required_columns):
        st.error("Een of meer vereiste kolommen ontbreken in de busplanning.")
        return

    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], errors='coerce')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], errors='coerce')

    # Verwijder rijen met NaT in starttijd of eindtijd
    bus_planning = bus_planning.dropna(subset=['starttijd', 'eindtijd'])

    bus_planning['duration'] = (bus_planning['eindtijd'] - bus_planning['starttijd']).dt.total_seconds() / 3600

    min_duration = 0.05  
    bus_planning['duration'] = bus_planning['duration'].apply(lambda x: max(x, min_duration))

    color_map = {
        '400.0': 'blue',
        '401.0': 'yellow',
        'materiaal rit': 'green',
        'idle': 'red',
        'opladen': 'orange'
    }

    bus_planning['buslijn'] = bus_planning['buslijn'].astype(str)

    def determine_color(row):
        if pd.notna(row['buslijn']) and row['buslijn'] in color_map:
            return color_map[row['buslijn']]  
        elif row['activiteit'] in color_map:
            return color_map[row['activiteit']]  
        else:
            return 'gray' 

    bus_planning['color'] = bus_planning.apply(determine_color, axis=1)

    fig, ax = plt.subplots(figsize=(12, 6))
    omloopnummers = bus_planning['omloop nummer'].unique()
    omloop_indices = {omloop: i for i, omloop in enumerate(omloopnummers)}

    for omloop in omloopnummers:
        trips = bus_planning[bus_planning['omloop nummer'] == omloop]

        if trips.empty:
            ax.barh(omloop_indices[omloop], 1, left=0, color='black', edgecolor='black')
            continue

        for _, trip in trips.iterrows():
            starttime = trip['starttijd']
            duration = trip['duration']
            color = trip['color'] 

            ax.barh(omloop_indices[omloop], duration, left=starttime.hour + starttime.minute / 60,
                    color=color, edgecolor='black')

    ax.set_yticks(list(omloop_indices.values()))
    ax.set_yticklabels(list(omloop_indices.keys()))

    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('Bus Number')
    ax.set_title('Gantt Chart for Bus Scheduling')

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='blue', edgecolor='black', label='Regular trip 400'),
        Patch(facecolor='yellow', edgecolor='black', label='Regular trip 401'),
        Patch(facecolor='green', edgecolor='black', label='Deadhead trip'),
        Patch(facecolor='red', edgecolor='black', label='Idle'),
        Patch(facecolor='orange', edgecolor='black', label='Charging')
    ]
 
    ax.legend(handles=legend_elements, title='Legend')

    st.pyplot(fig)

def main(uploaded_file, given_data): 
    if uploaded_file and given_data:
        with st.spinner('Your data is being processed...'): 
            try:
                bus_planning = pd.read_excel(uploaded_file)
                time_table = pd.read_excel(given_data, sheet_name='Dienstregeling')
                distance_matrix = pd.read_excel(given_data, sheet_name="Afstandsmatrix")
            except Exception as e:
                st.error(f"Error reading Excel files: {str(e)}")
                return

            st.write('Your Bus Planning:')
            st.dataframe(bus_planning)

            st.write('Gantt Chart Of Your Bus Planning:')
            plot_schedule_from_excel(bus_planning)  # Hier gebruiken we bus_planning in plaats van uploaded_file

            st.write('There Were Mistakes Found In Your Bus Planning:')
            errors = []

            if bus_planning.empty or time_table.empty or distance_matrix.empty:
                st.error("One or more DataFrames are empty. Please check the uploaded files.")
                return

            try: 
                errors += check_batterij_status(bus_planning, distance_matrix)
            except Exception as e:
                errors.append(f'Something went wrong checking battery: {str(e)}')

            try:
                errors += check_route_continuity(bus_planning) 
            except Exception as e:
                errors.append(f'Something went wrong checking route continuity: {str(e)}')

            try:
                bus_planning = driven_rides(bus_planning)
            except Exception as e:
                errors.append(f'Something went wrong checking driven rides: {str(e)}')

            try:
                errors += every_ride_covered(bus_planning, time_table)  # Corrected from distance_matrix to time_table
            except Exception as e:
                errors.append(f'Something went wrong checking if each ride is covered: {str(e)}')

            try:
                errors += check_travel_time(bus_planning, distance_matrix)
            except Exception as e:
                errors.append(f'Something went wrong checking the travel time: {str(e)}')
                
# Streamlit 
st.title("Bus Planning Checker")
uploaded_file = st.file_uploader("Upload Your Bus Planning Here", type="xlsx")
given_data = st.file_uploader("Upload Your Timetable Here", type="xlsx")

main(uploaded_file, given_data)

import streamlit as st

st.title("Help")

tab1, tab2, tab3 = st.tabs(['How to use', 'Troubleshooting', 'Error interpretation'])

with tab1:
    st.subheader("**Need assistance?**")
    st.write("**This is how to use the app**")

    st.markdown("""1. Go to the navigation panel and select ‘Bus Planning Checker’.""")
    st.image('Picture1.png', width=200)

    st.markdown("""2. You should be presented with the following page. Here you can upload your bus planning and your timetable.""")
    st.image('Picture2.png', width=600)

    st.markdown("""
    ---
    Note:
    - Do not refresh the page after uploading files, this will clear all data
    - Follow the correct upload sequence  to ensure accurate results
    - Both files must be .xlsx files
    ---
    3. Results appear on the same page after uploading both files. You will find:
        - The uploaded bus planning for easy viewing and verification
        - A visualization of the planning to help you identify issues at a glance.
        - A list of detected issues or inconsistencies in your planning""")
    st.image('Picture4.png', width=400)

with tab2:
    st.subheader("**Troubleshooting**")
    st.markdown("""
    **Things to do if you’re having trouble uploading your files**
    - Ensure that the files are .xlsx files. Any other file format will not work
    - Verify that you uploaded the files in the correct order. The bus planning at the top, the timetable at the bottom
    - Verify that the files are complete and contain all required fields. Missing data or headers may result in errors during analysis
    - If the issue persists, try refreshing the page and re-uploading the files""")

with tab3:
    st.subheader("**Error interpretation**")
    st.write("**Not sure what an error means? Here you can find some more explanation**")
    st.markdown("""
    - **Battery under minimum threshold detected**: check route timing and ensure that sufficient charging time is allocated.
    - **Route continuity issue found**: ensure that the endpoint of the previous route matches the start location of the next route.
    - **Some rides may be missing 'buslijn' (bus line) entries**: Make sure all routes are clearly labeled with their bus lines to avoid mismatches.
    - **Inconsistencies found between bus planning and timetable data**: ensure that all timetable rides are included in the bus planning and vice versa.
    - **Missing 'starttijd' column in either bus planning or timetable file**: verify both files contain start times for accurate matching.
    - **The calculated travel time for bus line from start location to end location is outside the expected range**: check timing and distance data to ensure accuracy.
    - **Invalid start or end time detected**: check entries for accurate time formats (HH:MM:SS) and ensure times are complete.
    - **Essential columns are missing in the bus planning data**: confirm that all rides have start and end times for reliable analysis.""")
    
import streamlit as st

st.title("How It Works")

st.write("**The app checks the following conditions:**")

st.markdown("""
1. **Battery Status**: the app checks and ensures that the battery level of the bus does not drop below **10%** of the State of Health, which is **30 kWh**. 
The system accounts for both driving and idle time consumption and models charging times at two rates: a higher rate for charging up to **90%** and a slower rate beyond that. 

2. **Route Continuity**: the app checks that the endpoint of each route aligns with the starting location of the following route to maintain continuity in the bus's journey. 

3. **Travel Time**: the app confirms that the travel time for each route falls within the predefined range. 

4. **Coverage of Scheduled Rides**: the app ensures that every ride listed in the **timetable** is matched in the **bus planning** records. 

5. **Data Consistency**: the app verifies that all critical columns are present in your data. 

6. **Error Reporting**: in cases where errors or discrepancies are found, the app provides detailed error messages. These messages include specific 
information about the issue, such as route numbers, times, and locations, allowing for easy adjusting.
""")