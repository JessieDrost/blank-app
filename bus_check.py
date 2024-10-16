import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
from io import StringIO
from datetime import datetime, timedelta
import numpy as np

# Make streamlit pretty
st.title("Bus Planning Checker")
st.write(
    "Instantly validate your circulation planning for compliance!"
)
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

def load_data(file_name):
    distance_matrix = pd.read_excel(file_name, sheet_name="Afstandsmatrix")
    time_table = pd.read_excel(file_name, sheet_name="Dienstregeling")
    return distance_matrix, time_table

def set_parameters():
    max_capacity = 300
    SOH = [85, 95]
    charging_speed_90 = 450 / 60
    charging_time_10 = 60 / 60
    actual_capacity_90 = max_capacity * 0.9
    actual_capacity = actual_capacity_90
    daytime_limit = actual_capacity_90 * 0.9
    consumption_per_km = (0.7 + 2.5) / 2
    min_idle_time = 15
    return max_capacity, actual_capacity, daytime_limit, consumption_per_km, min_idle_time

def prepare_data(distance_matrix, time_table):
    distance_matrix["afstand in km"] = distance_matrix["afstand in meters"] / 1000
    distance_matrix["min reistijd in uur"] = distance_matrix["min reistijd in min"] / 60
    distance_matrix["max reistijd in uur"] = distance_matrix["max reistijd in min"] / 60
    distance_matrix["mean reistijd in uur"] = (distance_matrix["min reistijd in uur"] + distance_matrix["max reistijd in uur"]) / 2
    distance_matrix["buslijn"] = distance_matrix["buslijn"].fillna("deadhead trip")
    distance_matrix["max_energy"] = distance_matrix["afstand in km"] * 2.5
    distance_matrix["min_energy"] = distance_matrix["afstand in km"] * 0.7
    
    time_table['Row_Number'] = time_table.index + 1
    time_table['vertrektijd_dt'] = time_table['vertrektijd'].apply(lambda x: datetime.strptime(x, '%H:%M'))
    time_table["vertrektijd"] = pd.to_datetime(time_table["vertrektijd"], format='%H:%M', errors='coerce')
    
    return distance_matrix, time_table

def calculate_end_time(row, distance_matrix):
    travel_time = distance_matrix[(distance_matrix['startlocatie'] == row['startlocatie']) & 
                                  (distance_matrix['eindlocatie'] == row['eindlocatie'])]["mean reistijd in uur"].values
    if len(travel_time) > 0:
        travel_time_in_min = travel_time[0] * 60
        end_time = row['vertrektijd_dt'] + timedelta(minutes=travel_time_in_min)
        return end_time
    else:
        return None

def apply_end_times(time_table, distance_matrix):
    time_table['eindtijd'] = time_table.apply(lambda row: calculate_end_time(row, distance_matrix), axis=1)
    return time_table

def simulate_battery(uploaded_file, actual_capacity, start_time, end_time, min_idle_time, errors):
    battery = actual_capacity * 0.9
    min_battery = actual_capacity * 0.1

    for i, row in uploaded_file.iterrows():
        start_time = datetime.strptime(row['starttijd'], '%H:%M:%S')
        end_time = datetime.strptime(row['eindtijd'], '%H:%M:%S')

        if row['activiteit'] in ['dienst rit', 'materiaal rit']:
            consumption = row['energieverbruik']
            battery -= consumption
            if battery < min_battery:
                errors.append(f"Warning: Battery of bus {row['omloop nummer']:.0f} too low at {row['starttijd']}.")
        elif row['activiteit'] == 'opladen':
            idle_start_time = datetime.strptime(row['starttijd'], '%H:%M:%S')
            idle_end_time = datetime.strptime(row['eindtijd'], '%H:%M:%S')
            idle_time = (idle_end_time - idle_start_time).total_seconds() / 60
            if idle_time >= min_idle_time:
                battery = charging(battery, actual_capacity, idle_start_time, start_time, end_time)
            else:
                errors.append(f"Warning: Charging time too short between {row['starttijd']} and {row['eindtijd']}, only {idle_time} minutes.")
    
    if battery < min_battery:
        errors.append(f"Warning: Battery too low after {row['starttijd']}.")
    
    return battery

def charging(battery, actual_capacity, current_time, start_times, end_times):
    min_battery = 0.10 * actual_capacity
    max_battery_day = 0.90 * actual_capacity
    max_battery_night = actual_capacity
    charging_per_min = 450 / 60

    start_time = next((tijd for line, locatie, tijd in start_times if current_time >= tijd.time()), None)
    end_time = next((tijd for line, locatie, tijd in end_times if current_time >= tijd.time()), None)

    if start_time is None or end_time is None:
        raise ValueError(f"Start/end time not found for current time: {current_time}")

    max_battery = max_battery_night if current_time < start_time.time() or current_time > end_time.time() else max_battery_day
    charged_energy = 15 * charging_per_min
    new_battery = battery + charged_energy if battery <= min_battery else battery
    return min(new_battery, max_battery)

def driven_rides(bus_planning): 
    """Displays which rides are driven by extracting valid bus lines from the planning.
    
    Parameters:
        bus_planning: DataFrame
            The full bus planning data.
            
    Returns:
        DataFrame: Cleaned DataFrame with only relevant columns and rows that have a bus line.
    """
    clean_bus_planning = bus_planning[['startlocatie', 'starttijd', 'eindlocatie', 'buslijn']]
    clean_bus_planning = clean_bus_planning.dropna(subset=['buslijn'])
    return clean_bus_planning


