#!/usr/bin/env python3

# #################################################################################################
# This script allows you to easily use an inexpensive EZShare SD card or adapter in
# your Resmed CPAP/BiPAP device and download the data from your CPAP/BiPAP device for
# use in OSCAR and similar software without having to remove the card every time.
# For Mac users, it can automatically switch to the EZShare network and back. 
# For Windows users, leave USE_NETWORK_SWITCHING set to False.
# This was tested on a Resmed AirSense 11 and AirCurve 10. YMMV on other devices.
# OSCAR can be downloaded here https://www.sleepfiles.com/OSCAR/
# OSCAR is software that provides excellent reporting with far more detail than myAir
# Visit http://apneaboard.com to learn more about improving your CPAP results.
# #################################################################################################

# #################################################################################################
# Setup instructions for Mac users:
#  Install HomeBrew (if you don't have it)
#    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
#  Install Python 3 using HomeBrew
#    brew install python
# Install additional libraries using python's package installer
#    pip install requests beautifulsoup4
# #################################################################################################

# #################################################################################################
# Setup instructions for Windows users
# Install Python 3 from the official website: https://www.python.org/downloads/
# Make sure to check the option to add Python to PATH during the installation process.
# 
# Open Command Prompt and run the following commands to install additional libraries:
#   pip install requests beautifulsoup4
# #################################################################################################

# #################################################################################################
# The default code (os.path.join etc) will place the file in the path below. 
# You can change that in the config block
# Windows:      C:\Users\MY_USERNAME\Documents\CPAP_Data
# MacOS:        /Users/MY_USERNAME/Documents/CPAP_Data
# Linux et al:  /home/MY_USERNAME/Documents/CPAP_Data
# You can store it wherever you want to, as long as OSCAR can read from it.
# #################################################################################################

# #################################################################################################
# This may be called from its folder directly, with or without arguments to overwrite the defaults:
# python ezshare_resmed.py 
# python ezshare_resmed.py --start_from 20230101 --show_progress Verbose --overwrite
# It may also be called from a shell script, so you can put that on your desktop 
# while keeping the python code in a less accessible location:
# ./run_foo.sh
# ./run_foo.sh --start_from 20230101 --show_progress Verbose --overwrite
# #################################################################################################

# #################################################################################################
# Required imports -- don't modify.
import os
import requests
import time
import sys
import platform
import argparse
from subprocess import run, PIPE
import urllib.parse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import configparser
import re

###################################################################################################

# #################################################################################################
# Location to save the files. Modify to your preferred location as needed:
root_path = os.path.join(os.path.expanduser('~'), "Documents", "CPAP_Data", "SD_card")
#root_path = 'C:\Users\USERNAME\Documents\CPAP_Data\SD_card'
#root_path = '/home/USERNAME/Documents/CPAP_Data/SD_card'
# #################################################################################################

# date filter options:
START_FROM = 5  # Integer -- number of days to go back from the current date
#START_FROM = "20230819"   # Start date in YYYYMMDD format
#START_FROM = "ALL"        # Option to start from the earliest date logged
SHOW_PROGRESS = 'Verbose'  # Can be True, False, or 'Verbose'. Verbose provides considerably more feedback.
OVERWRITE_EXISTING_FILES = False
CREATE_MISSING = False

######################################################################################
# WiFi Switching Configuration (Mac Only)
# This is just a convenience thing and is not required for the code to function
# Disable if you prefer. It won't even try to run except on a mac.
# If you're on ethernet, it should still work unless your DHCP is set to 192.168.4
######################################################################################
USE_NETWORK_SWITCHING = True

EZSHARE_NETWORK = "ezshare"
EZSHARE_PASSWORD = "88888888"
CONNECTION_DELAY = 5
CONNECTION_ID = None

# #################################################################################################
# Typically shouldn't need to edit anything after this point
# #################################################################################################
root_url = 'http://192.168.4.1/dir?dir=A:'

# #################################################################################################
# Read from config file if it exists to overwrite defaults
# #################################################################################################

