import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# STREAMLIT 
st.logo("tra_logo_rgb_HR.png", size='large')
page = 'Bus Planning Checker' # Standaard pagine voordat je een knop hebt geklikt

# SIDEBAR
with st.sidebar:
    st.subheader('Navigation')
    
    if st.button("Bus Planning Checker", icon="🚍", use_container_width=True):
        page = 'Bus Planning Checker'
    if st.button('How It Works', icon="📖", use_container_width=True):
        page = 'How It Works'
    if st.button('Help', icon="❓", use_container_width=True):
        page = 'Help'

   
# OMLOOPPLANNING VALIDEREN
def check_batterij_status(bus_planning, distance_matrix, SOH, min_SOC, consumption_per_km):
    max_capacity = 300 * (SOH / 100)
    min_batterij = max_capacity * (min_SOC / 100)

    # Verwerk tijd
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], format='%H:%M')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], format='%H:%M')

    # DataFrame samenvoegen
    df = pd.merge(bus_planning, distance_matrix, on=['startlocatie', 'eindlocatie', 'buslijn'], how='left')

    # Energieverbruik berekenen met minimumwaarde
    df['consumptie (kWh)'] = (df['afstand in meters'] / 1000) * max(consumption_per_km, 0.7)

    # Idle verbruik
    df.loc[df['activiteit'] == 'idle', 'consumptie (kWh)'] = 0.01

    # Laadsnelheden
    charging_speed_90 = 450 / 60
    charging_speed_10 = 60 / 60

    battery_level = max_capacity
    vorig_omloopnummer = None

    issues = []

    for i, row in df.iterrows():
        next_start_time = bus_planning['starttijd'].iloc[i + 1] if i + 1 < len(bus_planning) else None

        # Nieuwe omloop controle
        if row['omloop nummer'] != vorig_omloopnummer:
            battery_level = max_capacity  # Reset battery at the start of a new route

        # Opladen
        if row['activiteit'] == 'opladen':
            charging_duration = (row['eindtijd'] - row['starttijd']).total_seconds() / 60
            charge_power = (charging_speed_90 if battery_level <= (SOH * 0.9) else charging_speed_10) * charging_duration
            battery_level = min(battery_level + charge_power, max_capacity)
        else:
            battery_level -= row['consumptie (kWh)']

        battery_level = max(battery_level, 0)  # Zorg dat batterij niet negatief wordt

        if battery_level < min_batterij:
            issues.append(row)

        vorig_omloopnummer = row['omloop nummer']

    if not issues:
        return pd.DataFrame()  # Return empty DataFrame if no issues

    failed_df = pd.DataFrame(issues)
    required_columns = ['omloop nummer', 'starttijd', 'consumptie (kWh)']
    missing_columns = set(required_columns) - set(failed_df.columns)
    if missing_columns:
        raise ValueError(f"Missing columns in output DataFrame: {missing_columns}")

    return failed_df[required_columns]
    

def check_route_continuity(bus_planning):
    """
    Check if the endpoint of route n matches the start point of route n+1.
    Parameters:
        - bus_planning: DataFrame with route data.
    Output: Returns a DataFrame with rows where inconsistencies are found.
    """

    # DataFrame to store rows with issues
    issues = []

    # Check if DataFrame is None or missing required columns
    if bus_planning is None:
        st.error("The 'bus_planning' DataFrame is None.")
        return pd.DataFrame()  # Return empty DataFrame

    required_columns = {'omloop nummer', 'startlocatie', 'eindlocatie', 'starttijd'}
    if not required_columns.issubset(bus_planning.columns):
        missing_columns = required_columns - set(bus_planning.columns)
        st.error(f"Missing columns in 'bus_planning': {missing_columns}")
        return pd.DataFrame()  # Return empty DataFrame

    # Check for NaN values in critical columns
    if bus_planning[['omloop nummer', 'startlocatie', 'eindlocatie', 'starttijd']].isnull().any().any():
        st.error("NaN values found in critical columns of 'bus_planning'.")
        return pd.DataFrame()  # Return empty DataFrame

    # Check route continuity
    for i in range(len(bus_planning) - 1):
        current_end_location = bus_planning.at[i, 'eindlocatie']
        next_start_location = bus_planning.at[i + 1, 'startlocatie']
        omloop_nummer = bus_planning.at[i, 'omloop nummer']
        next_start_time = bus_planning.at[i + 1, 'starttijd']  # Start time of the next route

        if current_end_location != next_start_location:
            # Add the problematic rows to the issues list
            issues.append({
                'omloop nummer': omloop_nummer,
                'current_end_location': current_end_location,
                'next_start_location': next_start_location,
                'next_start_time': next_start_time
            })

    # Create a DataFrame with the issues
    issues_df = pd.DataFrame(issues)

    # Return the DataFrame with inconsistencies
    return issues_df


