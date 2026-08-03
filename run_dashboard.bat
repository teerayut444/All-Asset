@echo off
title All Asset NPA Dashboard Launcher (7 Companies)
echo ======================================================================
echo   All Asset NPA Dashboard Launcher - 7 Companies
echo   [ Baania / BAM / SAM / ZmyHome / Livinginsider / DDproperty / Taladnudbaan ]
echo ======================================================================
echo.
echo Checking virtual environments or global python...
echo.

set VENV_PATH_LIVING=..\Livinginsider NPA\.venv
if exist "%VENV_PATH_LIVING%\Scripts\activate.bat" (
    echo [Info] Found virtual environment in Livinginsider NPA folder. Activating...
    call "%VENV_PATH_LIVING%\Scripts\activate.bat"
    goto run
)

set VENV_PATH_BAM=..\BAM NPA\.venv
if exist "%VENV_PATH_BAM%\Scripts\activate.bat" (
    echo [Info] Found virtual environment in BAM NPA folder. Activating...
    call "%VENV_PATH_BAM%\Scripts\activate.bat"
    goto run
)

set VENV_PATH_ZMY=..\ZmyHome NPA\.venv
if exist "%VENV_PATH_ZMY%\Scripts\activate.bat" (
    echo [Info] Found virtual environment in ZmyHome NPA folder. Activating...
    call "%VENV_PATH_ZMY%\Scripts\activate.bat"
    goto run
)

set VENV_PATH_BAANIA=..\Baania NPA new\.venv
if exist "%VENV_PATH_BAANIA%\Scripts\activate.bat" (
    echo [Info] Found virtual environment in Baania NPA new folder. Activating...
    call "%VENV_PATH_BAANIA%\Scripts\activate.bat"
    goto run
)

set VENV_PATH_DD=..\DDproperty NPA\.venv
if exist "%VENV_PATH_DD%\Scripts\activate.bat" (
    echo [Info] Found virtual environment in DDproperty NPA folder. Activating...
    call "%VENV_PATH_DD%\Scripts\activate.bat"
    goto run
)

set VENV_PATH_TALAD=..\Taladnudbaan NPA\.venv
if exist "%VENV_PATH_TALAD%\Scripts\activate.bat" (
    echo [Info] Found virtual environment in Taladnudbaan NPA folder. Activating...
    call "%VENV_PATH_TALAD%\Scripts\activate.bat"
    goto run
)

echo [Info] No local virtual environment found. Using global python environment.

:run
echo.
echo [Launch] Starting Streamlit Dashboard for 7 Companies...
python -m streamlit run app.py
if %errorlevel% neq 0 (
    echo.
    echo [Error] Failed to start Streamlit. Attempting to install dependencies...
    python -m pip install streamlit pandas openpyxl plotly bs4 requests pyarrow
    echo.
    echo [Launch] Retrying starting Streamlit Dashboard...
    python -m streamlit run app.py
)

pause