def every_ride_covered(bus_planning, time_table):
    """Checks if every ride in the timetable is covered in the bus planning.

    Parameters: 
        bus_planning : DataFrame
            DataFrame representing the rides that are actually driven.
        time_table : DataFrame
            DataFrame representing the scheduled rides.
            
    Returns:
        str or DataFrame: Error messages or success message.
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
        errors.append(f"Rows only contained in bus planning:\n {difference_bus_planning_to_time_table}")
    if not difference_time_table_to_bus_planning.empty:
        errors.append(f"Rows only contained in time table:\n {difference_time_table_to_bus_planning}")

    if difference_bus_planning_to_time_table.empty and difference_time_table_to_bus_planning.empty:
        return "Bus planning is equal to time table"


def plot_schedule(scheduled_orders):
    """Plots a Gantt chart of the scheduled orders.
    
    Parameters:
        scheduled_orders (dict): Contains details about scheduled orders, their start time, end time, machine used, and setup time.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    y_pos = 0
    
    color_map = {'400': 'blue', '401': 'yellow'}
    
    for machine, orders in scheduled_orders.items():
        y_pos += 1
        for order in orders:
            order_color = order['colour']
            processing_time = order['end_time'] - order['start_time'] - order['setup_time']
            setup_time = order['setup_time']
            start_time = order['start_time']

            color = color_map.get(order_color, 'black')
            ax.barh(y_pos, processing_time, left=start_time + setup_time, color=color, edgecolor='black')
            ax.text(start_time + setup_time + processing_time / 2, y_pos, f"Order {order['order']}", 
                    ha='center', va='center', color='black', rotation=90)

            if setup_time > 0:
                ax.barh(y_pos, setup_time, left=start_time, color='gray', edgecolor='black', hatch='//')
    
    ax.set_yticks(range(1, len(scheduled_orders) + 1))
    ax.set_yticklabels([f"Machine {m}" for m in scheduled_orders.keys()])
    ax.set_xlabel('Time')
    ax.set_ylabel('Machines')
    ax.set_title('Gantt Chart for Paint Shop Scheduling')
    plt.show()


def check_travel_time(bus_planning, distance_matrix):
    """Validates if travel times are within acceptable ranges defined in the distance matrix.
    
    Parameters:
        bus_planning : DataFrame
            Contains 'starttijd', 'eindtijd', 'startlocatie', 'eindlocatie', 'buslijn'.
        distance_matrix : DataFrame
            Contains 'startlocatie', 'eindlocatie', 'min reistijd in min', 'max reistijd in min', 'buslijn'.
    
    Returns:
        str: Error messages for rows that do not fall within acceptable time limits.
    """
    bus_planning['starttijd'] = pd.to_datetime(bus_planning['starttijd'], format='%H:%M:%S', errors='coerce')
    bus_planning['eindtijd'] = pd.to_datetime(bus_planning['eindtijd'], format='%H:%M:%S', errors='coerce')
    bus_planning['verschil_in_minuten'] = (bus_planning['eindtijd'] - bus_planning['starttijd']).dt.total_seconds() / 60

    merged_df = pd.merge(bus_planning, distance_matrix, on=['startlocatie', 'eindlocatie', 'buslijn'], how='inner')

    for index, row in merged_df.iterrows():
        if not (row['min reistijd in min'] <= row['verschil_in_minuten'] <= row['max reistijd in min']):
            errors.append(
                f"Row {index}: The difference in minutes ({row['verschil_in_minuten']:.0f}) is not within {row['min reistijd in min']} - {row['max reistijd in min']}."
            )


def remove_startingtime_endtime_equal(bus_planning): 
    """Removes rows where start time and end time are the same.
    
    Parameters:
        bus_planning: DataFrame
    
    Returns:
        DataFrame: Cleaned DataFrame with rows having equal start and end times removed.
    """
    clean_bus_planning = bus_planning[bus_planning['starttijd'] != bus_planning['eindtijd']]
    return clean_bus_planning

def main():
    errors = []
    
    # Load the datasets
    uploaded_file = load_uploaded_file()
    time_table = load_time_table()
    distance_matrix = load_distance_matrix()
    scheduled_orders = load_scheduled_orders()

    # Step 1: Clean and validate data
    try:
        uploaded_file = driven_rides(uploaded_file)
    except Exception as e:
        errors.append(f"Error processing driven rides: {str(e)}")
    
    try:
        every_ride_covered(uploaded_file, time_table)
    except Exception as e:
        errors.append(f"Error checking ride coverage: {str(e)}")

    try:
        check_travel_time(uploaded_file, distance_matrix)
    except Exception as e:
        errors.append(f"Error checking travel times: {str(e)}")

    try:
        uploaded_file = remove_startingtime_endtime_equal(uploaded_file)
    except Exception as e:
        errors.append(f"Error removing equal start and end times: {str(e)}")
    
    # Step 2: Plot the schedule (if needed)
    try:
        plot_schedule(scheduled_orders)
    except Exception as e:
        errors.append(f"Error plotting the schedule: {str(e)}")
    
    # Return errors
    return errors

if __name__ == "__main__":
    errors = main()
    if errors:
        print("Errors found during execution:")
        for error in errors:
            print(error)
    else:
        print("All steps completed successfully.")
