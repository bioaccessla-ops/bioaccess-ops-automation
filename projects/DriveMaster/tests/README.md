# DriveMaster Demonstration Scripts

This directory contains scripts to demonstrate and test the core functionality of the DriveMaster tool.

## Prerequisites

1.  **Test Folder:** You must have a dedicated test folder in your Google Drive.
2.  **Folder ID:** Get the ID of this test folder from the Google Drive URL.
3.  **Edit Scripts:** Open `run_demo.sh` or `run_demo.bat` and replace the placeholder `YOUR_ROOT_FOLDER_ID` with your actual test folder ID.

## How to Run

### For Windows

Open a command prompt or PowerShell, navigate to the `tests` directory, and run:
```sh
.\run_demo.bat
```

### For macOS / Linux

1.  Make the script executable (only needs to be done once):
    ```sh
    chmod +x run_demo.sh
    ```
2.  Run the script:
    ```sh
    ./run_demo.sh
    ```

## What the Demo Does

The script will perform the following actions:

1.  **Full Permission Report:** Generates a complete report of all permissions in the test folder and saves it to the `reports/` directory.
2.  **User-Specific Report:** Generates a filtered report showing permissions for only one specific user.
3.  **Dry Run of Changes:** Simulates applying permission changes based on `sample_actions.csv` without actually modifying anything on Google Drive.
4.  **Live Run of Changes (Commented Out):** Shows the command to apply changes live, but it is disabled by default for safety.