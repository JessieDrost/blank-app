import streamlit as st

st.logo("Logo_transdev_klein.png", size='large', icon_image="tra_logo_rgb_LR.jpg")

# Add links to the sidebar
pg = st.navigation([st.Page("bus_planning_checker.py"), st.Page("How_it_works.py"), st.Page("help.py")])
pg.run()

st.title("Bus Planning Checker")
st.write(
    "Instantly validate your circulation planning for compliance!"
)
