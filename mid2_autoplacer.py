import streamlit as st
import requests
import xml.etree.ElementTree as ET
from base64 import b64decode
import csv
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import json
import re
import threading
from queue import Queue
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
import pandas as pd
import base64
from io import StringIO

st.header('Mid2 Autoplacer 🎯 ')
st.markdown("""
**What does this script do?**

- Automatically places the second midroll marker (Mid2) across a show's back catalogue.
- Mid2 markers will only be placed in episodes that already have existing Mid1 markers.
- Mid2 placement occurs only in episodes longer than 20 minutes.
- If the existing postroll is positioned 5 minutes or more before the end of the episode, it will be swapped with Mid2, and the postroll will be moved to the very end of the episode.

**What do I need?**

- Show ID
- API Key

**How do I run this?**

- Add yourself as an admin to the show in User Management
- Copy the Show ID from AdminCMS (the ID must be formatted `622f830e50e1630012bd369a` without hyphens)
- Enter the Show ID and your API key into the form below and click Start
######
""")


# Hardcoded password
password = 'EXAMPLE_HARDCODED'

# Function to normalize titles
def normalize_title(title):
    title = title.lower()
    title = re.sub(r'[^a-z0-9]', '', title)
    return title

# Fetch and parse RSS feed
def fetch_and_parse_rss(url):
    response = requests.get(url)
    content = response.text
    root = ET.fromstring(content)
    namespace = {'acast': 'https://schema.acast.com/1.0/'}

    podcast_title = root.find('.//channel/title').text
    signature = root.find('.//acast:signature', namespace).text

    episodes = [
        {
            'episodeId': item.find('.//acast:episodeId', namespace).text,
            'settings': item.find('.//acast:settings', namespace).text,
            'title': item.find('.//title').text,
            'pubDate': item.find('.//pubDate').text
        }
        for item in root.findall('.//item')
        if item.find('.//acast:episodeId', namespace) is not None
    ]

    return podcast_title, signature, episodes

def extract_valid_json_from_text(text):
    try:
        start = text.index('{')
        end = text.rindex('}') + 1
        valid_json = text[start:end]
        return json.loads(valid_json)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Failed to extract JSON: {e}")
        return {}

def decrypt(signature, text, password):
    try:
        salt = b64decode(signature)
        kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1, backend=default_backend())
        key = kdf.derive(password.encode())
        cipher = Cipher(algorithms.AES(key), modes.CBC(salt), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(b64decode(text)) + decryptor.finalize()
        decrypted_text = decrypted.decode('utf-8')
        return extract_valid_json_from_text(decrypted_text)
    except Exception as e:
        print(f"Decryption failed: {e}")
        return {}

def fetch_media_info(media_url):
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))

    try:
        response = session.get(f"https://sphinx-encoder-api-v2.prod.ateam.acast.cloud/file?url={requests.utils.quote(media_url)}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch data for URL {media_url}: {response.status_code}")
            return {}
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data for URL {media_url}: {e}")
        return {}

def fetch_all_episode_details(showId, headers):
    url = f"https://open.acast.com/rest/shows/{showId}/episodes"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch all episodes details: {response.status_code}")
        return []

def find_longest_silence_within_range(silence_periods, start_percentage, end_percentage, duration):
    if not silence_periods:
        return None

    start_time = duration * start_percentage / 100
    end_time = duration * end_percentage / 100
    longest_silence = max(
        (silence for silence in silence_periods if start_time <= silence['end'] <= end_time),
        key=lambda s: s['duration'],
        default=None
    )

    if longest_silence:
        silence_start = longest_silence['end'] - longest_silence['duration']
        return {'start': silence_start, 'end': longest_silence['end'], 'duration': longest_silence['duration']}
    return None

def check_marker_exists(markers, placement, index=0):
    count = 0
    for marker in markers:
        if marker['placement'] == placement and 'start' in marker:
            if count == index:
                return marker['start']
            count += 1
    return None

def sanitize_filename(title):
    return re.sub(r'[^a-z0-9]', '', title.lower().replace(' ', '_'))