# Define possible paths for the config file
config_files = [
    'ezshare_resmed.ini',  # In the same directory as the script
    os.path.join(os.path.expanduser('~'), '.config', 'ezshare_resmed.ini'),
    os.path.join(os.path.expanduser('~'), '.config', 'ezshare_resmed', 'ezshare_resmed.ini'),
    os.path.join(os.path.expanduser('~'), '.config', 'ezshare_resmed', 'config.ini')
]

# Iterate through possible paths and use the first one that exists
config_path = None
for file in config_files:
    if os.path.exists(file):
        config_path = file
        break

# If config file is found, read its contents
if config_path:
    # Create a configparser object and read the config file
    config = configparser.ConfigParser()
    config.read(config_path)

    # date filter options:
    START_FROM = config.getint('ezshare_resmed', 'start_from', fallback=5)
    SHOW_PROGRESS = config.get('ezshare_resmed', 'show_progress', fallback='Verbose')
    OVERWRITE_EXISTING_FILES = config.getboolean('ezshare_resmed', 'overwrite', fallback=False)
    CREATE_MISSING = config.getboolean('ezshare_resmed', 'create_missing', fallback=False)
    EZSHARE_NETWORK = config.get('ezshare_resmed', 'sid', fallback='ezshare')
    EZSHARE_PASSWORD = config.get('ezshare_resmed', 'psk', fallback='88888888')
    root_path = config.get('ezshare_resmed', 'path', fallback=os.path.join(os.path.expanduser('~'), "Documents", "CPAP_Data", "SD_card"))

# #################################################################################################
# Allow command line arguments to overwrite defaults
# #################################################################################################
parser = argparse.ArgumentParser(description='Your script description')
parser.add_argument('--start_from', type=str, help='Start from date or number of days')
parser.add_argument('--show_progress', choices=['True', 'False', 'Verbose'], help='Show progress level')
parser.add_argument('--path', type=str, help=f'Set destination path. Defaults to {root_path}')
parser.add_argument('--sid', type=str, help=f'Set network ssid. Defaults to {EZSHARE_NETWORK}')
parser.add_argument('--psk', type=str, help=f'Set network pass phrase. Defaults to {EZSHARE_PASSWORD}')
parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files')
parser.add_argument('--create_missing', action='store_true', help='Create destination path if missing')
args = parser.parse_args()

if args.start_from:
    START_FROM = args.start_from
if args.show_progress:
    SHOW_PROGRESS = args.show_progress
if SHOW_PROGRESS.lower() == 'true':
    SHOW_PROGRESS = True
elif SHOW_PROGRESS.lower() == 'false':
    SHOW_PROGRESS = False

if args.path:
    root_path = args.path
if args.sid:
    EZSHARE_NETWORK = args.sid
if args.psk:
    EZSHARE_PASSWORD = args.psk

if args.overwrite:
    OVERWRITE_EXISTING_FILES = True
if args.create_missing:
    CREATE_MISSING = True

if not isinstance(START_FROM, (int, str)) or (isinstance(START_FROM, str) and START_FROM not in ["ALL", "20230819"]):
    print("Invalid value for START_FROM. It should be an integer, 'ALL', or a date in 'YYYYMMDD' format.")
    sys.exit(1)
    
if SHOW_PROGRESS not in [True, False, 'Verbose']:
    if not SHOW_PROGRESS:
        print (False)
    else:
        print (f'SHOW:{SHOW_PROGRESS}:')
    print("Invalid value for SHOW_PROGRESS. It should be True, False, or 'Verbose'.")
    sys.exit(1)

# #################################################################################################
# Based upon the start_from setting in the config block vs folder name, sends a yes or no to caller
# #################################################################################################
def should_process_folder(folder_name, path):
    start_from_date = START_FROM
    if 'DATALOG' not in path:
        return True
    if start_from_date == "ALL":
        return True
    if isinstance(start_from_date, int):
        start_from_date = datetime.now() - timedelta(days=start_from_date)
    else:
        start_from_date = datetime.strptime(start_from_date, '%Y%m%d')
    folder_date = datetime.strptime(folder_name, '%Y%m%d')
    return folder_date >= start_from_date


