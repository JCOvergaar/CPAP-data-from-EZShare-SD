#!/usr/bin/env python3
import os
import time
import sys
import platform
import argparse
import subprocess
import urllib.parse
import datetime
import configparser
import re
import logging
import textwrap
import shutil
import tempfile

import bs4
import requests
from requests import adapters
from urllib3.util import retry


class EZShare():
    """Class to handle the EZShare SD card download process

    Attributes:
        path (str): Local path to store the downloaded files
        url (str): URL of the EZShare SD card
        start_time (datetime.datetime): Date to start syncing from
        show_progress (bool): If progress should be shown
        verbose (bool): If verbose output should be shown
        overwrite (bool): If existing files should be overwritten
        create_missing (bool): If missing directories should be created
        sid (str): SSID of the network to connect to
        psk (str): Passphrase of the network to connect to
        connection_id (str): Connection ID of the network connection
        log (logging.Logger): Logger object for the class
        session (requests.Session): Session object for the requests library
        ignore (list[str]): List of files to ignore
        retries (retry.Retry): Retry object for the requests library
    
    Methods:
        connect_to_wifi: Connect to the EZShare network
        run: Entry point for the EZShare class
        recursive_traversal: Recursivly traverse the file system
        list_dir: List files and directories in the current directory
        check_files: Determine if files should be downloaded or skipped and downloads the correct files
        download_file: Grab a single file from the SD card
        check_dirs: Determine if folders should be included or skipped, create new folders where necessary
        should_process_folder: Checks that datalog files are within sync range
        disconnect_from_wifi: Disconnect from the EZShare network
    """

    def __init__(self, path, url, start_time, show_progress, verbose, overwrite, create_missing, ssid, psk, 
                 ignore, retries=5, connection_delay=5):
        """Class constructor for the EZShare class
        Args:
            path (str): Local path to store the downloaded files
            url (str): URL of the EZShare SD card
            start_time (datetime.datetime): Date to start syncing from
            show_progress (bool): If progress should be shown
            verbose (bool): If verbose output should be shown
            overwrite (bool): If existing files should be overwritten
            create_missing (bool): If missing directories should be created
            ssid (str): SSID of the network to connect to
            psk (str): Passphrase of the network to connect to
            ignore (list[str]): List of files to ignore
            retries (int): Number of retries for failed downloads, defaults to 5
            connection_delay (int): Delay in seconds after connecting to the network, defaults to 5
        """
        if verbose:
            log_level = logging.DEBUG
        elif show_progress:
            log_level = logging.INFO
        else:
            log_level = logging.WARN
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=log_level)
        self.path = path
        self.url = url
        self.start_time = start_time
        self.overwrite = overwrite
        self.create_missing = create_missing
        self.ssid = ssid
        self.psk = psk
        self.connection_id = None
        self.existing_connection_id = None
        self.log = logging.getLogger("EZShare")
        self.platform_system = platform.system()

        if self.ssid:
            self.log.info(f"Connecting to {self.ssid}. Waiting a few seconds for connection to establish...")
            try:
                self.connect_to_wifi()
            except OSError as e:
                self.log.warning(f"Failed to connect to {self.ssid}. Error: {e}")
                if sys.__stdin__.isatty():
                    response = input("Unable to connect automatically, please connect manually and press 'C' to continue or any other key to cancel: ")
                    if response.lower() == 'c':
                        return True
                    else:
                        sys.exit("Connection attempt canceled by user.")

        self.session = requests.Session()
        self.ignore = ['.', '..', 'back to photo'] + ignore
        self.retries = retries
        self.retry = retry.Retry(total=retries, backoff_factor=0.25)
        self.session.mount('http://', adapters.HTTPAdapter(max_retries=self.retry))

    @property
    def wifi_profile(self):
        if self.ssid and self.psk:
            return textwrap.dedent(f"""\
                <?xml version="1.0"?>
                <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
                    <name>{self.ssid}</name>
                    <SSIDConfig>
                        <SSID>
                            <name>{self.ssid}</name>
                        </SSID>
                    </SSIDConfig>
                    <connectionType>ESS</connectionType>
                    <connectionMode>manual</connectionMode>
                    <MSM>
                        <security>
                            <authEncryption>
                                <authentication>WPA2PSK</authentication>
                                <encryption>AES</encryption>
                                <useOneX>false</useOneX>
                            </authEncryption>
                            <sharedKey>
                                <keyType>passPhrase</keyType>
                                <protected>false</protected>
                                <keyMaterial>{self.psk}</keyMaterial>
                            </sharedKey>
                        </security>
                    </MSM>
                    <MacRandomization xmlns="http://www.microsoft.com/networking/WLAN/profile/v3">
                        <enableRandomization>false</enableRandomization>
                    </MacRandomization>
                </WLANProfile>
            """)
        elif self.ssid:
            return textwrap.dedent(f"""\
                <?xml version="1.0" encoding="US-ASCII"?>
                <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
                    <name>{self.ssid}</name>
                    <SSIDConfig>
                        <SSID>
                            <name>{self.ssid}</name>
                        </SSID>
                    </SSIDConfig>
                    <connectionType>ESS</connectionType>
                    <connectionMode>auto</connectionMode>
                    <MSM>
                        <security>
                            <authEncryption>
                                <authentication>open</authentication>
                                <encryption>none</encryption>
                                <useOneX>false</useOneX>
                            </authEncryption>
                        </security>
                    </MSM>
                    <MacRandomization xmlns="http://www.microsoft.com/networking/WLAN/profile/v3">
                        <enableRandomization>false</enableRandomization>
                    </MacRandomization>
                </WLANProfile>
            """)
        else:
            return None

    def connect_to_wifi(self):
        """Wifi Connect - Connect to EZShare Wi-Fi network
        
        Raises:
            OSError: When automatically connecting to WiFi is not supported on
        the system or it fails to connect
        """
        if self.platform_system == 'Darwin':
            cmd = f'networksetup -setairportnetwork en0 "{self.ssid}"'
            if self.psk:
                cmd += f' {self.psk}'
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                raise OSError(f"Error connecting to {self.ssid}. Return code: {e.returncode}, error: {e.stderr}")
            
        elif self.platform_system == 'Linux' and shutil.which('nmcli'):
            if self.psk:
               cmd = f'nmcli d wifi connect "{self.ssid}" password {self.psk}'
            else: 
                cmd = f'nmcli connection up "{self.ssid}"'

            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                raise OSError(f"Error connecting to {self.ssid}. Return code: {e.returncode}, error: {e.stderr}")

            # Regular expression pattern to match the string after "activated with"
            pattern = r"activated with '([^']*)'"

            # Search for the pattern in the message
            match = re.search(pattern, result.stdout)

            if match:
                # Extract the string after "activated with"
                self.connection_id = match.group(1)


        elif self.platform_system == "Windows":
            existing_profile_command = 'netsh wlan show interfaces'
            try:
                existing_profile_result = subprocess.run(existing_profile_command, shell=True, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                raise OSError(f"Error checking network existing network profile. Return code: {e.returncode}, error: {e.stderr}")
            for line in existing_profile_result.stdout.split('\n'):
                if line.strip().startswith('Profile'):
                    self.existing_connection_id = line.split(':')[1].strip()
                    break

            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as wifi_profile_file:
                wifi_profile_file.write(self.wifi_profile)
            profile_cmd = f'netsh wlan add profile filename={wifi_profile_file.name}'
            try:
                profile_result = subprocess.run(profile_cmd, shell=True, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                raise OSError(f"Error creating network profile for {self.ssid}. Return code: {e.returncode}, error: {e.stderr}")
            finally:
                os.remove(wifi_profile_file.name)
            self.connection_id = self.ssid
            self.log.info(f"Created profile for {self.ssid} successfully.")

            connect_cmd = f'netsh wlan connect name="{self.connection_id}"'
            try:
                connect_result = subprocess.run(connect_cmd, shell=True, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                raise OSError(f"Error connecting to {self.ssid}. Return code: {e.returncode}, error: {e.stderr}")
        else:
            raise OSError('Automatic Wi-Fi connection is not supported on this system.')
            
        self.log.info(f"Connected to {self.ssid} successfully.")

            
    def run(self):
        """Entry point for the EZShare class

        Raises:
            SystemExit: When the path does not exist and create_missing is False
        """
        if not os.path.exists(self.path):
            if self.create_missing:
                os.makedirs(self.path)
            else:
                sys.exit(f"Path {self.path} does not exist and create_missing is off. Unable to continue.")

        self.recursive_traversal(self.url, self.path)
        self.disconnect_from_wifi()

    def recursive_traversal(self, url, dir_path):
        """Recursivly traverse the file system

        Args:
            url (str): URL of the directory to traverse
            dir_path (str): Local path of the directory to traverse
        """
        files, dirs = self.list_dir(url)
        self.check_files(files, url, dir_path)
        self.check_dirs(dirs, url, dir_path)

        if 'DATALOG' in dir_path:
            self.log.info(f'{os.path.basename(dir_path)} completed') 

    def list_dir(self, url):
        """lists names and links to files and directories in the referenced directory
        
        Args:
            url (str): URL to the directory to be listed
        
        Returns:
            Tuple[list,list]: 
                [0] (list[Tuple[str,str,float]]): A list containing a tuple for each file in the current directory
                    [0] (str): Name of the file
                    [1] (str): URL component to the file
                    [3] (float): Modification time of the file as a POSIX timestamp
                [1] (list[Tuple[str,str]]): A list containing a tuple for each directory in the directory in the current directory
                    [0] (str): Name of the directory
                    [1] (str): URL component to the directory
        """
        html_content = requests.get(url)
        soup = bs4.BeautifulSoup(html_content.text, 'html.parser')
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
                    file_ts = datetime.datetime.strptime(match.group(), '%Y-%m-%d   %H:%M:%S').timestamp()
                else:
                    file_ts = None

                soupline = bs4.BeautifulSoup(line, 'html.parser')
                link = soupline.a
                if link:
                    link_text = link.get_text(strip=True)
                    # Oscar expects STR.edf, not STR.EDF
                    if link_text == "STR.EDF":
                        link_text = "STR.edf"

                    link_href = link['href']

                    if link_text in self.ignore or link_text.startswith('.'):
                        continue

                    if 'download?file' in link_href:
                        files.append((link_text, urllib.parse.urlparse(link_href).query, file_ts))
                    elif 'dir?dir' in link_href:
                        dirs.append((link_text, link_href))

        return files, dirs

    def check_files(self, files, url, dir_path):
        """Determine if files should be downloaded or skipped and downloads the correct files

        Args:
            files (list[Tuple[str,str,float]]): A list containing a tuple for each file in the current directory
                    [0] (str): Name of the file
                    [1] (str): URL component to the file
                    [3] (float): Modification time of the file in as a POSIX timestamp
            url (str): URL to the current directory
            dir_path (str): Local path to curent directory
        """
        for filename, file_url, file_ts in files:
            local_path = os.path.join(dir_path, filename)
            local_exists = os.path.exists(local_path)
            absolute_file_url = urllib.parse.urljoin(url, f'download?{file_url}')

            #Date files, existing and overwrite is off
            if 'DATALOG' in dir_path and local_exists and not self.overwrite:
                self.log.debug(f'{filename} already exists... skipped')
                continue

            self.download_file(absolute_file_url, local_path, file_ts=file_ts)

            if 'DATALOG' in dir_path and local_exists and self.overwrite:
                self.log.info(f'{filename} replaced')
            if 'DATALOG' not in dir_path:
                self.log.info(f'{filename} completed')
            else:
                self.log.debug(f'{filename} completed')

    def download_file(self, url, filename, file_ts=None):
        """Grab a single file from the SD card.
    
        Args:
            url (str): url to the file to download
            filename (str): Name of the file
            file_ts (float): Modification time of the file in as a POSIX timestamp, default None
        
        Raises:
            SystemExit: When the download fails
        """
        mtime = 0
        if os.path.isfile(filename):
            mtime = os.path.getmtime(filename)
        if self.overwrite or mtime <= file_ts:
            self.log.debug(f'Downloading {filename} from {url}')
            try:
                response = requests.get(url)
            except requests.exceptions.RequestException as e:
                sys.exit(f'Failed to download {filename} from {url}. Exception: {e}')
            with open(filename, 'wb') as file:
                file.write(response.content)
            self.log.debug(f'{filename} written to disk')
            if file_ts:
                os.utime(filename, (file_ts, file_ts))
        else:
            self.log.warning(f"File {filename} already exists and is newer than the file on the SD card. Skipping because overwrite is off.")


    def check_dirs(self, dirs, url, dir_path):
        """Determine if folders should be included or skipped, create new folders where necessary

        Args:
            dirs (list[Tuple[str,str]]): A list of tuples for each directory in the current directory
                [0] (str): Name of the directory
                [1] (str): URL component to the directory
            url (str): URL to current directory
            dir_path (str): Local path to current directory
        """
        for dirname, dir_url in dirs:
            if dirname != 'System Volume Information':
                if 'DATALOG' in dir_path and not self.should_process_folder(dirname, dir_path):
                    continue  # Skip this folder
                new_dir_path = os.path.join(dir_path, dirname)
                os.makedirs(new_dir_path, exist_ok=True)
                absolute_dir_url = urllib.parse.urljoin(url, dir_url)
                self.recursive_traversal(absolute_dir_url, new_dir_path)

    def should_process_folder(self, folder_name, path):
        """Checks that datalog files are within sync range
    
        Args:
            folder_name (str): name of the folder
            path (str): path of the folder
        
        Returns:
            bool: If the folder shouldbe processed returns True otherwise returs False
        """
        if 'DATALOG' not in path:
            return True
        if not self.start_time:
            return True
        folder_time = datetime.datetime.strptime(folder_name, '%Y%m%d')
        return folder_time >= self.start_time

    def disconnect_from_wifi(self):
        """WIFI Disconnect - Dropping the wifi interface briefly makes MacOS reconnect to the default SSID
        """
        if self.platform_system == 'Darwin':
            # Turn off the Wi-Fi interface (en0)
            subprocess.run('networksetup -setairportpower en0 off', shell=True)
            # Turn it back on
            subprocess.run('networksetup -setairportpower en0 on', shell=True)
        elif self.platform_system == 'Linux' and shutil.which('nmcli'):
            if self.connection_id:
                cmd = f'nmcli connection down {self.connection_id}'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)

        elif self.platform_system == 'Windows':
            if self.connection_id:
                profile_cmd = f'netsh wlan delete profile {self.connection_id}'
                try:
                    profile_result = subprocess.run(profile_cmd, shell=True, capture_output=True, text=True, check=True)
                except subprocess.CalledProcessError as e:
                    raise OSError(f"Error removing network profile for {self.ssid}. Return code: {e.returncode}, error: {e.stderr}")
            if self.existing_connection_id:
                connect_cmd = f'netsh wlan connect name="{self.existing_connection_id}"'
                try:
                    connect_result = subprocess.run(connect_cmd, shell=True, capture_output=True, text=True, check=True)
                except subprocess.CalledProcessError as e:
                    raise OSError(f"Error reconnecting to original network profile: {self.existing_connection_id}. Return code: {e.returncode}, error: {e.stderr}")


def main():
    """Entry point when used as a CLI tool
    """
    CONNECTION_DELAY = 5
    APP_NAME = os.path.basename(__file__).split('.')[0]
    CONFIG_FILES = [
        f'{APP_NAME}.ini',  # In the same directory as the script
        'config.ini',
        os.path.join(os.path.expanduser('~'), '.config', f'{APP_NAME}.ini'),
        os.path.join(os.path.expanduser('~'), '.config', f'{APP_NAME}', f'{APP_NAME}.ini'),
        os.path.join(os.path.expanduser('~'), '.config', f'{APP_NAME}', 'config.ini')
    ]

    # Iterate through possible paths and use the first one that exists
    config_path = None
    for config_file in CONFIG_FILES:
        if os.path.exists(config_file):
            config_path = config_file
            break
    
    config = configparser.ConfigParser()
    # If config file is found, read its contents
    if config_path:
        # Create a configparser object and read the config file
        config.read(config_path)

    # Set defaults using the config file or the hardcoded defaults
    path = config.get(f'{APP_NAME}', 'path', fallback=os.path.join(os.path.expanduser('~'), "Documents", "CPAP_Data", "SD_card"))
    url = config.get(f'{APP_NAME}', 'url', fallback='http://192.168.4.1/dir?dir=A:')
    start_from = config.get(f'{APP_NAME}', 'start_from', fallback=None)
    day_count = config.getint(f'{APP_NAME}', 'day_count', fallback=None)
    show_progress = config.getboolean(f'{APP_NAME}', 'show_progress', fallback=False)
    verbose = config.getboolean(f'{APP_NAME}', 'verbose', fallback=False)
    overwrite = config.getboolean(f'{APP_NAME}', 'overwrite', fallback=False)
    create_missing = config.getboolean(f'{APP_NAME}', 'create_missing', fallback=True)
    ignore = config.get(f'{APP_NAME}', 'ignore', fallback='JOURNAL.JNL,ezshare.cfg')
    ssid = config.get(f'{APP_NAME}', 'ssid', fallback=None)
    psk = config.get(f'{APP_NAME}', 'psk', fallback=None)
    retries = config.getint(f'{APP_NAME}', 'retries', fallback=5)

    # Parse command line arguments
    description = textwrap.dedent(f"""\
    {APP_NAME} wirelessly syncs Resmed CPAP/BiPAP treatment data logs stored on a EZShare WiFi SD card wirelessly to your local device
    
    A configuration file can be used to set defaults
    See documentation for confiuration file options, default locations and precidence 
    Command line arguments will override the configuration file
    """)
    epilog = textwrap.dedent(f"""\
    Example:
        {APP_NAME} --ssid ezshare --psk 88888888 -v
    """)
    parser = argparse.ArgumentParser(prog=APP_NAME, description=description, epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--path', type=str, help=f'set destination path, defaults to {path}')
    parser.add_argument('--url', type=str, help=f'set source URL, Defaults to {url}')
    parser.add_argument('--start_from', type=str, help=f'start from date in YYYYMMDD format, deaults to {start_from}; this will override day_count if set')
    parser.add_argument('--day_count', '-n', type=int, help=f'number of days to sync, defaults to {day_count}; if both start_from and day_count are unset all files will be synced')
    parser.add_argument('--show_progress', action='store_true', help=f'show progress, defaults to {show_progress}')
    parser.add_argument('--verbose', '-v', action='store_true', help=f'verbose output, defaults to {verbose}')
    parser.add_argument('--overwrite', action='store_true', help=f'overwrite existing files, defaults to {overwrite}')
    parser.add_argument('--create_missing', action='store_true', help=f'create destination path if missing, defaults to {create_missing}')
    parser.add_argument('--ignore', type=str, help=f'case insensitive comma separated list of files to ignore, defaults to {ignore}')
    parser.add_argument('--ssid', type=str, help=f'set network SSID; if set automaticconnection to the WiFi network will be attempted, defaults to {ssid}')
    parser.add_argument('--psk', type=str, help=f'set network pass phrase, defaults to {psk}')
    parser.add_argument('--retries', type=int, help=f'set number of retries for failed downloads, defaults to {retries}')
    args = parser.parse_args()

    if args.path:
        path = args.path
    if args.url:
        url = args.url
    if args.start_from:
        start_from = args.start_from
    if args.day_count:
        day_count = args.day_count
    if args.show_progress:
        show_progress = True
    if args.verbose:
        verbose = True
    if args.overwrite:
        overwrite = True
    if args.create_missing:
        create_missing = True
    if args.ignore:
        ignore = args.ignore
    if args.ssid:
        ssid = args.ssid
    if args.psk:
        psk = args.psk
    if args.retries:
        retries = args.retries
    
    ignore_list = ignore.split(',')

    if start_from:
        try:
            start_ts = datetime.datetime.strptime(start_from, '%Y%m%d')
        except ValueError as e:
            raise ValueError(f'Invalid date format provided in \'start_from\'. Please use YYYYMMDD. Error: {e}')
    elif day_count:
        start_ts = datetime.datetime.now() - datetime.timedelta(days=day_count)
    else:
        start_ts = None
            
    ezshare = EZShare(path, url, start_ts, show_progress, verbose, overwrite, 
                      create_missing, ssid, psk, ignore_list, retries, CONNECTION_DELAY)
    
    ezshare.run()


if __name__ == '__main__':
    main()