import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

distance_matrix = pd.read_excel("Connexxion data - 2024-2025.xlsx", sheet_name="Afstandsmatrix")
time_table = pd.read_excel("Connexxion data - 2024-2025.xlsx", sheet_name="Dienstregeling")

st.title("Bus Planning Checker")
st.write(
    "Instantly validate your circulation planning for compliance!"
)

# File upload (CSV or Excel)
bus_planning = st.file_uploader("Drag and drop your circulation planning (CSV or Excel file)", type=["csv", "xlsx"])

# Parameters
max_capacity = 300  # Maximum capacity in kWh
SOH = [85, 95]  # State of Health
charging_speed_90 = 450 / 60  # kWh per minute for charging up to 90%
charging_time_10 = 60 / 60  # kWh per minute for charging from 90% to 100%
actual_capacity = max_capacity * 0.9
daytime_limit = actual_capacity * 0.9
consumption_per_km = (0.7 + 2.5) / 2  # kWh per km
min_idle_time = 15

# Data Preparation
distance_matrix["afstand in km"] = distance_matrix["afstand in meters"] / 1000
distance_matrix["min reistijd in uur"] = distance_matrix["min reistijd in min"] / 60
distance_matrix["max reistijd in uur"] = distance_matrix["max reistijd in min"] / 60
distance_matrix["buslijn"] = distance_matrix["buslijn"].fillna("deadhead trip")
distance_matrix["max_energy"] = distance_matrix["afstand in km"] * 2.5
distance_matrix["min_energy"] = distance_matrix["afstand in km"] * 0.7

time_table['vertrektijd_dt'] = time_table['vertrektijd'].apply(lambda x: datetime.strptime(x, '%H:%M'))

errors = []

def calculate_end_time(row):
    """ Adds the maximum travel time to the departure time to create a column with end time.
    Parameters: row
    Output: end time in HH:MM
    """
    travel_time = distance_matrix[(distance_matrix['startlocatie'] == row['startlocatie']) & 
                                  (distance_matrix['eindlocatie'] == row['eindlocatie'])]['min reistijd in uur'].values
    if len(travel_time) > 0:  # Check if travel_time is not empty
        travel_time_in_min = travel_time[0] * 60  # Convert travel time to minutes
        end_time = row['vertrektijd_dt'] + timedelta(minutes=travel_time_in_min)
        return end_time
    else:
        return None

time_table['eindtijd'] = time_table.apply(calculate_end_time, axis=1)

# Battery charging simulation
def charging(battery, actual_capacity, current_time, start_time, end_time):
    """Charge the battery based on the current time and time table."""
    min_battery = 0.10 * actual_capacity
    max_battery_day = 0.90 * actual_capacity
    max_battery_night = actual_capacity
    charging_per_min = charging_speed_90

    if current_time < start_time or current_time > end_time:
        max_battery = max_battery_night
    else:
        max_battery = max_battery_day

    charged_energy = min_idle_time * charging_per_min
    new_battery = battery + charged_energy if battery <= min_battery else battery
    return min(new_battery, max_battery)

def simulate_battery(uploaded_file, actual_capacity, start_time, end_time):
    """Simulate battery usage throughout the day based on the bus planning."""
    battery = actual_capacity * 0.9
    min_battery = actual_capacity * 0.1

    # Convert start and end times to datetime
    for i, row in uploaded_file.iterrows():
        start_time = datetime.strptime(row['starttijd'], '%H:%M:%S')
        end_time = datetime.strptime(row['eindtijd'], '%H:%M:%S')
        
        # Check if the trip is a regular or deadhead trip
        if row['activiteit'] in ['regular trip', 'deadhead trip']:
            consumption = row['energieverbruik']
            battery -= consumption
            if battery < min_battery:
                errors.append(f"Warning: Battery of bus {row['omloop nummer']:.0f} too low at {row['starttijd']}.")
        
        # Check if the bus has enough time to charge
        elif row['activiteit'] == 'opladen':
            idle_start_time = datetime.strptime(row['starttijd'], '%H:%M:%S')
            idle_end_time = datetime.strptime(row['eindtijd'], '%H:%M:%S')
            idle_time = (idle_end_time - idle_start_time).total_seconds() / 60
            if idle_time >= min_idle_time:
                battery = charging(battery, actual_capacity, idle_start_time, start_time, end_time)
            else:
                errors.append(f"Warning: Charging time too short between {row['starttijd']} and {row['eindtijd']}, only {idle_time} minutes.")

        # Ensure battery remains above 10%
        if battery < min_battery:
            errors.append(f"Warning: Battery too low after {row['starttijd']}.")
    
    return battery

