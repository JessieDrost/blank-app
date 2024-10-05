import streamlit as st

st.logo("Logo_transdev_klein.png", size='large', icon_image="tra_logo_rgb_LR.jpg")

# Add links to the sidebar
pg = st.navigation([st.Page("Bus_Planning_Checker.py"), st.Page("How_it_Works.py"), st.Page("Help.py")])
pg.run()

st.title("Bus Planning Checker")
st.write(
    "Instantly validate your circulation planning for compliance!"
)