def driven_rides(bus_planning):
    clean_bus_planning = bus_planning[['startlocatie', 'starttijd', 'eindlocatie', 'buslijn']]
    clean_bus_planning = clean_bus_planning.dropna(subset=['buslijn']) 
    return clean_bus_planning


def every_ride_covered(bus_planning, time_table):
    """
    Check if every ride in the bus planning matches the timetable and return discrepancies.
    Parameters:
        - bus_planning: DataFrame with planned rides.
        - time_table: DataFrame with timetable rides.
    Output:
        - Returns a DataFrame with discrepancies containing 'omloop nummer', 'startlocatie', 'activiteit', 'starttijd'.
    """

    # Ensure columns are correctly named
    if 'vertrektijd' in time_table.columns:
        time_table = time_table.rename(columns={'vertrektijd': 'starttijd'})
    
    # Check if 'starttijd' exists in both DataFrames
    if 'starttijd' not in bus_planning.columns or 'starttijd' not in time_table.columns:
        st.error("Missing start time column in either bus planning or timetable.")
        return pd.DataFrame()  # Return empty DataFrame

    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], errors='coerce')
    time_table['starttijd'] = pd.to_datetime(time_table['starttijd'], errors='coerce')

    # Sort the DataFrames
    bus_planning_sorted = bus_planning.sort_values(by=['startlocatie', 'starttijd', 'eindlocatie', 'buslijn']).reset_index(drop=True)
    time_table_sorted = time_table.sort_values(by=['startlocatie', 'starttijd', 'eindlocatie', 'buslijn']).reset_index(drop=True)

    # Find differences
    difference_bus_planning_to_time_table = bus_planning_sorted.merge(
        time_table_sorted, on=['startlocatie', 'starttijd', 'eindlocatie', 'buslijn'], how='outer', indicator=True
    ).query('_merge == "left_only"')

    difference_time_table_to_bus_planning = bus_planning_sorted.merge(
        time_table_sorted, on=['startlocatie', 'starttijd', 'eindlocatie', 'buslijn'], how='outer', indicator=True
    ).query('_merge == "right_only"')

    # Combine the differences
    issues = pd.concat([difference_bus_planning_to_time_table, difference_time_table_to_bus_planning])

    # Filter to return only the required columns
    if not issues.empty:
        result_df = issues[['omloop nummer', 'startlocatie', 'activiteit', 'starttijd']]
        return result_df

    # If no differences, return an empty DataFrame
    return pd.DataFrame(columns=['omloop nummer', 'startlocatie', 'activiteit', 'starttijd'])


def check_travel_time(bus_planning, distance_matrix):
    """
    Checks if the travel time for each ride is within the expected range.
    Parameters:
        - bus_planning: DataFrame with planned rides.
        - distance_matrix: DataFrame with expected travel time data.
    Output:
        - Returns a DataFrame with discrepancies containing 
          'omloop nummer', 'startlocatie', 'eindlocatie', 'reistijd', 'starttijd'.
    """
    # Check if 'starttijd' and 'eindtijd' columns exist
    if 'starttijd' not in bus_planning.columns or 'eindtijd' not in bus_planning.columns:
        st.error("Missing start time or end time column in bus planning data.")
        return pd.DataFrame()  # Return empty DataFrame
    
    # Convert 'starttijd' and 'eindtijd' to datetime, handling errors
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], format='%H:%M:%S', errors='coerce')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], format='%H:%M:%S', errors='coerce')
    
    # Check for invalid times
    if bus_planning['starttijd'].isna().any() or bus_planning['eindtijd'].isna().any():
        st.error("Found invalid start time or end time entries that could not be converted to time.")
        return pd.DataFrame()  # Return empty DataFrame

    # Calculate difference in minutes
    bus_planning['verschil_in_minuten'] = (bus_planning['eindtijd'] - bus_planning['starttijd']).dt.total_seconds() / 60
    
    # Merge with distance_matrix
    merged_df = pd.merge(
        bus_planning,
        distance_matrix,
        on=['startlocatie', 'eindlocatie', 'buslijn'],
        how='inner'
    )

    # List to collect discrepancies
    issues = []

    # Check if travel time falls within the expected range
    for index, row in merged_df.iterrows():
        if not (row['min reistijd in min'] <= row['verschil_in_minuten'] <= row['max reistijd in min']):
            # Add the failing row with additional computed columns
            issues.append({
                'omloop nummer': row.get('omloop nummer', None),
                'startlocatie': row['startlocatie'],
                'eindlocatie': row['eindlocatie'],
                'reistijd': row['verschil_in_minuten'],
                'starttijd': row['starttijd']
            })

    # Create a DataFrame for discrepancies
    if issues:
        return pd.DataFrame(issues)

    # If no discrepancies, return an empty DataFrame
    return pd.DataFrame(columns=['omloop nummer', 'startlocatie', 'eindlocatie', 'reistijd', 'starttijd'])


