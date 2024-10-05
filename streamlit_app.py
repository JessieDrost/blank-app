import streamlit as st

# Display the logo
st.logo("Logo_transdev_klein.png", size="large")

# Define pages
bus_checker = st.Page("bus_check.py", title=":bus: Bus Planning Checker")
how_work = st.Page("how_it_works.py", title=":book: How It Works")
help_page = st.Page("help.py", title=":question: Help")

# Define the navigation menu with the pages
pg = st.navigation([bus_checker, how_work, help_page])

# Run the selected page
pg.run()