import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import seaborn as sns

# STREAMLIT CONFIGURATION
# Display the logo on the Streamlit app
st.logo("tra_logo_rgb_HR.png", size='large')

# Default page when the app starts
page = 'Bus Planning Checker'

# SIDEBAR NAVIGATION
with st.sidebar:
    st.subheader('Navigation')  # Section for navigating through the app
    
    # Buttons to navigate to different sections of the app 
    if st.button("Bus Planning Checker", icon="🚍", use_container_width=True):
        page = 'Bus Planning Checker'
    if st.button('How It Works', icon="📖", use_container_width=True):
        page = 'How It Works'
    if st.button('Help', icon="❓", use_container_width=True):
        page = 'Help'

# VALIDITY FUNCTIONS
def check_battery_status(bus_planning, distance_matrix, SOH, min_SOC, consumption_per_km):
    """
    Validates battery status throughout the bus schedule and adds state of charge (SOC) as a column.

    Args:
        bus_planning (DataFrame): The bus schedule with 'starttijd', 'eindtijd', and other columns.
        distance_matrix (DataFrame): Distances between locations.
        SOH (float): State of Health of the battery as a percentage.
        min_SOC (float): Minimum state of charge required as a percentage.
        consumption_per_km (float): Energy consumption per kilometer in kWh.

    Returns:
        DataFrame: Rows from the schedule where battery status issues occur, with SOC as a column.
    """
    # Calculate battery capacities based on SOH and min_SOC
    max_capacity = 300 * (SOH / 100)  # Maximum battery capacity in kWh
    min_battery = max_capacity * (min_SOC / 100)  # Minimum allowed battery level

    # Convert time columns to datetime for calculations
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], format='%H:%M')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], format='%H:%M')

    # Merge schedule with distance matrix to include distances between locations
    df = pd.merge(bus_planning, distance_matrix, on=['startlocatie', 'eindlocatie', 'buslijn'], how='left')

    # Calculate energy consumption based on distance and consumption per km
    df['consumption (kWh)'] = (df['afstand in meters'] / 1000) * max(consumption_per_km, 0.7)

    # Idle activities consume minimal power
    df.loc[df['activiteit'] == 'idle', 'consumption (kWh)'] = 0.01

    # Charging speeds for different battery levels
    charging_speed_90 = 450 / 60  # Charging speed below 90% SOC in kWh per minute
    charging_speed_10 = 60 / 60   # Charging speed above 90% SOC in kWh per minute

    battery_level = max_capacity  # Initialize battery level
    previous_loop_number = None  # Track the loop number for continuity

    issues = []  # List to log rows with issues
    state_of_charge = []  # Track SOC for each row

    for i, row in df.iterrows():
        next_start_time = bus_planning['starttijd'].iloc[i + 1] if i + 1 < len(bus_planning) else None

        # Reset battery level for new loops
        if row['omloop nummer'] != previous_loop_number:
            battery_level = max_capacity

        # Handle charging activity
        if row['activiteit'] == 'opladen':
            charging_duration = (row['eindtijd'] - row['starttijd']).total_seconds() / 60  # Charging time in minutes
            charge_power = (charging_speed_90 if battery_level <= (max_capacity * 0.9) else charging_speed_10) * charging_duration
            battery_level = min(battery_level + charge_power, max_capacity)  # Cap battery level to max capacity
        else:
            # Subtract energy consumption for other activities
            battery_level -= row['consumption (kWh)']

        battery_level = max(battery_level, 0)  # Ensure battery level is not negative
        state_of_charge.append(battery_level / max_capacity * 100)  # Append SOC as a percentage

        # Log issues if battery falls below the minimum SOC
        if battery_level < min_battery:
            issues.append(row)

        previous_loop_number = row['omloop nummer']

    # Add SOC as a column to the DataFrame
    df['state_of_charge'] = state_of_charge

    # Return rows with issues or an empty DataFrame if no issues are found
    if not issues:
        return pd.DataFrame()

    failed_df = pd.DataFrame(issues)
    failed_df['state of charge'] = df.loc[failed_df.index, 'state_of_charge']  # Add SOC to issue rows

    # Ensure required columns are present in the output
    required_columns = ['omloop nummer', 'starttijd', 'consumption (kWh)', 'state of charge']
    missing_columns = set(required_columns) - set(failed_df.columns)
    if missing_columns:
        raise ValueError(f"Missing columns in output DataFrame: {missing_columns}")

    return failed_df[required_columns]

