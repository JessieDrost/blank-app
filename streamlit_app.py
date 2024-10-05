import streamlit as st

st.logo("Logo_transdev_klein.png", size="large", icon_image="tra_logo_rgb_LR.jpg")


st.title("Bus Planning Checker")
st.write(
    "Instantly validate your circulation planning for compliance!"
)
bus_checker = st.Page("bus_check.py", title="Bus Planning Checker")
how_work = st.Page("how_it_works.py", title="How It Works")
help = st.Page("help.py", title="How To Use")

pg = st.navigation(bus_checker, how_work, help)
pg.run()