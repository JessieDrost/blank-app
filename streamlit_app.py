import streamlit as st

st.logo("Logo_transdev_klein.png", size='large', icon_image="tra_logo_rgb_LR.jpg")

st.markdown(
    """
    <style>
    .reportview-container {
        background: url("https://brandguide.transdev.nl/files/220504-transdev-vdl-citea-huizen-0022-bewerkt-1.jpg")
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Add a title to the sidebar
st.sidebar.title("Navigation")

# Add links to the sidebar
st.sidebar.markdown(":bus: Bus Planning Checker")
st.sidebar.markdown(":book: How it Works")
st.sidebar.markdown(":question: Help")

st.title("Bus Planning Checker")
st.write(
    "Instantly validate your circulation planning for compliance!"
)