def process_episode(episode, signature, password, queue):
    episode_guid = episode['_id']
    episode_title = episode['title']
    settings_text = episode['settings']
    
    decrypted_settings = decrypt(signature, settings_text, password)
    if 'cms' in decrypted_settings and 'mediaUrl' in decrypted_settings['cms']:
        media_url = decrypted_settings['cms']['mediaUrl']
        media_info = fetch_media_info(media_url)
        if not media_info:
            queue.put(None)  # Skipping episodes if media info could not be fetched
            return

        silence_periods = media_info.get('silenceDetected', [])
        episode_duration = media_info.get('duration', 0)

        if episode_duration < 1200:  # Skipping episodes with duration less than 20 minutes
            queue.put(None)
            return

        markers = episode.get('markers', [])
        # print(f"Processing episode {episode_guid}: Found markers {markers}")

        preroll = check_marker_exists(markers, 'preroll')
        postroll = check_marker_exists(markers, 'postroll')

        # Check if postroll is at the very end of the episode
        postroll_at_end = postroll is not None and postroll >= episode_duration - 1

        # Collect all midroll markers
        midroll = check_marker_exists(markers, 'midroll', 0)
        midroll2 = check_marker_exists(markers, 'midroll', 1)

        # Skip if midroll2 already exists
        if midroll2:
            queue.put(None)
            return

        # New logic to handle postroll marker
        if postroll and postroll < episode_duration - 300:  # 300 seconds = 5 minutes
            midroll2 = postroll
            postroll = episode_duration  # Update postroll to the very end

        if not midroll:
            queue.put(None)  # Skip if no existing midroll
            return

        if not midroll2 and episode_duration >= 1200:
            start_percentage = 50
            if midroll:
                midroll_end_time = midroll + episode_duration * 0.10  # Ensure 10% difference
                start_percentage = max(start_percentage, (midroll_end_time / episode_duration) * 100)

            longest_silence_midroll2 = find_longest_silence_within_range(silence_periods, start_percentage, 90, episode_duration)
            if longest_silence_midroll2:
                midroll2 = longest_silence_midroll2['start'] + (longest_silence_midroll2['duration'] / 2)
                if midroll and abs(midroll2 - midroll) < (0.10 * episode_duration):
                    midroll2 = None
                if preroll and abs(midroll2 - preroll) < (0.10 * episode_duration):
                    midroll2 = None
                if postroll and midroll2 is not None and abs(midroll2 - postroll) < (0.10 * episode_duration):
                    midroll2 = None

            if not midroll2 and midroll:
                new_midroll_range_end = max(50, (midroll / episode_duration) * 100 - 10)
                new_midroll_range_start = max(20, (midroll / episode_duration) * 100 - 20)
                new_midroll_suggestion = find_longest_silence_within_range(silence_periods, new_midroll_range_start, new_midroll_range_end, episode_duration)
                if new_midroll_suggestion:
                    midroll2 = new_midroll_suggestion['start'] + (new_midroll_suggestion['duration'] / 2)
                    if midroll2 == midroll or abs(midroll2 - midroll) < (0.10 * episode_duration):
                        midroll2 = None

        if not midroll2:
            queue.put(None)  # Skip if no midroll2 can be generated
            return

        publish_date = episode.get('publishDate', '')

        result = [
            episode_guid, 
            preroll, 
            midroll if midroll else '', 
            midroll2 if midroll2 else '', 
            postroll, 
            episode_duration, 
            'Yes' if postroll_at_end else 'No',  # Note if postroll is at the end
            publish_date
        ]
        # print(f"Result for episode {episode_guid}: {result}")
        queue.put(result)
    else:
        print(f"Skipping episode {episode_guid} due to missing 'cms' or 'mediaUrl'")
        queue.put(None)

def worker(episode, signature, password, queue):
    process_episode(episode, signature, password, queue)

def parse_acast_date(date_str):
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Date format not recognized: {date_str}")

def parse_rss_date(date_str):
    return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")

def print_patch_request(episode_guid, preroll, midroll, midroll2, postroll, publish_date, episode_status, showId, headers):
    # Construct markers string dynamically based on the presence of midroll2
    if midroll2:
        markers = f"{preroll},{midroll},{midroll2},{postroll}"
    else:
        markers = f"{preroll},{midroll},{postroll}"

    update_payload = {
        'markers': markers,
        'publishDate': publish_date,
        'status': episode_status
    }

    url = f"https://open.acast.com/rest/shows/{showId}/episodes/{episode_guid}"
    
    max_retries = 3
    for attempt in range(max_retries):
        response = requests.patch(url, headers=headers, data=json.dumps(update_payload))
        
        print(f"PATCH request for Episode GUID {episode_guid}:\nURL: {url}\nHeaders: {headers}\nPayload:\n{json.dumps(update_payload, indent=4)}")
        print(f"Response Status Code: {response.status_code}\nResponse Text: {response.text}")

        if response.status_code == 502:
            print(f"Received 502 error, retrying... ({attempt + 1}/{max_retries})")
            time.sleep(2)  # Wait for 2 seconds before retrying
            continue
        break

    # Log non-200 responses
    if response.status_code != 200:
        with open('error_log.txt', 'a') as log_file:
            log_file.write(f"Episode GUID: {episode_guid}\nStatus Code: {response.status_code}\nResponse Text: {response.text}\n\n")
    
    return response

