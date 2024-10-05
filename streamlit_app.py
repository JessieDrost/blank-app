import streamlit as st

st.logo("Logo_transdev_klein.png", size='large', icon_image="Logo_transdev_groot.png")

# Add a title to the sidebar
st.sidebar.title("Navigation")

# Add links to the sidebar
st.sidebar.markdown("[Bus Planning Checker]")
st.sidebar.markdown("[How it Works]")
st.sidebar.markdown("[Help]")st.sidebar.markdown("Hi!")

st.title("🚌 Bus Planning Checker")
st.write(
    "Instantly validate your circulation planning for compliance!"
)
