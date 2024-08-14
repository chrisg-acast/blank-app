import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# Step 1: Define the user credentials and hashing
usernames = ["user1", "user2"]
names = ["John Doe", "Jane Doe"]
passwords = ["password1", "password2"]

# Hash the passwords
hashed_passwords = stauth.Hasher(passwords).generate()

# Step 2: Load user credentials into a correctly structured dictionary
credentials = {
    "usernames": {
        usernames[0]: {"name": names[0], "password": hashed_passwords[0]},
        usernames[1]: {"name": names[1], "password": hashed_passwords[1]},
    }
}

# Step 3: Print the credentials to verify the structure
st.write("Credentials Dictionary:", credentials)

# Step 4: Load the credentials into the authenticator
try:
    authenticator = stauth.Authenticate(
        credentials["usernames"],
        "my_cookie_name",  # Cookie name for storing authentication state
        "my_signature_key",  # Signature key to secure the cookie
        cookie_expiry_days=30
    )
    st.write("Authenticator created successfully.")
except KeyError as e:
    st.error(f"KeyError: {e}")

# Step 5: Implement the login form
name, authentication_status, username = authenticator.login("Login", "main") if 'authenticator' in locals() else (None, None, None)

if authentication_status:
    st.write(f"Welcome, {name}!")
    st.write("This is a protected content page. Only authenticated users can see this.")
elif authentication_status is False:
    st.error("Username/password is incorrect")
elif authentication_status is None:
    st.warning("Please enter your username and password")

# Step 6: Implement the logout button
if authentication_status:
    if st.button("Logout"):
        authenticator.logout("main")
        st.write("You have been logged out")