def check_route_continuity(bus_planning):
    """
    Checks for route continuity issues within the same loop number.

    Args:
        bus_planning (DataFrame): The bus schedule.

    Returns:
        DataFrame: Rows with route continuity issues.
    """
    issues = []

    # Verify necessary columns are present
    required_columns = {'omloop nummer', 'startlocatie', 'eindlocatie', 'starttijd'}
    if not required_columns.issubset(bus_planning.columns):
        missing_columns = required_columns - set(bus_planning.columns)
        st.error(f"Missing columns in 'bus_planning': {missing_columns}")
        return pd.DataFrame()

    # Sort schedule by loop number and start time
    bus_planning = bus_planning.sort_values(by=['omloop nummer', 'starttijd']).reset_index(drop=True)

    for i in range(len(bus_planning) - 1):
        current_row = bus_planning.iloc[i]
        next_row = bus_planning.iloc[i + 1]

        # Check continuity within the same loop number
        if (current_row['omloop nummer'] == next_row['omloop nummer']) & (current_row['eindlocatie'] != next_row['startlocatie']):
            issues.append({
                'omloop nummer': current_row['omloop nummer'],
                'current end location': current_row['eindlocatie'],
                'next start location': next_row['startlocatie'],
                'current end time': current_row['eindtijd'],
                'next start time': next_row['starttijd'],
            })

    return pd.DataFrame(issues)

def driven_rides(bus_planning):
    """
    Filters bus planning data for rides that include a bus line.

    Args:
        bus_planning (DataFrame): The bus schedule.

    Returns:
        DataFrame: Filtered DataFrame with rides containing a bus line.
    """
    return bus_planning[['startlocatie', 'starttijd', 'eindlocatie', 'buslijn']].dropna(subset=['buslijn'])

def every_ride_covered(bus_planning, timetable):
    """
    Checks if every trip in the bus planning is covered in the timetable.

    Args:
        bus_planning (DataFrame): Planned rides.
        timetable (DataFrame): Timetable rides.

    Returns:
        DataFrame: Discrepancies between planning and timetable.
    """
    # Rename column for consistency
    if 'vertrektijd' in timetable.columns:
        timetable = timetable.rename(columns={'vertrektijd': 'starttijd'})

    # Ensure necessary columns are present
    if 'starttijd' not in bus_planning.columns or 'starttijd' not in timetable.columns:
        st.error("Missing 'starttijd' column in bus planning or timetable.")
        return pd.DataFrame()

    # Convert start times to datetime for comparison
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], errors='coerce')
    timetable['starttijd'] = pd.to_datetime(timetable['starttijd'], errors='coerce')

    # Identify differences between planning and timetable
    differences = bus_planning.merge(
        timetable, on=['startlocatie', 'starttijd', 'eindlocatie', 'buslijn'], how='outer', indicator=True
    )

    issues = differences.query('_merge != "both"')

    if not issues.empty:
        return issues[['omloop nummer', 'startlocatie', 'activiteit', 'starttijd']]

    return pd.DataFrame(columns=['omloop nummer', 'startlocatie', 'activiteit', 'starttijd'])

