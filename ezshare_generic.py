import os
import requests
import time
import platform
from subprocess import run, PIPE
import urllib.parse
from bs4 import BeautifulSoup

# Configurations
root_path = os.path.join(os.path.expanduser('~'), "Documents", "CPAP_Data", "SD_card")
USE_NETWORK_SWITCHING = True
EZSHARE_NETWORK = "airsense11"
EZSHARE_PASSWORD = "5742104979"
CONNECTION_DELAY = 5
root_url = 'http://192.168.4.1/dir?dir=A:'


def get_files_and_dirs(url):
    html_content = requests.get(url)
    soup = BeautifulSoup(html_content.text, 'html.parser')
    files, dirs = [], []

    for link in soup.find_all('a', href=True):
        link_text = link.text.strip()
        link_href = link['href']
        if link_text not in ['.', '..', 'System Volume Information', 'back to photo']:
            if 'download?file' in link_href:
                files.append((link_text, urllib.parse.urlparse(link_href).query))
            elif 'dir?dir' in link_href:
                dirs.append((link_text, link_href))
    return files, dirs


def download_file(url, filename, retries=3):
    for _ in range(retries):
        try:
            response = requests.get(url)
            with open(filename, 'wb') as file:
                file.write(response.content)
            print(f'{filename} completed (V)')
            return
        except requests.exceptions.RequestException as e:
            print(f"Error downloading {url}: {e}. Retrying...")
            time.sleep(1)


def process_dirs(dirs, url, dir_path):
    for dirname, dir_url in dirs:
        new_dir_path = os.path.join(dir_path, dirname)
        os.makedirs(new_dir_path, exist_ok=True)
        absolute_dir_url = urllib.parse.urljoin(url, dir_url)
        controller(absolute_dir_url, new_dir_path)


def process_files(files, url, dir_path):
    for filename, file_url in files:
        local_path = os.path.join(dir_path, filename)
        absolute_file_url = urllib.parse.urljoin(url, f'download?{file_url}')
        download_file(absolute_file_url, local_path)


def controller(url, dir_path):
    files, dirs = get_files_and_dirs(url)
    process_files(files, url, dir_path)
    process_dirs(dirs, url, dir_path)


# Only for MacOS
def connect_to_wifi(ssid, password=None):
    cmd = f'networksetup -setairportnetwork en0 {ssid} {password or ""}'
    result = run(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    if result.returncode == 0:
        print(f"Connected to {ssid} successfully.")
        return True
    else:
        print(f"Failed to connect to {ssid}. Error: {result.stderr.decode('utf-8')}")
        return False


# Execution Block
if USE_NETWORK_SWITCHING:
    print(f"Connecting to {EZSHARE_NETWORK}. Waiting a few seconds for connection to establish...")
    if connect_to_wifi(EZSHARE_NETWORK, EZSHARE_PASSWORD):
        time.sleep(CONNECTION_DELAY)
    else:
        print("Connection attempt canceled by user.")
        exit(0)

controller(root_url, root_path)
