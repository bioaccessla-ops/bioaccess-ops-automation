# initial_qb_auth.py
import os
from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from dotenv import load_dotenv # <--- ADD THIS LINE

# Load environment variables from .env file
load_dotenv() # <--- ADD THIS LINE

# From your Intuit Developer App settings (now loaded from .env)
QB_CLIENT_ID = os.environ.get("QB_CLIENT_ID")
QB_CLIENT_SECRET = os.environ.get("QB_CLIENT_SECRET")
QB_REDIRECT_URI = os.environ.get("QB_REDIRECT_URI")
QB_ENVIRONMENT = os.environ.get("QB_ENVIRONMENT")

# Ensure QB_REDIRECT_URI is set, as it's critical for this script
if not QB_REDIRECT_URI:
    raise ValueError("QB_REDIRECT_URI must be set in your .env file.")


auth_client = AuthClient(
    client_id=QB_CLIENT_ID,
    client_secret=QB_CLIENT_SECRET,
    redirect_uri=QB_REDIRECT_URI,
    environment=QB_ENVIRONMENT,
)

# Step 1: Generate the authorization URL
auth_url = auth_client.get_authorization_url([
    Scopes.ACCOUNTING,
    # Add other scopes if needed, e.g., Scopes.PAYMENTS, Scopes.OPENID
])

print(f"Please go to this URL in your browser to authorize your app:\n{auth_url}")
print("\nAfter authorization, you will be redirected to your Redirect URI.")
print("Copy the 'code' and 'realmId' parameters from the URL after redirection.")

auth_code = input("Enter the 'code' from the redirected URL: ")
realm_id = input("Enter the 'realmId' from the redirected URL: ")

# Step 2: Exchange the authorization code for tokens
try:
    auth_client.get_bearer_token(auth_code, realm_id=realm_id) 
    
    print("\nAuthentication successful!")
    print(f"Access Token: {auth_client.access_token}")
    print(f"Refresh Token: {auth_client.refresh_token}")
    print(f"Realm ID (Company ID): {auth_client.realm_id}")

    # IMPORTANT: Update your .env file with these values!
    # For automated scripts, you'd usually have a mechanism to store/update these
    # but for this initial script, you'll copy-paste them into your .env file manually.
    print("\nIMPORTANT: Copy the Refresh Token and Realm ID printed above.")
    print("Then, open your .env file and paste them into the QB_REFRESH_TOKEN and QB_REALM_ID lines.")
    print("e.g., QB_REFRESH_TOKEN=\"YOUR_COPIED_TOKEN\"")
    print("      QB_REALM_ID=\"YOUR_COPIED_REALM_ID\"")


except Exception as e:
    print(f"Error during token exchange: {e}") 