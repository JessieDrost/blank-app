import streamlit as st

st.logo("Logo_transdev.png", size='large')

st.logo("Logo_transdev_klein.png", size='large', icon_image="Logo_transdev_groot.png")
st.sidebar.markdown("Hi!")

st.title("🚌 Bus Planning Checker")
st.write(
    "Instantly validate your circulation planning for compliance!"
)
