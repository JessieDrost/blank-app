import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# STREAMLIT CONFIGURATION
st.logo("tra_logo_rgb_HR.png", size='large')
page = 'Bus Planning Checker'  # Default page before any button is clicked

# SIDEBAR NAVIGATION
with st.sidebar:
    st.subheader('Navigation')
    
    if st.button("Bus Planning Checker", icon="🚍", use_container_width=True):
        page = 'Bus Planning Checker'
    if st.button('How It Works', icon="📖", use_container_width=True):
        page = 'How It Works'
    if st.button('Help', icon="❓", use_container_width=True):
        page = 'Help'

# FUNCTIONS
def check_battery_status(bus_planning, distance_matrix, SOH, min_SOC, consumption_per_km):
    """
    Validates battery status throughout the bus schedule.
    Args:
        bus_planning (DataFrame): The bus schedule with 'starttijd', 'eindtijd', and other columns.
        distance_matrix (DataFrame): Distances between locations.
        SOH (float): State of Health of the battery as a percentage.
        min_SOC (float): Minimum state of charge required as a percentage.
        consumption_per_km (float): Energy consumption per kilometer in kWh.
    Returns:
        DataFrame: Rows from the schedule where battery status issues occur.
    """
    max_capacity = 300 * (SOH / 100)
    min_battery = max_capacity * (min_SOC / 100)

    # Process times
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], format='%H:%M')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], format='%H:%M')

    # Merge with distance matrix
    df = pd.merge(bus_planning, distance_matrix, on=['startlocatie', 'eindlocatie', 'buslijn'], how='left')

    # Calculate energy consumption with a minimum value
    df['consumption (kWh)'] = (df['afstand in meters'] / 1000) * max(consumption_per_km, 0.7)

    # Idle consumption
    df.loc[df['activiteit'] == 'idle', 'consumption (kWh)'] = 0.01

    # Charging speeds
    charging_speed_90 = 450 / 60
    charging_speed_10 = 60 / 60

    battery_level = max_capacity
    previous_loop_number = None

    issues = []

    for i, row in df.iterrows():
        next_start_time = bus_planning['starttijd'].iloc[i + 1] if i + 1 < len(bus_planning) else None

        # Reset battery for a new loop
        if row['omloop nummer'] != previous_loop_number:
            battery_level = max_capacity

        # Charging
        if row['activiteit'] == 'opladen':
            charging_duration = (row['eindtijd'] - row['starttijd']).total_seconds() / 60
            charge_power = (charging_speed_90 if battery_level <= (SOH * 0.9) else charging_speed_10) * charging_duration
            battery_level = min(battery_level + charge_power, max_capacity)
        else:
            battery_level -= row['consumption (kWh)']

        battery_level = max(battery_level, 0)  # Ensure battery level is not negative

        if battery_level < min_battery:
            issues.append(row)

        previous_loop_number = row['omloop nummer']

    if not issues:
        return pd.DataFrame()  # Return empty DataFrame if no issues

    failed_df = pd.DataFrame(issues)
    required_columns = ['omloop nummer', 'starttijd', 'consumption (kWh)']
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

    if bus_planning is None:
        st.error("The 'bus_planning' DataFrame is None.")
        return pd.DataFrame()

    required_columns = {'omloop nummer', 'startlocatie', 'eindlocatie', 'starttijd'}
    if not required_columns.issubset(bus_planning.columns):
        missing_columns = required_columns - set(bus_planning.columns)
        st.error(f"Missing columns in 'bus_planning': {missing_columns}")
        return pd.DataFrame()

    bus_planning = bus_planning.sort_values(by=['omloop nummer', 'starttijd']).reset_index(drop=True)

    for i in range(len(bus_planning) - 1):
        current_row = bus_planning.iloc[i]
        next_row = bus_planning.iloc[i + 1]

        if current_row['omloop nummer'] == next_row['omloop nummer']:
            if current_row['eindlocatie'] != next_row['startlocatie']:
                issues.append({
                    'omloop nummer': current_row['omloop nummer'],
                    'current_end_location': current_row['eindlocatie'],
                    'next_start_location': next_row['startlocatie'],
                    'next_start_time': next_row['starttijd']
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


def every_ride_covered(bus_planning, time_table):
    """
    Checks if every ride in the bus planning is covered in the timetable.
    Args:
        bus_planning (DataFrame): Planned rides.
        time_table (DataFrame): Timetable rides.
    Returns:
        DataFrame: Discrepancies between planning and timetable.
    """
    if 'vertrektijd' in time_table.columns:
        time_table = time_table.rename(columns={'vertrektijd': 'starttijd'})

    if 'starttijd' not in bus_planning.columns or 'starttijd' not in time_table.columns:
        st.error("Missing 'starttijd' column in bus planning or timetable.")
        return pd.DataFrame()

    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], errors='coerce')
    time_table['starttijd'] = pd.to_datetime(time_table['starttijd'], errors='coerce')

    differences = bus_planning.merge(
        time_table, on=['startlocatie', 'starttijd', 'eindlocatie', 'buslijn'], how='outer', indicator=True
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
    if 'starttijd' not in bus_planning.columns or 'eindtijd' not in bus_planning.columns:
        st.error("Missing 'starttijd' or 'eindtijd' column in bus planning.")
        return pd.DataFrame()

    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], format='%H:%M:%S', errors='coerce')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], format='%H:%M:%S', errors='coerce')

    bus_planning['difference_in_minutes'] = (
        bus_planning['eindtijd'] - bus_planning['starttijd']
    ).dt.total_seconds() / 60

    merged_df = pd.merge(bus_planning, distance_matrix, on=['startlocatie', 'eindlocatie', 'buslijn'], how='inner')

    issues = []

    for _, row in merged_df.iterrows():
        if not (row['min reistijd in min'] <= row['difference_in_minutes'] <= row['max reistijd in min']):
            issues.append({
                'omloop nummer': row.get('omloop nummer', None),
                'startlocatie': row['startlocatie'],
                'eindlocatie': row['eindlocatie'],
                'reistijd': row['difference_in_minutes'],
                'starttijd': row['starttijd']
            })

    return pd.DataFrame(issues) if issues else pd.DataFrame(columns=['omloop nummer', 'startlocatie', 'eindlocatie', 'reistijd', 'starttijd'])