# #################################################################################################
# Extracts file names and links to files from directory listing html content
# #################################################################################################
def get_files_and_dirs(url):
    html_content = requests.get(url)
    soup = BeautifulSoup(html_content.text, 'html.parser')
    files = []
    dirs = []

    pre_text = soup.find('pre').decode_contents()
    lines = pre_text.split('\n')

    for line in lines:
        if line.strip():  # Skip empty line
            parts = line.rsplit(maxsplit=2)
            modifypart = parts[0].replace('- ', '-0').replace(': ', ':0')
            regex_pattern = r'\d*-\d*-\d*\s*\d*:\d*:\d*'

            match = re.search(regex_pattern, modifypart)

            if match:
                modifytime = datetime.strptime(match.group(), '%Y-%m-%d   %H:%M:%S').timestamp()
            else:
                modifytime = None

            soupline = BeautifulSoup(line, 'html.parser')
            link = soupline.a
            if link:
                link_text = link.get_text(strip=True)
                # Oscar expects STR.edf, not STR.EDF
                if link_text == "STR.EDF":
                    link_text = "STR.edf"

                link_href = link['href']

                if link_text in ['.', '..', 'back to photo', 'ezshare.cfg', 'JOURNAL.JNL'] or link_text.startswith('.'):
                    continue

                if 'download?file' in link_href:
                    files.append((link_text, urllib.parse.urlparse(link_href).query, modifytime))
                elif 'dir?dir' in link_href:
                    dirs.append((link_text, link_href))

    return files, dirs

# #################################################################################################
# Grab a single file from the SD card. It retries 3x in case the wifi is spotty.
# #################################################################################################
def download_file(url, filename, retries=3, modification_time=None):
    for attempt in range(retries):
        try:
            response = requests.get(url)
            with open(filename, 'wb') as file:
                file.write(response.content)
            if modification_time:
                os.utime(filename, (modification_time, modification_time))
            return  # Successful download, exit the function
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                print(f"Error downloading {url}: {e}. Retrying...")
            else:
                print(f"Failed to download {url} after {retries} attempts. Exception: {e}")
            time.sleep(1) # Wait a second before retrying
    print(f"Failed to download {url} after {retries} attempts.")

# #################################################################################################
# Determine if folders should be included or skipped, create new folders where necessary
# #################################################################################################
def check_dirs(dirs, url, dir_path):
    for dirname, dir_url in dirs:
        if dirname != 'System Volume Information':
            if 'DATALOG' in dir_path and not should_process_folder(dirname, dir_path):
                continue  # Skip this folder

            new_dir_path = os.path.join(dir_path, dirname)
            os.makedirs(new_dir_path, exist_ok=True)
            absolute_dir_url = urllib.parse.urljoin(url, dir_url)
            controller(absolute_dir_url, new_dir_path)

# #################################################################################################
# Determine if files should be downloaded or skipped
# #################################################################################################
def check_files(files,url,dir_path):
    for filename, file_url, file_date in files:
        local_path = os.path.join(dir_path, filename)
        absolute_file_url = urllib.parse.urljoin(url, f'download?{file_url}')

        #Date files, existing and overwrite is off
        if 'DATALOG' in dir_path and os.path.exists(local_path) and not OVERWRITE_EXISTING_FILES:
            if SHOW_PROGRESS == "Verbose":
                print(f'{filename} skipped')
            continue

        download_file(absolute_file_url, local_path, modification_time=file_date)

        if 'DATALOG' in dir_path and os.path.exists(local_path) and OVERWRITE_EXISTING_FILES and SHOW_PROGRESS == 'Verbose':
            print(f'{filename} replaced')
        if SHOW_PROGRESS and 'DATALOG' not in dir_path:
            print(f'{filename} completed')
        elif SHOW_PROGRESS == 'Verbose':
            print(f'{filename} completed (V)')


# #################################################################################################
# Primary control function -
# #################################################################################################

def controller(url, dir_path): 
    files, dirs = get_files_and_dirs(url)

    if not os.path.exists(dir_path) and CREATE_MISSING:
        os.makedirs(dir_path)

    check_files(files, url, dir_path) # Skip file?
    check_dirs(dirs, url, dir_path) #skip folder?

    if 'DATALOG' in dir_path and SHOW_PROGRESS: 
        print(f'{os.path.basename(dir_path)} completed') 