def check_travel_time(bus_planning, distance_matrix):
    """
    Validates that travel times are within expected ranges.

    Args:
        bus_planning (DataFrame): Planned rides.
        distance_matrix (DataFrame): Expected travel time data.

    Returns:
        DataFrame: Discrepancies in travel times.
    """
    print("Initial columns:", bus_planning.columns)

    # Strip column names to avoid leading/trailing spaces
    bus_planning.columns = bus_planning.columns.str.strip()

    # Ensure required columns are present
    if 'starttijd' not in bus_planning.columns or 'eindtijd' not in bus_planning.columns:
        print("Missing columns:", bus_planning.columns)
        return pd.DataFrame()

    # Validate and convert time columns to datetime
    try:
        bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], format='%H:%M:%S')
        bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], format='%H:%M:%S')
    except Exception as e:
        print("Datetime conversion error:", e)
        return pd.DataFrame()

    print("After datetime conversion:")
    print(bus_planning[['starttijd', 'eindtijd']].info())

    # Calculate the time difference in minutes
    bus_planning['difference_in_minutes'] = (
        bus_planning['eindtijd'] - bus_planning['starttijd']
    ).dt.total_seconds() / 60

    # Merge planning data with the distance matrix
    merged_df = pd.merge(bus_planning, distance_matrix, on=['startlocatie', 'eindlocatie', 'buslijn'], how='inner')

    issues = []

    # Check if travel times fall within the expected range
    for _, row in merged_df.iterrows():
        if not (row['min reistijd in min'] <= row['difference_in_minutes'] <= row['max reistijd in min']):
            issues.append({
                'omloop nummer': row.get('omloop nummer', None),
                'startlocatie': row['startlocatie'],
                'eindlocatie': row['eindlocatie'],
                'reistijd': row['difference_in_minutes'],
                'starttijd': row['starttijd']
            })

    return pd.DataFrame(issues)

# VISUALISATION FUNCTION
def plot_schedule_from_excel(bus_planning):
    """Plot a Gantt chart for bus scheduling based on a DataFrame."""
    required_columns = ['starttijd', 'eindtijd', 'buslijn', 'omloop nummer', 'activiteit']
    
    # Check if all required columns are present
    if not all(col in bus_planning.columns for col in required_columns):
        st.error("One or more necessary columns are missing in bus planning.")
        return

    # Convert time columns to datetime format
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], errors='coerce')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], errors='coerce')

    # Remove rows with invalid datetime values
    bus_planning = bus_planning.dropna(subset=['starttijd', 'eindtijd'])

    # Calculate duration in hours, ensuring a minimum value for visibility
    bus_planning['duration'] = ((bus_planning['eindtijd'] - bus_planning['starttijd']).dt.total_seconds() / 3600).clip(lower=0.05)

    # Define color mapping for various activities and bus lines
    color_map = {
        '400.0': 'blue',
        '401.0': 'yellow',
        'materiaal rit': 'green',
        'idle': 'red',
        'opladen': 'orange'
    }
    bus_planning['buslijn'] = bus_planning['buslijn'].astype(str)

    # Determine the color for each row based on bus line or activity
    def determine_color(row):
        return color_map.get(row['buslijn'], color_map.get(row['activiteit'], 'gray'))

    bus_planning['color'] = bus_planning.apply(determine_color, axis=1)

    # Create a Gantt chart
    fig, ax = plt.subplots(figsize=(12, 6))
    omloopnummers = bus_planning['omloop nummer'].unique()
    omloop_indices = {omloop: i for i, omloop in enumerate(omloopnummers)}

    for omloop, omloop_index in omloop_indices.items():
        trips = bus_planning[bus_planning['omloop nummer'] == omloop]

        if trips.empty:
            # Add a placeholder bar for empty schedules
            ax.barh(omloop_index, 1, left=0, color='black', edgecolor='black')
            continue

        for _, trip in trips.iterrows():
            # Plot each trip as a horizontal bar
            ax.barh(
                omloop_index, 
                trip['duration'], 
                left=trip['starttijd'].hour + trip['starttijd'].minute / 60, 
                color=trip['color'], 
                edgecolor='black'
            )

    # Add labels and legend to the chart
    ax.set_yticks(list(omloop_indices.values()))
    ax.set_yticklabels(list(omloop_indices.keys()))
    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('Bus Number')
    ax.set_title('Gantt Chart for Bus Scheduling')

    # Define legend elements
    legend_elements = [
        Patch(facecolor=color_map['400.0'], edgecolor='black', label='Regular trip 400'),
        Patch(facecolor=color_map['401.0'], edgecolor='black', label='Regular trip 401'),
        Patch(facecolor=color_map['materiaal rit'], edgecolor='black', label='Deadhead trip'),
        Patch(facecolor=color_map['idle'], edgecolor='black', label='Idle'),
        Patch(facecolor=color_map['opladen'], edgecolor='black', label='Charging')
    ]
    ax.legend(handles=legend_elements, title='Legend')

    # Render the plot in Streamlit
    st.pyplot(fig)