def plot_schedule_from_excel(bus_planning):
    """Plot a Gantt chart for bus scheduling based on a DataFrame."""
    required_columns = ['starttijd', 'eindtijd', 'buslijn', 'omloop nummer', 'activiteit']
    if not all(col in bus_planning.columns for col in required_columns):
        st.error("One or more necessary columns are missing in bus planning.")
        return

    # Convert time columns to datetime
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], errors='coerce')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], errors='coerce')

    # Drop rows with invalid datetime
    bus_planning = bus_planning.dropna(subset=['starttijd', 'eindtijd'])

    # Calculate duration in hours with a minimum value
    bus_planning['duration'] = ((bus_planning['eindtijd'] - bus_planning['starttijd']).dt.total_seconds() / 3600).clip(lower=0.05)

    # Map colors for different activities and bus lines
    color_map = {
        '400.0': 'blue',
        '401.0': 'yellow',
        'materiaal rit': 'green',
        'idle': 'red',
        'opladen': 'orange'
    }
    bus_planning['buslijn'] = bus_planning['buslijn'].astype(str)

    # Determine color per row
    def determine_color(row):
        return color_map.get(row['buslijn'], color_map.get(row['activiteit'], 'gray'))

    bus_planning['color'] = bus_planning.apply(determine_color, axis=1)

    # Plot Gantt chart
    fig, ax = plt.subplots(figsize=(12, 6))
    omloopnummers = bus_planning['omloop nummer'].unique()
    omloop_indices = {omloop: i for i, omloop in enumerate(omloopnummers)}

    for omloop, omloop_index in omloop_indices.items():
        trips = bus_planning[bus_planning['omloop nummer'] == omloop]

        if trips.empty:
            ax.barh(omloop_index, 1, left=0, color='black', edgecolor='black')  # Placeholder bar
            continue

        for _, trip in trips.iterrows():
            ax.barh(
                omloop_index, 
                trip['duration'], 
                left=trip['starttijd'].hour + trip['starttijd'].minute / 60, 
                color=trip['color'], 
                edgecolor='black'
            )

    # Add labels and legend
    ax.set_yticks(list(omloop_indices.values()))
    ax.set_yticklabels(list(omloop_indices.keys()))
    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('Bus Number')
    ax.set_title('Gantt Chart for Bus Scheduling')

    legend_elements = [
        Patch(facecolor=color_map['400.0'], edgecolor='black', label='Regular trip 400'),
        Patch(facecolor=color_map['401.0'], edgecolor='black', label='Regular trip 401'),
        Patch(facecolor=color_map['materiaal rit'], edgecolor='black', label='Deadhead trip'),
        Patch(facecolor=color_map['idle'], edgecolor='black', label='Idle'),
        Patch(facecolor=color_map['opladen'], edgecolor='black', label='Charging')
    ]
    ax.legend(handles=legend_elements, title='Legend')

    st.pyplot(fig)

def count_buses(bus_planning):
    """Count unique 'omloop nummer' values in bus planning."""
    if 'omloop nummer' not in bus_planning.columns:
        raise ValueError("'omloop nummer' column not found in the data.")
    
    valid_omloop = bus_planning['omloop nummer'].dropna()
    return valid_omloop.nunique()

def calculate_deadhead_time(bus_planning):
    """Calculate total time spent on deadhead trips in minutes."""
    required_columns = ['starttijd datum', 'eindtijd datum', 'activiteit']
    if not all(col in bus_planning.columns for col in required_columns):
        raise ValueError("Required columns for deadhead time calculation are missing.")
    
    deadhead_trips = bus_planning[bus_planning['activiteit'] == 'materiaal rit']
    deadhead_trips['starttijd datum'] = pd.to_datetime(deadhead_trips['starttijd datum'], errors='coerce')
    deadhead_trips['eindtijd datum'] = pd.to_datetime(deadhead_trips['eindtijd datum'], errors='coerce')

    deadhead_trips['duration_minutes'] = (deadhead_trips['eindtijd datum'] - deadhead_trips['starttijd datum']).dt.total_seconds() / 60
    return round(deadhead_trips['duration_minutes'].sum(), 0)

def calculate_energy_consumption(bus_planning, distance_matrix, consumption_per_km):
    """Calculate total energy consumption of buses in kWh."""
    required_columns = ['startlocatie', 'eindlocatie', 'buslijn', 'afstand in meters', 'activiteit']
    if not all(col in distance_matrix.columns for col in required_columns):
        raise ValueError("Required columns missing in distance matrix for energy calculation.")

    merged_df = pd.merge(bus_planning, distance_matrix, on=['startlocatie', 'eindlocatie', 'buslijn'], how='left')

    merged_df['consumptie (kWh)'] = (merged_df['afstand in meters'] / 1000) * max(consumption_per_km, 0.7)
    merged_df.loc[merged_df['activiteit'] == 'idle', 'consumptie (kWh)'] = 0.01

    return round(merged_df['consumptie (kWh)'].sum(), 0)
