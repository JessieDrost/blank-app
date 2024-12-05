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