def plot_schedule_from_excel(bus_planning):
    """Plot een Gantt-grafiek voor busplanning op basis van een DataFrame."""

    # Controleer of de vereiste kolommen aanwezig zijn
    required_columns = ['starttijd', 'eindtijd', 'buslijn', 'omloop nummer', 'activiteit']
    if not all(col in bus_planning.columns for col in required_columns):
        st.error("One or more necessary columns are missing in bus planning")
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


# KPI's BEREKENEN
def count_buses(bus_planning):
    """Count the number of unique 'omloop nummer' values associated with rides in the given file.

    Args:
        bus_planning (pd.DataFrame): DataFrame containing the bus planning data.

    Returns:
        int: Count of unique 'omloop nummer' values.
    """
    # Ensure 'omloop nummer' column exists
    if 'omloop nummer' not in bus_planning.columns:
        raise ValueError("'omloop nummer' column not found in the data.")
    
    # Drop rows with NaN in 'omloop nummer'
    valid_rows = bus_planning['omloop nummer'].dropna()
    
    # Count unique values
    unique_omloop_numbers = valid_rows.unique()
    
    return len(unique_omloop_numbers)


def calculate_deadhead_time(bus_planning):
    """
    Calculate the total amount of time spent on deadhead trips ("materiaal rit").

    :param file_path: Path to the input CSV file
    :return: Total time spent on deadhead trips in minutes
    """
    # Clean column names to avoid mismatches
    bus_planning.columns = bus_planning.columns.str.strip()

    # Filter rows for "materiaal rit" in the 'activiteit' column
    deadhead_trips = bus_planning[bus_planning['activiteit'] == 'materiaal rit']

    # Convert start and end time columns to datetime
    deadhead_trips['starttijd datum'] = pd.to_datetime(deadhead_trips['starttijd datum'])
    deadhead_trips['eindtijd datum'] = pd.to_datetime(deadhead_trips['eindtijd datum'])

    # Calculate duration for each trip in minutes
    deadhead_trips['duration_minutes'] = (deadhead_trips['eindtijd datum'] - deadhead_trips['starttijd datum']).dt.total_seconds() / 60

    # Sum up all durations
    total_deadhead_time = round(deadhead_trips['duration_minutes'].sum(),0)

    return total_deadhead_time


def calculate_energy_consumption(bus_planning, distance_matrix, consumption_per_km):
    """
    Calculate the total energy consumption of buses based on dynamic calculations.

    :param uploaded_file: DataFrame containing trip details.
    :param distance_matrix: DataFrame containing distance information for trips.
    :param consumption_per_km: Energy consumption rate per kilometer (kWh/km).
    :return: DataFrame with energy consumption per trip and total energy consumed in kWh.
    """
    # Ensure the time columns are in datetime format
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], format='%H:%M')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], format='%H:%M')

    # Merge the trip data with the distance matrix
    df = pd.merge(bus_planning, distance_matrix, on=['startlocatie', 'eindlocatie', 'buslijn'], how='left')

    # Calculate energy consumption for trips in kWh
    df['consumptie (kWh)'] = (df['afstand in meters'] / 1000) * max(consumption_per_km, 0.7)  # Apply a minimum rate

    # Add specific consumption for idle trips
    df.loc[df['activiteit'] == 'idle', 'consumptie (kWh)'] = 0.01

    # Calculate total energy consumption
    total_energy_consumption = round(df['consumptie (kWh)'].sum(),0)

    return total_energy_consumption