def process_csv(file_content, showId, headers, progress_bar, status_text):
    df = pd.read_csv(StringIO(file_content))
    total_rows = len(df)
    updated_count = 0  # Counter for updated episodes
    
    if total_rows == 0:
        st.warning("No episodes to process.")
        progress_bar.progress(1.0)
        status_text.text("No episodes found in the CSV.")
        return

    for index, row in df.iterrows():
        episode_guid = row['Episode GUID']
        preroll = row['Preroll']
        midroll = row.get('Midroll', None)
        midroll2 = row.get('Midroll2', None)
        postroll = row['Postroll']
        publish_date = row['Publish Date']
        episode_status = 'published'  # or derive from the CSV if needed

        # Ensure midroll2 is only included if it exists
        if pd.isna(midroll2):
            midroll2 = None

        response = print_patch_request(episode_guid, preroll, midroll, midroll2, postroll, publish_date, episode_status, showId, headers)
        if response.status_code == 200:
            updated_count += 1  # Increment counter if the patch request was successful
        time.sleep(1)  # Add a delay of 1 second between requests

        # Update progress bar and status text
        progress_bar.progress((index + 1) / total_rows)
        status_text.text(f"Processing episode {index + 1} of {total_rows}")

    # Display the number of episodes updated
    st.success(f"Number of episodes updated: {updated_count}\n\nAll done! 🎉")

def save_to_google_drive_via_pipedream(filename, file_content):
    webhook_url = "https://eowecaqy8eij74h.m.pipedream.net"
    file_content_base64 = base64.b64encode(file_content.encode('utf-8')).decode('utf-8')
    
    payload = {
        "filename": filename,
        "file": file_content_base64
    }
    
    response = requests.post(webhook_url, json=payload)
    if response.status_code == 200:
        print("File successfully uploaded to Google Drive via Pipedream.")
        st.success("Existing timestamps have been backed up successfully. Starting to insert mid2 markers now...")
    else:
        print(f"Failed to upload file: {response.status_code} - {response.text}")
        st.error(f"Failed to back up timestamps: {response.status_code} - {response.text}")

def main(showId, key):
    feed_url = f"https://feeds.acast.com/public/shows/{showId}"
    headers = {'x-api-key': key, 'Content-Type': 'application/json'}

    podcast_title, signature, rss_episodes = fetch_and_parse_rss(feed_url)
    # Placeholder for backup message
    backup_message = st.empty()
    backup_message.write(f"Backing up existing timestamps for {podcast_title} \n\nThis may take a few minutes...")  # Display the podcast title
    print(f"Podcast Title: {podcast_title}, Total Episodes Fetched: {len(rss_episodes)}")

    sanitized_title = sanitize_filename(podcast_title)
    filename = f"{sanitized_title}_timestamp_export.csv"

    queue = Queue()
    threads = []

    detailed_episodes = fetch_all_episode_details(showId, headers)
    print(f"Total Detailed Episodes Fetched: {len(detailed_episodes)}")

    # Create a mapping of publish date to detailed episode data
    detailed_episodes_map = {
        parse_acast_date(episode['publishDate']).strftime("%Y-%m-%d %H:%M:%S"): episode
        for episode in detailed_episodes
        if 'publishDate' in episode and episode['publishDate'] and episode.get('status') == 'published'  # Ensure the episode has a valid publish date and is published
    }

    for rss_episode in rss_episodes:
        rss_pub_date = parse_rss_date(rss_episode['pubDate']).strftime("%Y-%m-%d %H:%M:%S")
        if rss_pub_date in detailed_episodes_map:
            detailed_episode = detailed_episodes_map[rss_pub_date]
            detailed_episode['settings'] = rss_episode['settings']
            thread = threading.Thread(target=worker, args=(detailed_episode, signature, password, queue))
            thread.start()
            threads.append(thread)
        else:
            print(f"Skipping episode {rss_episode['episodeId']} as it was not found in detailed episodes")

    for thread in threads:
        thread.join()

    results = []
    while not queue.empty():
        result = queue.get()
        if result:
            results.append(result)

    # Sort results by publish date from latest to oldest, handle None values
    results.sort(key=lambda x: x[-1] if x[-1] else '', reverse=True)

    file_content = "Episode GUID,Preroll,Midroll,Midroll2,Postroll,Episode Duration,Postroll At End,Publish Date\n"
    file_content += "\n".join([f'{row[0]},{row[1]},{row[2]},{row[3]},{row[4]},{row[5]},{row[6]},{row[7]}' for row in results])

    save_to_google_drive_via_pipedream(filename, file_content)

    print(f"Data sent to Pipedream webhook for Google Drive upload successfully.")

    # After backup is completed
    backup_message.empty()

    # Initialize progress bar and status text
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Process the CSV to make PATCH requests
    process_csv(file_content, showId, headers, progress_bar, status_text)

# Check if the user is authenticated
if st.session_state.get("authentication_status"):
    with st.form(key='my_form'):
        showId = st.text_input("Show ID:")
        key = st.text_input("API Key:", type="password")

        # Status placeholder
        processing_time_message = st.empty()
        processing_time_message.caption("Processing time may vary depending on episode count.")
        
        submit_button = st.form_submit_button(label='Start')
        status_message = st.empty()

    if submit_button:
        processing_time_message.empty()
        status_message.write(f'Processing Show ID: {showId}')
        try:
            main(showId, key)
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
