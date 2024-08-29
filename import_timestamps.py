import streamlit as st

# Check if the user is authenticated
if st.session_state.get("authentication_status"):
    st.title('Import Timestamps')
    st.write('Coming soon!')
    # Add your timestamp exporter functionality here
else:
    st.warning("You must log in to access this page.")
    st.markdown("[Go to Login](../hub.py)")
