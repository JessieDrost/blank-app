import streamlit as st

st.image("tra_logo_rgb_HR.png", width=400)

pages = [
    st.Page("bus_checker.py", title="🚍 Bus Planning Checker"),
    st.Page("how_it_works.py", title="📖 How It Works"),
    st.Page("help.py", title="❓ Help")
]

page = st.navigation(pages)
page.run()