# PAGINA'S DEFINIEREN
def bus_checker_page(): 
    st.header("Bus Planning Checker")

    tab1, tab2, tab3 = st.tabs(['Data and Parameters', 'Your Data', 'Validity Checks'])
    
    with tab1:
        # File uploaders
        st.subheader('Data')
        col1, col2 = st.columns(2)
    
        with col1:
            uploaded_file = st.file_uploader("Upload Your Bus Planning Here", type="xlsx")
        with col2:
            given_data = st.file_uploader("Upload Your Time Table Here", type="xlsx")
        
        st.subheader('Parameters')
        SOH =                   st.slider("**State Of Health** - %", 85, 95, 90)
        min_SOC =               st.slider("**Minimum State Of Charge** - %", 5, 25, 10)
        consumption_per_km =    st.slider("**Battery Consumption Per KM** - KwH", 0.7, 2.5, 1.6)

    with tab2:
        # Check if the required files are uploaded
        if not uploaded_file or not given_data:
            st.error("You need to upload your data in the 'Data and Parameters' tab.")
            return  # Stop execution if files are not uploaded
        
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
                st.dataframe(bus_planning, hide_index=True)

                st.write('Gantt Chart Of Your Bus Planning:')
                plot_schedule_from_excel(bus_planning)  
            
                if bus_planning.empty or time_table.empty or distance_matrix.empty:
                    st.error("One or more DataFrames are empty. Please check the uploaded files.")
                    return

    with tab3:
            # Dislay KPIs
            st.subheader('KPIs')
            met_col1, met_col2, met_col3 = st.columns(3)

            try:
                buses_used = count_buses(bus_planning)  
                met_col1.metric('Total Buses Used', buses_used, delta=(buses_used - 20), delta_color="inverse")
            except Exception as e:
                st.error(f'Something went wrong displaying buses: {str(e)}')

            try:
                deadhead_minutes = calculate_deadhead_time(bus_planning)  
                met_col2.metric('Total Deadhead Trips In Minutes', deadhead_minutes)
            except Exception as e:
                st.error(f'Something went wrong displaying deadhead time: {str(e)}')
            
            try: 
                energy_cons = calculate_energy_consumption(bus_planning, distance_matrix, consumption_per_km)
                met_col3.metric('Total Energy Consumed in kW', energy_cons)
            except Exception as e:
                st.error(f'Something went wrong displaying energy consumption: {str(e)}')
                
            st.divider()
            
            # Check Batterij Status
            st.subheader('Battery Status')
            try: 
                battery_problems = check_batterij_status(bus_planning, distance_matrix, SOH, min_SOC, consumption_per_km)
                if battery_problems.empty:
                    st.write('No problems found!')
                else:
                    st.write('Battery dips under minimum State Of Charge')
                    with st.expander('Click to see the affected rows'):
                        st.dataframe(battery_problems)       
            except Exception as e:
                st.error(f'Something went wrong checking battery: {str(e)}')
            
            # Check Route Continuiteit
            st.subheader('Route Continuity')
            try:
                continuity_problems = check_route_continuity(bus_planning)
                if continuity_problems.empty:
                    st.write('No problems found!')
                else:
                    st.write('Start and en location do not line up')
                    with st.expander('Click to see the affected rows'):
                        st.dataframe(continuity_problems)
            except Exception as e:
                st.error(f'Something went wrong checking route continuity: {str(e)}')

            # Gereden Ritten
            try:
                bus_planning = driven_rides(bus_planning)
            except Exception as e:
                st.error(f'Something went wrong checking driven rides: {str(e)}')

            # Iedere Nodige Rit Wordt Gereden
            st.subheader('Ride Coverage')
            try:
                ride_coverage = every_ride_covered(bus_planning, time_table)
                if ride_coverage.empty:
                    st.write('No problems found!')
                else:
                    st.write('Ride coverage issues found')
                    with st.expander('Click to see the affected rows'):
                        st.dataframe(ride_coverage)             
            except Exception as e:
                st.error(f'Something went wrong checking if each ride is covered: {str(e)}')

            # Check Reistijd
            st.subheader('Travel Time')
            try:
                travel_time = check_travel_time(bus_planning, distance_matrix)
                if travel_time.empty:
                    st.write('No problems found!')
                else:
                    st.write('Issues with travel time found')
                    with st.expander('Click to see the affected rows'):
                        st.dataframe(travel_time)  
            except Exception as e:
                st.error(f'Something went wrong checking the travel time: {str(e)}')
    
                   
def how_it_works_page():
    st.header("How It Works")

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
    

def help_page():
    st.header("Help")

    tab1, tab2, tab3 = st.tabs(['How To Use', 'Troubleshooting', 'Error Interpretation'])

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
        st.image('Picture3.png', width=400)

    with tab2:
        st.subheader("**Troubleshooting**")
        st.markdown("""
        **Things to do if you are having trouble uploading your files**
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
        - **Some rides may be missing bus line entries**: Make sure all routes are clearly labeled with their bus lines to avoid mismatches.
        - **Inconsistencies found between bus planning and timetable data**: ensure that all timetable rides are included in the bus planning and vice versa.
        - **Missing start time column in either bus planning or timetable file**: verify both files contain start times for accurate matching.
        - **The calculated travel time for bus line from start location to end location is outside the expected range**: check timing and distance data to ensure accuracy.
        - **Invalid start or end time detected**: check entries for accurate time formats (HH:MM:SS) and ensure times are complete.
        - **Essential columns are missing in the bus planning data**: confirm that all rides have start and end times for reliable analysis.""")


# PAGE SELECTOR
if page == 'Bus Planning Checker':
    bus_checker_page()
elif page == 'How It Works':
    how_it_works_page()
elif page == 'Help':
    help_page()