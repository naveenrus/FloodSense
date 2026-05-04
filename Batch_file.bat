@echo off
title Flood System Launcher

:: Step 1: Activate the Conda environment using the full path
call C:\Users\NAVEEN\anaconda3\Scripts\activate.bat flood_env

:: Step 2: Change directory to the D drive and the project folder
cd /d D:\flood_systemmm

:: Step 3: Run the Streamlit application
:: Note: Using 'call' ensures the script stays active for the app to run
call streamlit run app.py

:: Step 4: Keep the window open if the app closes or crashes
pause