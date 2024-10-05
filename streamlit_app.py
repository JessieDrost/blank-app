import streamlit as st

st.logo("Logo_transdev.png", size='large')

st.sidebar.write('How it works')
st.sidebar.button('click here')

st.title("🚌 Bus Planning Checker")
st.write(
    "Instantly validate your circulation planning for compliance!"
)