def plot_activity_pie_chart(df):
    """
    Display a pie chart showing the distribution of activities in the total planning.
    """
    df['starttijd'] = pd.to_datetime(df['starttijd'], format='%H:%M:%S', errors='coerce')
    df['eindtijd'] = pd.to_datetime(df['eindtijd'], format='%H:%M:%S', errors='coerce')

    # Calculate the duration of each activity
    df['duur'] = (df['eindtijd'] - df['starttijd']).dt.total_seconds() / 3600

    # Group data by activity and calculate the total duration per activity
    stapel_data = df.groupby('activiteit')['duur'].sum().reset_index()

    # Ensure all expected activities are included
    activiteit_labels = ['opladen', 'idle']
    for label in activiteit_labels:
        if label not in stapel_data['activiteit'].values:
            stapel_data = stapel_data._append({'activiteit': label, 'duur': 0}, ignore_index=True)

    nieuwe_labels = ['Regular Trip', 'Idle', 'Deadhead Trip', 'Charging']

    # Create and display the pie chart
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(
        stapel_data['duur'], 
        labels=None, 
        autopct=lambda pct: f'{pct:.1f}%', 
        startangle=90, 
        colors=['blue', 'red', 'green', 'orange'], 
        textprops={'fontsize': 14, 'fontweight': 'bold'}
    )
    ax.legend(nieuwe_labels, loc="best")
    ax.set_title('Distribution of Activities in the Total Planning')
    st.pyplot(fig)

def plot_charging_heatmap(df):
    """
    Display a heatmap showing the 'Charging' activity by hour of the day.
    """
    df['starttijd'] = pd.to_datetime(df['starttijd'], format='%H:%M:%S', errors='coerce')
    df['uur'] = df['starttijd'].dt.hour

    # Filter data for 'Charging' activity
    opladen_df = df[df['activiteit'] == 'opladen']

    # Count occurrences of charging by hour
    heatmap_data = opladen_df['uur'].value_counts().reindex(range(24), fill_value=0)

    # Create and display the heatmap
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.heatmap(
        heatmap_data.values.reshape(1, -1), 
        cmap='YlGnBu', 
        annot=True, 
        cbar=True, 
        ax=ax, 
        xticklabels=[f"{hour}:00" for hour in range(24)], 
        yticklabels=["Charging"]
    )
    ax.set_title('Heatmap of Activity "Charging" per Hour')
    ax.set_xlabel('Hour of the Day')
    ax.set_ylabel('Activity')
    st.pyplot(fig)

def plot_activity_bar_chart(df):
    """
    Display a bar chart showing the total time spent on each activity.
    """
    df['starttijd'] = pd.to_datetime(df['starttijd'], format='%H:%M:%S', errors='coerce')
    df['eindtijd'] = pd.to_datetime(df['eindtijd'], format='%H:%M:%S', errors='coerce')

    # Calculate the duration of each activity
    df['duur'] = (df['eindtijd'] - df['starttijd']).dt.total_seconds() / 3600

    # Group data by activity and calculate the total duration per activity
    stapel_data = df.groupby('activiteit')['duur'].sum().reset_index()

    # Ensure all expected activities are included
    activiteit_labels = ['opladen', 'idle']
    for label in activiteit_labels:
        if label not in stapel_data['activiteit'].values:
            stapel_data = stapel_data._append({'activiteit': label, 'duur': 0}, ignore_index=True)

    # Create and display the bar chart
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(stapel_data['activiteit'], stapel_data['duur'], color=['blue', 'red', 'green', 'orange'])
    nieuwe_labels = ['Regular Trip', 'Idle', 'Deadhead Trip', 'Charging']
    ax.set_xticks(range(len(nieuwe_labels)))
    ax.set_xticklabels(nieuwe_labels, fontsize=12)
    ax.set_title('Total Time per Activity')
    ax.set_xlabel('Activity')
    ax.set_ylabel('Total Time (Hours)')
    st.pyplot(fig)

# KPI FUNCTIONS

