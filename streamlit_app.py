import streamlit as st

# Display the logo
st.logo("tra_logo_rgb_HR.jpg", size="large", icon_image="Logo_transdev_klein.png")

# Define pages
bus_checker = st.Page("bus_check.py", title="Bus Planning Checker")
how_work = st.Page("how_it_works.py", title="How It Works")
help_page = st.Page("help.py", title="Help")

# Define the navigation menu with the pages
pg = st.navigation([bus_checker, how_work, help_page])

# Run the selected page
pg.run()