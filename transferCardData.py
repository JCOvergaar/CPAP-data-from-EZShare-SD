######################################################################################
# This script allows you to easily use an inexpensive EZShare SD card or adapter in
# your Resmed CPAP/BiPAP device and download the data from your CPAP/BiPAP device for
# use in OSCAR and similar software without having to remove the card every time.
# For Mac users, it can automatically switch to the EZShare network and back. 
# For Windows users, leave USE_NETWORK_SWITCHING set to False.
# This was tested on a Resmed AirSense 11 and AirCurve 10. YMMV on other devices.
# OSCAR can be downloaded here https://www.sleepfiles.com/OSCAR/
# OSCAR is software that provides excellent reporting with far more detail than myAir
# Visit http://apneaboard.com to learn more about improving your CPAP results.
######################################################################################

######################################################################################
# Setup instructions for Mac users:
#  Install HomeBrew (if you don't have it)
#    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
#  Install Python 3 using HomeBrew
#    brew install python
# Install additional libraries using python's package installer
#    pip install requests beautifulsoup4
######################################################################################

######################################################################################
# Setup instructions for Windows users
# Install Python 3 from the official website: https://www.python.org/downloads/
# Make sure to check the option to add Python to PATH during the installation process.
# 
# Open Command Prompt and run the following commands to install additional libraries:
#   pip install requests beautifulsoup4
######################################################################################


# Import Required Python libraries
import os
import requests
import threading
import subprocess
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

######################################################################################
# Configuration variables
######################################################################################

TARGET_DIR = os.path.join(os.path.expanduser('~'), "Documents", "CPAP_Data")
START_DATE = 15  # Integer -- number of days to go back from the current date
        # alternative date filters
        # START_DATE = "20220701"   # Start date in YYYYMMDD format
        # START_DATE = "ALL"        # Option to start from the earliest date logged
SHOW_PROGRESS = True                # Set to False to suppress output
OVERWRITE_EXISTING_FILES = True     # Set to True if you want to overwrite existing files
INCLUDE_EMPTY_FOLDERS = True        # Set to True if you want to include empty folders for days CPAP wasn't used.


######################################################################################
# WiFi Switching Configuration (Mac Only)
# This is just a convenience thing and is not required for the code to function
# Enable it if you want, but only if you're using a Mac
######################################################################################

USE_NETWORK_SWITCHING = False #Change to True to avoid having to change networks by hand.

EZSHARE_NETWORK = "ez Share"        # Default, can be changed in the ezshare.cfg file on the card
EZSHARE_PASSWORD = "88888888"       # Default, can be changed in the ezshare.cfg file on the card
DEFAULT_NETWORK = "{Your WiFi SSID}"
DEFAULT_PASSWORD = "Your WiFi password"
CONNECTION_DELAY = 5                # Networks don't connect instantly. 5 seconds is the default, change it if needed.

######################################################################################
# Anything from this point on should not require modification as of Summer 2023
######################################################################################

# Helper function to create a directory if not exists
def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)
        
# Helper function to download a file
def download_file(url, target_path):
    if OVERWRITE_EXISTING_FILES or not os.path.exists(target_path):
        response = requests.get(url, stream=True)
        with open(target_path, 'wb') as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)

# Function to download the daily files, with various flags to customize output
def download_datalog_files(url, target_path):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a', href=True)
    if not links or all(not link['href'].endswith('.EDF') for link in links):
        return False  # No files to download
    
    threads = []
    for link in links:
        if link['href'].endswith('.EDF'):
            download_url = "http://192.168.4.1/download?file=" + link['href'].split('/')[-1]
            file_name = os.path.basename(download_url.split('?file=')[-1])
            file_path = os.path.join(target_path, file_name)
            t = threading.Thread(target=download_file, args=(download_url, file_path))
            threads.append(t)
            t.start()
            # Limiting the number of concurrent downloads to 4
            if len(threads) >= 4:
                [t.join() for t in threads]
                threads = []

    return True  # Files were downloaded

# Helper function to switch networks temporarily. Password optional.
def connect_to_wifi(ssid, password=None):
    cmd = f'networksetup -setairportnetwork en0 {ssid}'
    if password:
        cmd += f' {password}'
    subprocess.run(cmd, shell=True)



if USE_NETWORK_SWITCHING:
    # Connect to the EZShare card's network to download files

    print(f"Connecting to {EZSHARE_NETWORK}. Waiting {CONNECTION_DELAY} seconds for connection to establish...")
    connect_to_wifi(EZSHARE_NETWORK, EZSHARE_PASSWORD) #password optional if saved
    time.sleep(CONNECTION_DELAY)  # wait for the connection to establish

# Download static files (always overwrite)
if SHOW_PROGRESS:
    print("Downloading static files...")
static_files = [
    "http://192.168.4.1/download?file=JOURNAL.JNL",
    "http://192.168.4.1/download?file=STR.EDF",
    "http://192.168.4.1/download?file=SETTINGS%5CCURREN~1.JSO",
    "http://192.168.4.1/download?file=SETTINGS%5CCURREN~1.CRC"
]

for url in static_files:
    file_name = os.path.basename(url.split('?file=')[-1])
    target_path = os.path.join(TARGET_DIR, file_name)
    download_file(url, target_path)
    if SHOW_PROGRESS:
        print(f"Downloading {file_name}...")

# Download datalog files
if SHOW_PROGRESS:
    print("\nDownloading daily CPAP data...")


# Iterate through the directories by date, respecting the start date
current_date = datetime.today()
date_folder = current_date.strftime('%Y%m%d')

# Determine the start date based on the configuration
if isinstance(START_DATE, int):
    start_date = datetime.today() - timedelta(days=START_DATE)
elif START_DATE == "ALL":
    # Retrieve the earliest date from the datalog folder
    response = requests.get("http://192.168.4.1/dir?dir=A:%5CDATALOG")
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a', href=True)
    earliest_date = min([link.text.strip() for link in links])
    start_date = datetime.strptime(earliest_date, '%Y%m%d')
else:
    start_date = datetime.strptime(START_DATE, '%Y%m%d')

while datetime.strptime(date_folder, '%Y%m%d') >= start_date:
    current_date -= timedelta(days=1)
    date_folder = current_date.strftime('%Y%m%d')

    folder_url = f"http://192.168.4.1/dir?dir=A:%5CDATALOG%5C{date_folder}"
    target_path = os.path.join(TARGET_DIR, "DATALOG", date_folder)
    
    if os.path.exists(target_path) and not OVERWRITE_EXISTING_FILES:
        print(f"Files for {date_folder} already exist. Skipping directory...")
        continue

    create_directory(target_path)
    files_downloaded = download_datalog_files(folder_url, target_path)
    
    if not files_downloaded and not INCLUDE_EMPTY_FOLDERS:
        os.rmdir(target_path)
        if SHOW_PROGRESS:
            print(f"No CPAP data for {current_date.strftime('%Y-%m-%d')} -- skipped")
    elif SHOW_PROGRESS:
        print(f"{current_date.strftime('%Y-%m-%d')} complete.")


if USE_NETWORK_SWITCHING:
    # Switch back to the default network
    print(f"\nReconnecting to {DEFAULT_NETWORK}. Waiting {CONNECTION_DELAY} seconds for connection to establish...")
    connect_to_wifi(DEFAULT_NETWORK, DEFAULT_PASSWORD) #password optional if saved
    time.sleep(CONNECTION_DELAY)  # wait for the connection to establish

# End of script