def count_buses(bus_planning):
    """Count the number of unique 'omloop nummer' values in the bus planning data.

    Args:
        bus_planning (DataFrame): The data containing bus schedules.

    Returns:
        int: Number of unique 'omloop nummer' values.

    Raises:
        ValueError: If 'omloop nummer' column is missing in the data.
    """
    # Check if the required column exists in the data
    if 'omloop nummer' not in bus_planning.columns:
        raise ValueError("'omloop nummer' column not found in the data.")

    # Drop NaN values and count unique entries
    valid_omloop = bus_planning['omloop nummer'].dropna()
    return valid_omloop.nunique()

def calculate_deadhead_time(bus_planning):
    """Calculate the total time spent on deadhead trips in minutes.

    Args:
        bus_planning (DataFrame): The data containing bus schedules.

    Returns:
        float: Total deadhead time in minutes.

    Raises:
        ValueError: If required columns are missing in the data.
    """
    # Define required columns for the calculation
    required_columns = ['starttijd datum', 'eindtijd datum', 'activiteit']

    # Check if all required columns exist in the data
    if not all(col in bus_planning.columns for col in required_columns):
        raise ValueError("Required columns for deadhead time calculation are missing.")

    # Filter the data for deadhead trips ('materiaal rit' activity)
    deadhead_trips = bus_planning[bus_planning['activiteit'] == 'materiaal rit']

    # Convert start and end times to datetime format, handling errors
    deadhead_trips['starttijd datum'] = pd.to_datetime(deadhead_trips['starttijd datum'], errors='coerce')
    deadhead_trips['eindtijd datum'] = pd.to_datetime(deadhead_trips['eindtijd datum'], errors='coerce')

    # Calculate the duration of each deadhead trip in minutes
    deadhead_trips['duration_minutes'] = (deadhead_trips['eindtijd datum'] - deadhead_trips['starttijd datum']).dt.total_seconds() / 60

    # Sum up the total duration and round to the nearest minute
    return round(deadhead_trips['duration_minutes'].sum(), 0)

def calculate_energy_consumption(bus_planning, distance_matrix, consumption_per_km):
    """Calculate the total energy consumed for the bus planning.

    Args:
        bus_planning (DataFrame): The bus schedule with details of trips and activities.
        distance_matrix (DataFrame): Matrix with distances between locations.
        consumption_per_km (float): Energy consumption per kilometer in kWh.

    Returns:
        float: Total energy consumed in kWh.
    """
    # Merge the bus planning data with the distance matrix
    df = pd.merge(bus_planning, distance_matrix, on=['startlocatie', 'eindlocatie', 'buslijn'], how='left')

    # Calculate energy consumption for each trip in kWh
    df['consumption (kWh)'] = (df['afstand in meters'] / 1000) * max(consumption_per_km, 0.7)

    # Adjust energy consumption for idle activities to a minimal value
    df.loc[df['activiteit'] == 'idle', 'consumption (kWh)'] = 0.01

    # Calculate the total energy consumption and round to the nearest kWh
    total_energy_consumed = round(df['consumption (kWh)'].sum(), 0)

    return total_energy_consumed

# PAGE DEFINITIONS

