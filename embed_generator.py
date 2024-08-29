import csv
import feedparser
import re
import os
import streamlit as st
import pandas as pd

def sanitize_filename(filename):
    filename = re.sub(r'[\\/*?:"<>|]', "", filename)
    return filename.replace(" ", "_")

def get_episode_ids(show_id):
    url = f"https://feeds.acast.com/public/shows/{show_id}"
    feed = feedparser.parse(url)
    show_title = feed.feed.title
    sanitized_show_title = sanitize_filename(show_title)
    episodes = []

    for entry in feed.entries:
        if 'acast_episodeid' in entry:
            embed_code = f'<iframe src="https://embed.acast.com/{show_id}/{entry["acast_episodeid"]}" frameBorder="0" width="100%" height="190px"></iframe>'
            pub_date = entry.published if 'published' in entry else 'Unknown'
            episodes.append((entry.title, pub_date, embed_code))

    return episodes, show_title, sanitized_show_title

def save_to_csv(episodes, sanitized_show_title):
    csv_file = f'{sanitized_show_title}.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Episode Title", "Published Date", "Embed Code"])
        writer.writerows(episodes)
    return csv_file

st.header('🎧 Embed Player Generator') 
st.markdown("Generate a CSV file with episode title, publish date, and embed player code.")

show_id = st.text_input("Acast Show ID:")
generate_button = st.button('Generate')

if generate_button and show_id:
    try:
        processing_text = st.empty()
        processing_text.write(f'Processing Show ID: {show_id}')
        episodes, show_title, sanitized_show_title = get_episode_ids(show_id)
        processing_text.empty() 
        st.write(f'{show_title} ({len(episodes)} episodes)') 
        filename = save_to_csv(episodes, sanitized_show_title) 
        df = pd.read_csv(filename)
        st.write(df)
        csv = df.to_csv(index=False).encode()
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"{filename}",
            mime="text/csv",
        )

    except Exception:
        st.error("Error! Verify the Show ID is valid and the feed has not been redirected.")