# #################################################################################################
# Wifi Connect - If enabled, check OS, and if MacOS, switch wifi to the EZShare SSID
# #################################################################################################
def connect_to_wifi(ssid, password=None):
    if platform.system() == 'Darwin':
        cmd = f'networksetup -setairportnetwork en0 {ssid}'
        if password:
            cmd += f' {password}'

        result = run(cmd, shell=True, stdout=PIPE, stderr=PIPE)

        if result.returncode == 0:
            if SHOW_PROGRESS:
                print(f"Connected to {ssid} successfully.")
            return True
        else:
            print(f"Failed to connect to {ssid}. Error: {result.stderr.decode('utf-8')}")
            if sys.__stdin__.isatty():
                response = input("Unable to connect automatically, please connect manually and press 'C' to continue or any other key to cancel: ")
                if response.lower() == 'c':
                    return True
                else:
                    return False
            else:
                return False
    elif platform.system() == 'Linux' and platform.freedesktop_os_release()["VERSION_CODENAME"] == 'bookworm':
        if password:
            cmd = f'nmcli d wifi connect "{ssid}" password {password}'
        else:
            cmd = f'nmcli connection up "{ssid}"'

        result = run(cmd, shell=True, capture_output=True, text=True, check=True)

        if result.returncode == 0:
            # Regular expression pattern to match the string after "activated with"
            pattern = r"activated with '([^']*)'"

            # Search for the pattern in the message
            match = re.search(pattern, result.stdout)

            if match:
                global CONNECTION_ID
                # Extract the string after "activated with"
                CONNECTION_ID = match.group(1)

            if SHOW_PROGRESS:
                print(f"Connected to {ssid} successfully.")
            return True
        else:
            print(f"Failed to connect to {ssid}. Error: {result.stderr.decode('utf-8')}")
            if sys.__stdin__.isatty():
                response = input("Unable to connect automatically, please connect manually and press 'C' to continue or any other key to cancel: ")
                if response.lower() == 'c':
                    return True
                else:
                    return False
            else:
                return False
    else:
        print(f'Wifi connection is not supported on this OS.')
        print(f'You appear to be running {platform.system()}.')
        if sys.__stdin__.isatty():
            response = input(f"""Please connect manually and press 'C' and then 'Enter' to continue, or any other key and 'Enter' to cancel: """)
            if response.lower() == 'c':
                return True
            else:
                return False
        else:

            return False

# #################################################################################################
# WIFI Disconnect - Dropping the wifi interface briefly makes MacOS reconnect to the default SSID
# #################################################################################################
def disconnect_from_wifi():
    if platform.system() == 'Darwin':
        # Turn off the Wi-Fi interface (en0)
        run('networksetup -setairportpower en0 off', shell=True)
        # Turn it back on
        run('networksetup -setairportpower en0 on', shell=True)
    elif platform.system() == 'Linux' and platform.freedesktop_os_release()["VERSION_CODENAME"] == 'bookworm':
        global CONNECTION_ID
        if CONNECTION_ID:
            cmd = f'nmcli connection down {CONNECTION_ID}'
            result = run(cmd, shell=True, capture_output=True, text=True, check=True)
# #################################################################################################
# Execution Block
# #################################################################################################
if USE_NETWORK_SWITCHING:
    if SHOW_PROGRESS:
        print(f"Connecting to {EZSHARE_NETWORK}. Waiting a few seconds for connection to establish...")
    if connect_to_wifi(EZSHARE_NETWORK, EZSHARE_PASSWORD):
        time.sleep(CONNECTION_DELAY)
    else:
        print("Connection attempt canceled by user.")
        sys.exit(0) # Exit the entire process
        
controller(root_url, root_path)

if USE_NETWORK_SWITCHING:
    if SHOW_PROGRESS:
        print(f"\nExiting {EZSHARE_NETWORK}. Waiting a few seconds for connection to establish...")
    disconnect_from_wifi()
    time.sleep(CONNECTION_DELAY)

#End