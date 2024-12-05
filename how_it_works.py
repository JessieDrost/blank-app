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