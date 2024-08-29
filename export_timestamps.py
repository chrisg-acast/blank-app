import feedparser
import requests
import json
import csv
from operator import itemgetter
import os
from dateutil import parser
import streamlit as st
import pandas as pd
import base64
from datetime import date
import streamlit_extras

hide_menu_style = """
        <style>
        #MainMenu {visibility: hidden;}
        </style>
        """
st.markdown(hide_menu_style, unsafe_allow_html=True)

st.header('⏳ Timestamp Exporter')
st.markdown("Generate a CSV file with episode title, GUID, publish date, and ad marker timestamps.")

# Check if the user is authenticated
if st.session_state.get("authentication_status"):
    with st.form(key='my_form'):
        st.markdown("Use API key associated with your Acast account and verify you have assigned yourself the admin role on the show via User Management.")
        showId = st.text_input("Acast Show ID:")
        key = st.text_input("API Key:", type="password")

        # Status placeholder
        processing_time_message = st.empty()
        processing_time_message.caption("Processing time may vary depending on episode count.")
        
        submit_button = st.form_submit_button(label='Generate')
        status_message = st.empty()

    if submit_button:
        processing_time_message.empty()
        status_message.write(f'Processing Show ID: {showId}')
        try:
            url = "https://open.acast.com/rest/shows/" + showId + "/episodes/"
            headers = {
                'x-api-key': key,
            }
            response = requests.request("GET", url, headers=headers)
            episodeData = response.json()

            # Parse RSS Feed early
            rssFeed = feedparser.parse("https://feeds.acast.com/public/shows/" + showId)
            showName = rssFeed["feed"]["title"]

            # Build a dictionary for RSS feed items
            rssItems = {item.title + str(parser.parse(item.published).date()): item.id for item in rssFeed['items']}

            rows = []
            for episodes in episodeData:
                episodeGUID = episodes.get('_id')
                episodeTitle = episodes.get('title')
                publishStatus = episodes.get('status')
                episodePublished = episodes.get('publishDate')
                duration = episodes.get('duration')
                adMarkers = {marker['placement']: str(marker['start']) for marker in episodes['markers'] if 'start' in marker}
                
                # Get ad markers from dictionary, or default to an empty string
                preroll = adMarkers.get('preroll', "")
                midroll = adMarkers.get('midroll', "")
                postroll = adMarkers.get('postroll', "")

                if postroll == '9999':
                    postroll = duration

                if publishStatus == 'published':
                    row = {}
                    row['Episode Title'] = episodeTitle
                    row['GUID'] = episodeGUID
                    row['Publish Date'] = episodePublished
                    row['Preroll'] = preroll
                    row['Midroll'] = midroll
                    row['Postroll'] = postroll
                    rows.append(row)

            rows.sort(key=itemgetter('Publish Date'), reverse=True)

            for row in rows:
                cmsTitle = row['Episode Title']
                cmsPublished = row['Publish Date']
                if not isinstance(cmsPublished, date):
                    cmsPublished = parser.parse(cmsPublished).date()
                cmsPublished_str = cmsPublished.strftime('%m/%d/%Y')  # Convert date to string in Month/Date/Year format

                rssGUID = rssItems.get(cmsTitle + cmsPublished_str)

                if rssGUID is not None:
                    row['GUID'] = rssGUID
                    row['Publish Date'] = cmsPublished_str  # Use the string format of the date
            

            df = pd.DataFrame(rows)

            filename = showName.replace(' ', '_') + '.csv'  # Replace spaces with underscores

            csv = df.to_csv(index=False)

            # Clear status message
            status_message.empty()

            st.write(f'{showName} ({len(episodeData)} episodes)')  # print show title and number of episodes
            st.write(df)
            st.download_button(label="Download CSV", data=csv.encode(), file_name=filename, mime='text/csv')
        except requests.exceptions.HTTPError as errh:
            st.error("HTTP Error: {0}".format(errh))
        except requests.exceptions.ConnectionError as errc:
            st.error("Error Connecting: {0}".format(errc))
        except requests.exceptions.Timeout as errt:
            st.error("Timeout Error: {0}".format(errt))
        except AttributeError:
            st.error("Error! Please ensure valid Show ID and API key. Also, double-check your Acast account has admin role on the show in User Management.")
        except requests.exceptions.RequestException as err:
            st.error("Error! Please ensure valid Show ID and API key. Also, double-check your Acast account has admin role on the show in User Management. {0}".format(err))
else:
    st.warning("You must log in to access this page.")
    st.markdown("[Go to Login](../hub.py)")
