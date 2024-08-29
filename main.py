import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# 1. Set the page configuration first
st.set_page_config(
    page_title="Script Hub",
    page_icon=":material/edit:",
)

st.logo('img/text.png')
# 2. Load configuration from the YAML file
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# 3. Initialize the authenticator without preauthorization
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

st.markdown(
        """
        <style>
        button[title="View fullscreen"] {
            display: none;
        }
        </style>
        """, unsafe_allow_html=True
    )# 4. Authenticate the user using keyword arguments
try:
    name, authentication_status, username = authenticator.login()
    # Store the authentication status in session state
    st.session_state['authentication_status'] = authentication_status
    st.query_params = {"rerun": "false"}  # Force rerun to update UI based on new authentication status
except stauth.LoginError as e:
    st.error(e)

# 5. Handle authentication status
if st.session_state.get("authentication_status") is None:
    st.write('')  # Add spacing

elif st.session_state['authentication_status']:
    st.query_params = {"page": "hub.py"}

    home = st.Page("hub.py", title="Home")
    timestamp_export = st.Page("export_timestamps.py", title="Export Timestamps")
    mid2_autoplacer = st.Page("mid2_autoplacer.py", title="Mid2 Autoplacer")
    import_timestamps = st.Page("import_timestamps.py", title="Import Timestamps")
    rss_finder = st.Page("rss_finder.py", title="RSS Finder")
    embed_generator = st.Page("embed_generator.py", title="Embed Player Generator") 

    pg = st.navigation([home, timestamp_export, mid2_autoplacer, import_timestamps, rss_finder, embed_generator])
    pg = st.navigation(
        {
            "": [home],
            "Timestamps": [import_timestamps, timestamp_export],
            "Automatic Midroll Placement": [mid2_autoplacer],    
            "Tools": [rss_finder, embed_generator],
        }
    )
    pg.run()
elif st.session_state['authentication_status'] is False:
    st.error("Username/password is incorrect")