import streamlit as st
import requests
import time
from streamlit_extras.add_vertical_space import add_vertical_space

# Function to search podcasts
def search_podcasts(query, retries=3):
    for i in range(retries):
        try:
            response = requests.get('https://itunes.apple.com/search', params={
                'term': query,
                'media': 'podcast',
            })
            response.raise_for_status()  # Raises an HTTPError if the response was unsuccessful
            data = response.json()
            podcasts = [
                {
                    'title': result['trackName'],
                    'link': result['collectionViewUrl'],
                    'feed': result.get('feedUrl', 'N/A'),
                    'artwork': result['artworkUrl600'],
                    'author': result.get('artistName', 'N/A'),
                    'genre': result.get('primaryGenreName', 'N/A'),
                    'episode_count': result.get('trackCount', 'N/A'),
                }
                for result in data['results']
            ]
            podcasts = sorted(podcasts, key=lambda p: 'acast.com' not in p['feed'])
            return podcasts

        except requests.exceptions.HTTPError as e:
            if response.status_code == 503 and i < retries - 1:  # Retry on 503 error
                time.sleep(1)
                continue
            else:
                st.error(f"HTTP error: {e}")
                return None
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            return None

    return None  # If we got here, we failed all retries

# Function to display podcasts
def display_podcasts(podcasts):
    if not podcasts:
        st.warning("No podcasts found.")
        return
    
    for podcast in podcasts:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(podcast["artwork"], use_column_width=True)
        with col2:
            st.markdown(f"### [{podcast['title']}]({podcast['link']})")
            st.markdown(f"**Author:** {podcast['author']}")
            st.markdown(f"**Genre:** {podcast['genre']}")
            st.markdown(f"**Episodes:** {podcast['episode_count']}")
            if "acast.com" in podcast['feed']:
                guid = podcast['feed'].split("/")[-2] if podcast['feed'].endswith('/') else podcast['feed'].split("/")[-1]
                acast_link = f"https://shows.acast.com/{guid}"
                st.markdown(f"**Show ID:** {guid}")
                st.markdown(f"[Acast Link]({acast_link})")
            st.markdown(f"**RSS Feed:** {podcast['feed']}")

# Main function
def main():
    st.title('Import Timestamps')
    st.write('Coming soon!')
    
    st.header('🔍 RSS Finder')
    st.write("Search through the Apple Podcasts database to find the RSS feed of a show.")
    add_vertical_space(2)

    podcast_name = st.text_input('Podcast Name:')
    if st.button('Search'):
        with st.spinner('Searching Apple Podcasts...'):
            podcasts = search_podcasts(podcast_name)
            if podcasts:
                display_podcasts(podcasts)
            else:
                st.warning("No podcasts found. Try another search.")

if __name__ == '__main__':
    main()
