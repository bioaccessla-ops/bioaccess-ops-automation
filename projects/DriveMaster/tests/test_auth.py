# main.py
from projects.DriveMaster.src.auth import authenticate_and_get_service
from googleapiclient.errors import HttpError

def main():
    print("--- Starting Test ---")
    drive_service = authenticate_and_get_service()

    if drive_service:
        try:
            # This is a simple, harmless API call to test if the service works.
            about = drive_service.about().get(fields='user').execute()
            user_email = about['user']['emailAddress']
            
            print("\n--- TEST RESULT ---")
            print(f"✅ Success! Script is authenticated and acting as: {user_email}")

        except HttpError as e:
            print(f"\n--- TEST RESULT ---")
            print(f"❌ Failure! An API error occurred: {e}")
    else:
        print(f"\n--- TEST RESULT ---")
        print("❌ Failure! The authentication process did not return a service object.")


if __name__ == '__main__':
    main()