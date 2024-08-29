import streamlit as st
# Check if the user is authenticated
if st.session_state.get("authentication_status"):
    left_co, cent_co,last_co = st.columns(3)
    with cent_co:
        st.image('img/image_banner.png')
        st.write("\n")
    st.markdown(
        """
        <style>
        button[title="View fullscreen"] {
            display: none;
        }
        </style>
        | Scripts | Details |
        |------||------|
        |<a href="Ad_Settings_Decrypter" target = "_self">Ad Settings Decrypter</a> | Decrypt <acast\:settings> in an RSS feed. |
        |<a href="Backup_Importer" target = "_self">Backup Importer</a> | Import all episodes from an RSS feed to a specified show. |
        |<a href="Embed_Player_Generator" target = "_self">Embed Player Generator</a> | Export CSV with episode title, published date, and embed player code. |
        |<a href="RSS_Finder" target = "_self">RSS Finder</a> | Search Apple Podcasts database to find the RSS feed of a show.|
        |<a href="Timestamp_Exporter" target = "_self">Timestamp Exporter</a> | Export CSV with episode title, GUID, published date, and ad marker timestamps. |
        |<a href="Automatic_Midroll_Insertion" target = "_self">Automatic Midroll Insertion</a> | Automatically insert midroll markers in silence points across a show's back catalogue. |
        """, unsafe_allow_html=True
    )
else:
    st.warning("You must log in to access this page.")