# Function to check route continuity
def check_route_continuity(bus_planning):
    """
    Check if the endpoint of route n matches the start point of route n+1.
    Parameters:
        - bus_planning: DataFrame with route data.
    Output: Print messages if there are inconsistencies.
    """
    for i in range(len(bus_planning) - 1):
        current_end_location = bus_planning.iloc[i]['eindlocatie']
        next_start_location = bus_planning.iloc[i + 1]['startlocatie']
        if current_end_location != next_start_location:
            print(f"Warning: Route continuity issue between {bus_planning.iloc[i]['omloop nummer']:.0f} ending at {current_end_location} and next route starting at {next_start_location}.")
            return False
           
    return True

def battery_consumption(distance, current_time, start_time, end_time):
    """Calculate battery consumption based on distance and time."""
    battery_capacity = max_capacity * 0.9
    consumption = distance * np.mean(consumption_per_km)
    remaining_battery = battery_capacity - consumption
    
    return charging(remaining_battery, battery_capacity, current_time, start_time, end_time)

# Yvonnes code
def driven_rides(bus_planning):
    """ displays which rides are droven
    Parameters
        omloopplanning: DataFrame
        The full circulation planning data.
    output
        DataFrame
        A cleaned bus planning DataFrame containing only the relevant columns 
        and rows where a bus line is present.
    """
    clean_bus_planning = bus_planning[['startlocatie', 'starttijd', 'eindlocatie', 'buslijn']]
    clean_bus_planning = clean_bus_planning.dropna(subset=['buslijn'])
    return clean_bus_planning

def normalize_time_format(df, time_column):
    """Convert time to a uniform format, ignoring seconds.
    Parameters: 
        - df : DataFrame
            The DataFrame containing time data.
        - time_column: str
            Column with time as a string.
    Output: 
        DataFrame
        DataFrame with time in standardized form (%H:%M).
    """
    df[time_column] = pd.to_datetime(df[time_column]).dt.strftime('%H:%M')
    return df

def every_ride_covered(bus_planning, time_table):
    """Checks if every ride in the timetable is covered in bus planning.
    
    Parameters: 
        bus_planning : DataFrame
            The DataFrame representing the rides that are actually driven.
        time_table : DataFrame
            The DataFrame representing the rides that are supposed to be driven.
    
    Returns:
        DataFrame or str
            If there are differences, returns a DataFrame with the differences.
            If all rides are covered, returns a success message.
    """
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
        print("Rows only contained in bus planning:\n", difference_bus_planning_to_time_table)
    if not difference_time_table_to_bus_planning.empty:
        print("Rows only contained in time table:\n", difference_time_table_to_bus_planning)

    if difference_bus_planning_to_time_table.empty and difference_time_table_to_bus_planning.empty:
        return "Bus planning is equal to time table"
       
uploaded_file = driven_rides(bus_planning)
uploaded_file = normalize_time_format(uploaded_file, "starttijd")

result = every_ride_covered(uploaded_file, time_table)

print(result)

def check_travel_time(bus_planning, distance_matrix):
    """
    Check if the time difference between the start time and end time in bus planning
    falls within the minimum and maximum travel time in distance_matrix,
    while start location, end location, and bus line are the same.
    
    Parameters:
    bus_planning : DataFrame
        A DataFrame with columns 'starttijd', 'eindtijd', 'startlocatie', 'eindlocatie', 'buslijn'.
    distance_matrix : DataFrame
        A DataFrame with columns 'startlocatie', 'eindlocatie', 'minimale_reistijd', 'maximale_reistijd', 'buslijn'.
    
    Returns:
    Messages for rows that do not fall within the travel time.
    """
    # Ensure start time and end time are datetime
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], format='%H:%M:%S', errors='coerce')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], format='%H:%M:%S', errors='coerce')

    # Calculate the difference in minutes
    bus_planning['verschil_in_minuten'] = (bus_planning['eindtijd'] - bus_planning['starttijd']).dt.total_seconds() / 60

    # Merge both datasets on 'startlocatie', 'eindlocatie' and 'buslijn'
    merged_df = pd.merge(
        bus_planning,
        distance_matrix,
        on=['startlocatie', 'eindlocatie', 'buslijn'],
        how='inner'  # Keep only common rows
    )

    # Check if the difference is within the minimum and maximum travel time
    for index, row in merged_df.iterrows():
        if not (row['min reistijd in min'] <= row['verschil_in_minuten'] <= row['max reistijd in min']):
            errors.append(f"Row {index}: The difference in minutes ({row['verschil_in_minuten']:.0f}) is not between {row['max reistijd in min']} and {row['min reistijd in min']} for bus route {row['buslijn']} from {row['startlocatie']} to {row['eindlocatie']}.")
        