def bus_checker_page(): 
    """Define the layout and functionality of the Bus Planning Checker page."""
    st.header("Bus Planning Checker")

    # Create tabs for different functionalities
    tab1, tab2, tab3 = st.tabs(['Data and Parameters', 'Validity Checks', 'Your Data'])

    with tab1:
        # Section for uploading files and setting parameters
        st.subheader('Data')
        col1, col2 = st.columns(2)
    
        with col1:
            # Upload the bus planning file
            uploaded_file = st.file_uploader("Upload Your **Bus Planning** Here", type="xlsx")
        with col2:
            # Upload the timetable file
            given_data = st.file_uploader("Upload Your **Timetable** Here", type="xlsx")
        
        # Parameter sliders
        st.subheader('Parameters')
        SOH =                   st.slider("**State Of Health** - %", 85, 95, 90)
        min_SOC =               st.slider("**Minimum State Of Charge** - %", 5, 25, 10)
        consumption_per_km =    st.slider("**Battery Consumption Per KM** - KwH", 0.7, 2.5, 1.6)

    with tab3:
        # Check if the required files are uploaded
        if not uploaded_file or not given_data:
            st.error("You need to upload your data in the 'Data and Parameters' tab.")
            return  # Stop execution if files are not uploaded
        
        if uploaded_file and given_data:
            with st.spinner('Your data is being processed...'): 
                try:
                    # Read the uploaded files into DataFrames
                    bus_planning = pd.read_excel(uploaded_file)
                    timetable = pd.read_excel(given_data, sheet_name='Dienstregeling')
                    distance_matrix = pd.read_excel(given_data, sheet_name="Afstandsmatrix")
                except Exception as e:
                    st.error(f"Error reading Excel files: {str(e)}")
                    return

                # Display the bus planning data
                st.write('**Your Bus Planning**')
                st.dataframe(bus_planning, hide_index=True)

                # Generate a Gantt chart for the bus planning
                st.write('**Gantt Chart Of Your Bus Planning**')
                plot_schedule_from_excel(bus_planning) 

                # Display activity visualizations
                st.write('**Activity Visualisations Of Your Bus Planning**')
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write("Distribution of activities")
                    plot_activity_pie_chart(bus_planning)

                with col2:
                    st.write("Distribution of charging")
                    plot_charging_heatmap(bus_planning)

                with col3:
                    st.write("Total time per activity")
                    plot_activity_bar_chart(bus_planning)
            
                # Check if any uploaded data is empty
                if bus_planning.empty or timetable.empty or distance_matrix.empty:
                    st.error("One or more DataFrames are empty. Please check the uploaded files.")
                    return

                # Instruction to expand graphs
                st.write('*Click on the graph to expand*')
                
    with tab2:
        # Display KPIs (Key Performance Indicators)
        st.subheader('KPIs')
        met_col1, met_col2, met_col3 = st.columns(3)

        try:
            # Calculate and display the total number of buses used
            buses_used = count_buses(bus_planning)  
            met_col1.metric('Total Buses Used', buses_used, delta=(buses_used - 20), delta_color="inverse")
        except Exception as e:
            # Handle and display errors related to bus counting
            st.error(f'Something went wrong displaying buses: {str(e)}')

        try:
            # Calculate and display total deadhead time in minutes
            deadhead_minutes = calculate_deadhead_time(bus_planning)  
            met_col2.metric('Total Deadhead Trips In Minutes', deadhead_minutes)
        except Exception as e:
            # Handle and display errors related to deadhead time calculation
            st.error(f'Something went wrong displaying deadhead time: {str(e)}')
        
        try: 
            # Calculate and display total energy consumption in kW
            energy_cons = calculate_energy_consumption(bus_planning, distance_matrix, consumption_per_km)
            met_col3.metric('Total Energy Consumed in kW', energy_cons)
        except Exception as e:
            # Handle and display errors related to energy consumption calculation
            st.error(f'Something went wrong displaying energy consumption: {str(e)}')
            
        # Add a visual divider for better UI separation
        st.divider()
        
        # Check Battery Status
        st.subheader('Battery Status')
        try: 
            # Check for battery issues based on State of Health (SOH) and minimum State of Charge (SOC)
            battery_problems = check_battery_status(bus_planning, distance_matrix, SOH, min_SOC, consumption_per_km)
            if battery_problems.empty:
                # Display a message if no battery problems are found
                st.write('No problems found!')
            else:
                # Highlight and display rows with battery issues
                st.markdown(':red[Battery dips below minimum State Of Charge]')
                with st.expander('Click to see the affected rows'):
                    st.dataframe(battery_problems)       
        except Exception as e:
            # Handle and display errors related to battery status checks
            st.error(f'Something went wrong checking battery: {str(e)}')
        
        # Check Route Continuity
        st.subheader('Route Continuity')
        try:
            # Check for continuity issues where start and end locations do not align
            continuity_problems = check_route_continuity(bus_planning)
            if continuity_problems.empty:
                # Display a message if no continuity problems are found
                st.write('No problems found!')
            else:
                # Highlight and display rows with continuity issues
                st.markdown(':red[Start and end location do not line up]')
                with st.expander('Click to see the affected rows'):
                    st.dataframe(continuity_problems)
        except Exception as e:
            # Handle and display errors related to route continuity checks
            st.error(f'Something went wrong checking route continuity: {str(e)}')

        # Check Driven Rides
        try:
            # Update the bus planning data with information about driven rides
            bus_planning = driven_rides(bus_planning)
        except Exception as e:
            # Handle and display errors related to driven ride checks
            st.error(f'Something went wrong checking driven rides: {str(e)}')

        # Check if Every Necessary Trip is Covered
        st.subheader('Trip Coverage')
        try:
            # Verify if all trips in the timetable are covered in the bus planning
            ride_coverage = every_ride_covered(bus_planning, timetable)
            if ride_coverage.empty:
                # Display a message if all trips are covered
                st.write('No problems found!')
            else:
                # Highlight and display rows with uncovered trips
                st.markdown(':red[Some trips included in timetable are not present in bus planning, or vice versa]')
                with st.expander('Click to see the affected rows'):
                    st.dataframe(ride_coverage)             
        except Exception as e:
            # Handle and display errors related to trip coverage checks
            st.error(f'Something went wrong checking if each trip is covered: {str(e)}')

        # Check Travel Time
        st.subheader('Travel Time')
        try:
            # Check for travel time issues based on the distance matrix
            travel_time = check_travel_time(bus_planning, distance_matrix)
            if travel_time.empty:
                # Display a message if no travel time issues are found
                st.write('No problems found!')
            else:
                # Highlight and display rows with travel time issues
                st.markdown(':red[Travel time outside of bound as specified in distance matrix]')
                with st.expander('Click to see the affected rows'):
                    st.dataframe(travel_time)  
        except Exception as e:
            # Handle and display errors related to travel time checks
            st.error(f'Something went wrong checking the travel time: {str(e)}')

                       
