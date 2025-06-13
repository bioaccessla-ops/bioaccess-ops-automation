@echo off
REM # --- Final DriveMaster Demonstration Script with All Steps ---

REM # --- CONFIGURATION ---
set ROOT_FOLDER_ID=1Q_GFk5fC7huNF-F1eTLmNKvPPMA68nLw
set USER_EMAIL=jmoreno@bioaccessla.com
REM # ---

echo.
echo [DEMO 1] Generating a FULL permission report (baseline)...
python ../main.py report --root %ROOT_FOLDER_ID% --output full_demo_report.csv
echo Report saved to reports/full_demo_report.csv
echo.
echo --------------------------------------------------------------------
echo.

echo [DEMO 2] Generating a USER-SPECIFIC permission report for %USER_EMAIL%...
python ../main.py report --root %ROOT_FOLDER_ID% --output user_demo_report.csv --email %USER_EMAIL%
echo Report saved to reports/user_demo_report.csv
echo.
echo --------------------------------------------------------------------
echo.

echo [DEMO 3] Performing a DRY RUN of permission changes...
python ../main.py apply-changes --input ./sample_actions.csv --dry-run
echo.
echo --------------------------------------------------------------------
echo.

echo [DEMO 4] Applying permission changes LIVE...
echo.
echo The script will now make the following changes based on sample_actions.csv:
REM # - Modify: Change ernie.moreno62@gmail.com on 'Test Doc 1' from writer to commenter.
REM # - Remove: Remove ernie.moreno62@gmail.com's reader access from 'Sub-Folder 1'.
REM # - Add: Grant new.test.user@example.com viewer access to 'Test Sheet 2'.
REM # - Remove Domain: Remove bioaccessla.com domain reader access from 'Test Sheet 2'.
echo.
echo WARNING: The next step will make REAL changes to your Google Drive permissions.
PAUSE
python ../main.py apply-changes --input ./sample_actions.csv --live
echo Changes applied.
echo.
echo --------------------------------------------------------------------
echo.

echo [DEMO 5] VERIFYING a report AFTER applying changes...
python ../main.py report --root %ROOT_FOLDER_ID% --output report_after_changes.csv
echo Verification report saved to reports/report_after_changes.csv
echo.
echo --------------------------------------------------------------------
echo.

echo [DEMO 6] Applying ROLLBACK to restore original permissions...
echo.
echo The script will now REVERSE the changes based on rollback_actions.csv:
REM # - Modify: Change ernie.moreno62@gmail.com on 'Test Doc 1' back to writer.
REM # - Add: Restore ernie.moreno62@gmail.com's reader access to 'Sub-Folder 1'.
REM # - Remove: Remove new.test.user@example.com's viewer access from 'Test Sheet 2'.
REM # - Add Domain: Restore bioaccessla.com domain reader access to 'Test Sheet 2'.
echo.
echo The next step will reverse the changes made in DEMO 4.
PAUSE
python ../main.py apply-changes --input ./rollback_actions.csv --live
echo.
echo Rollback complete.
echo --------------------------------------------------------------------
echo.

echo [DEMO 7] FINAL VERIFICATION after rolling back changes...
python ../main.py report --root %ROOT_FOLDER_ID% --output report_after_rollback.csv
echo Final verification report saved to reports/report_after_rollback.csv
echo.
echo --------------------------------------------------------------------
echo.


echo Demonstration finished. You can now compare the CSV files in the 'reports' folder.
PAUSE