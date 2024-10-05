import streamlit as st

st.logo("Logo_transdev_klein.png", size='large', icon_image="tra_logo_rgb_LR.jpg")

# Add links to the sidebar
bus_planning_checker = st.Page(
    "bus_check.py", title="Bus Planning Checker", icon=":bus:")

how_it_works = st.Page(
    "how_it_works.py", title="How it Works", icon=":book:")

help_page = st.Page(
    "help.py", title="How To Use", icon=":question:")
pg = st.navigation([st.Page("Bus_Planning_Checker.py"), st.Page("How_it_Works.py"), st.Page("Help.py")])
pg.run()

st.title("Bus Planning Checker")
st.write(
    "Instantly validate your circulation planning for compliance!"
)