def how_it_works_page():
    st.header("How It Works")

    st.write("**The tool checks the following conditions:**")

    st.markdown("""
    1. **Battery Status**: the tool checks that the battery level of the bus does not drop below the minimum of the State of Charge, which is **10%** by default. 
    The system accounts for both driving and idle time consumption and charging times at two rates: a higher rate for charging up to **90%** and a slower rate beyond that. 

    2. **Route Continuity**: the tool checks that the end location of each route aligns with the starting location of the following route. 
    
    3. **Trip Coverage**: the tool ensures that every trip listed in the **timetable** is matched in the **bus planning**, and vice versa. 

    4. **Travel Time**: the tool confirms that the travel time for each route falls within the predefined range included in the distance matrix. 

    5. **Data Consistency**: the tool verifies that all critical columns are present in your data. 

    """)
    
def help_page():
    st.header("Help")

    tab1, tab2 = st.tabs(['How To Use', 'Troubleshooting'])

    with tab1:
        st.subheader("**Need assistance?**")
        st.write("**This is how to use the app**")

        st.markdown("""1. Go to the navigation panel and select ‘Bus Planning Checker’.""")
        st.image('nav_panel.png', width=200)

        st.markdown("""2. You should be presented with the following page. Here you can upload your bus planning and your timetable.""")
        st.image('bus_planning_page.png', width=600)

        st.markdown("""
        ---
        Note:
        - Do not refresh the page after uploading files, this will clear all data
        - Follow the correct upload sequence  to ensure accurate results
        - Both files must be .xlsx files
        ---
        3. You can view the validity of your planning in the **Validity Checks** tab. You will find:
            - KPIs to quickly assess the quality of your planning and compare different plans
            - The validity of your planning against various criteria""")
        
        st.image('validity_checks.png', width=400)
        st.write('Use the dropdown menu to identify and review affected rows if issues are found.')
        st.image('affected_rows.png', width=400)
        
        st.markdown("""
        4. You can view the validity of your planning in the **Your Data** tab. You will find:
            - An Excel sheet of the bus planning
            - A Gantt chart of your planning
            - Three graphs showing the activity distribution of your planning""")
        
        st.image('your_data.png', width=400)

    with tab2:
        st.subheader("**Troubleshooting**")
        st.markdown("""
        **Things to do if you are having trouble uploading your files**
        - Ensure that the files are .xlsx files. Any other file format will not work
        - Verify that you uploaded the files in the correct order. The bus planning on the left, the timetable on the right
        - Verify that the files are complete and contain all required fields. Missing data or headers may result in errors during analysis
        - If the issue persists, try refreshing the page and re-uploading the files""")


# PAGE SELECTOR
if page == 'Bus Planning Checker':
    bus_checker_page()
elif page == 'How It Works':
    how_it_works_page()
elif page == 'Help':
    help_page()