# Example call with bus planning 2 and distance matrix
bus_planning_2 = pd.read_excel('omloopplanning.xlsx')  # Ensure this exists

# Call the function
check_travel_time(bus_planning_2, distance_matrix)

def remove_startingtime_endtime_equal(bus_planning): 
    """ If the starting time and end time are equal, the row is removed.
    Parameters: 
        bus_planning: DataFrame
            Whole bus planning.
    Output: DataFrame
        Clean DataFrame.
    """
    clean_bus_planning = bus_planning[bus_planning['starttijd'] != bus_planning['eindtijd']]
    return clean_bus_planning

new_planning = remove_startingtime_endtime_equal(bus_planning)

# Battery charging simulation
def charging(battery, actual_capacity, current_time, start_time, end_time):
    """Charge the battery based on the current time and bus schedule."""
    min_battery = 0.10 * actual_capacity
    max_battery_day = 0.90 * actual_capacity
    max_battery_night = actual_capacity
    charging_per_min = charging_speed_90

    if current_time < start_time or current_time > end_time:
        max_battery = max_battery_night
    else:
        max_battery = max_battery_day

    charged_energy = min_idle_time * charging_per_min
    new_battery = battery + charged_energy if battery <= min_battery else battery
    return min(new_battery, max_battery)

# Function to calculate battery status
def simulate_battery(bus_planning, actual_capacity, start_time, end_time):
    """
    Simulate the battery status during the trip schedule.
    Parameters:
        - bus_planning: DataFrame with the trip schedule.
        - actual_capacity: Battery capacity of the bus.
        - start_time: First departure time of the regular trip.
        - end_time: Last end time of the regular trip.
    Output: Battery percentage after the simulation.
    """
    battery = actual_capacity * 0.9  # Start with 90% battery
    min_battery = actual_capacity * 0.1  # Minimum battery percentage
    max_battery_day = actual_capacity * 0.9  # Maximum 90% during the day
    max_battery_night = actual_capacity  # Maximum 100% at night
    min_charging_time = 15  # Minimum 15 minutes of charging

    for i, row in bus_planning.iterrows():
        # Convert start and end times to datetime
        start_time = datetime.strptime(row['starttijd'], '%H:%M:%S')
        end_time = datetime.strptime(row['eindtijd'], '%H:%M:%S')

        # Check if the trip is a regular trip or deadhead trip
        if row['activiteit'] in ['dienst rit', 'materiaal rit']:
            consumption = row['energieverbruik']
            battery -= consumption

            # Check if battery status has dropped below 10%
            if battery < min_battery:
                print(f"Warning: Battery too low after trip {row['buslijn']} at {row['starttijd']} from {row['startlocatie']} to {row['eindlocatie']}.")
                return battery  # Stop simulation if battery is too low

        # Check if the bus is idle and has enough time to charge
        if row['activiteit'] == 'opladen':
            idle_start_time = datetime.strptime(row['starttijd'], '%H:%M:%S')
            idle_end_time = datetime.strptime(row['eindtijd'], '%H:%M:%S')
            idle_time = (idle_end_time - idle_start_time).total_seconds() / 60  # Idle time in minutes

            # Check if the idle time is at least 15 minutes
            if idle_time >= min_charging_time:
                battery = charging(battery, actual_capacity, idle_start_time, start_time, end_time)
            else:
                print(f"Warning: Charging time too short from {row['startlocatie']} to {row['eindlocatie']} at {row['starttijd']} to {row['eindtijd']}, only {idle_time} minutes.")

        # Check battery status after each step
        if battery < min_battery:
            print(f"Warning: Battery too low after {row['starttijd']}.")
            break

    return battery

# Function to check route continuity
def check_route_continuity(bus_planning):
    """
    Check if the endpoint of trip n matches the start point of trip n+1.
    Parameters:
        - bus_planning: DataFrame with trip data.
    Output: Print messages if there are inconsistencies.
    """
    for i in range(len(bus_planning) - 1):
        current_end_location = bus_planning.iloc[i]['eindlocatie']
        next_start_location = bus_planning.iloc[i + 1]['startlocatie']
        if current_end_location != next_start_location:
            print(f"Warning: Route continuity issue between {bus_planning.iloc[i]['buslijn']} ending at {current_end_location} and next trip starting at {next_start_location}.")
            return False
    return True

