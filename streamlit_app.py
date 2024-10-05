import streamlit as st

st.logo("Logo_transdev_klein.png", size='large', icon_image="tra_logo_rgb_LR.jpg")

# Add a title to the sidebar
st.sidebar.title("Navigation")

# Add links to the sidebar
st.sidebar.markdown("Bus Planning Checker")
st.sidebar.markdown("How it Works")
st.sidebar.markdown("Help")

st.title("Bus Planning Checker")
st.write(
    "Instantly validate your circulation planning for compliance!"
)
pg = st.navigation([st.Page("bus_planning_checker.py"), st.Page("How_it_works.py"), st.Page("help.py")])
pg.run()