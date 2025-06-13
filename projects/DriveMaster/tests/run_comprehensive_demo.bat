@echo off
REM # --- Comprehensive DriveMaster Demonstration Script ---

REM # --- CONFIGURATION ---
set ROOT_FOLDER_ID=1Q_GFk5fC7huNF-F1eTLmNKvPPMA68nLw
REM # ---

echo.
echo [STEP 1] Generating a BASELINE report to see the original state...
python ../main.py report --root %ROOT_FOLDER_ID% --output comprehensive_baseline.csv
echo Report saved to reports/comprehensive_baseline.csv
echo.
echo --------------------------------------------------------------------
echo.

echo [STEP 2] Applying a comprehensive set of permissions LIVE...
echo.
echo The script will now ADD a variety of user, group, and domain permissions.
echo.
echo WARNING: The next step will make REAL changes to your Google Drive permissions.
PAUSE
python ../main.py apply-changes --input ./comprehensive_actions.csv --live
echo Comprehensive changes applied.
echo.
echo --------------------------------------------------------------------
echo.

echo [STEP 3] VERIFYING a report AFTER applying changes...
python ../main.py report --root %ROOT_FOLDER_ID% --output report_after_comprehensive_changes.csv
echo Verification report saved to reports/report_after_comprehensive_changes.csv
echo.
echo --------------------------------------------------------------------
echo.

echo [STEP 4] Applying ROLLBACK to remove all added permissions...
echo.
echo The next step will remove every permission that was just added.
PAUSE
python ../main.py apply-changes --input ./comprehensive_rollback.csv --live
echo.
echo Rollback complete.
echo --------------------------------------------------------------------
echo.

echo [STEP 5] FINAL VERIFICATION after rolling back changes...
python ../main.py report --root %ROOT_FOLDER_ID% --output report_after_comprehensive_rollback.csv
echo Final verification report saved to reports/report_after_comprehensive_rollback.csv
echo.
echo --------------------------------------------------------------------
echo.

echo Comprehensive demonstration finished.
PAUSE