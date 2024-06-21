#!/usr/bin/env python3
import os
import pathlib
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
import tqdm
from urllib3.util import retry


APP_NAME = pathlib.Path(__file__).stem
VERSION = 'v1.0.0-beta'
logger = logging.getLogger(APP_NAME)


class EZShare():
    """
    Class to handle the EZShare SD card download process

    Attributes:
        path (str): Local path to store the downloaded files
        url (str): URL of the EZShare SD card
        start_time (datetime.datetime): Date to start syncing from
        show_progress (bool): Print progress
        overwrite (bool): Overwrite existing files
        keep_old (bool): Do not overwrite even if newer version is available
        ssid (str): SSID of the network to connect to
        psk (str): Passphrase of the network to connect to
        connection_id (str): Connection ID of the network connection
        existing_connection_id (str): Connection ID of the existing network connection
        interface_name (str): Name of the Wi-Fi interface
        platform_system (str): platform.system()
        session (requests.Session): Session object for the requests library
        ignore (list[str]): List of files to ignore
        retries (retry.Retry): Retry object for the requests library
        connection_delay (int): Delay in seconds after connecting to the network
    
    Methods:
        print: Check if messages should be printed and prints
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

    def __init__(self, path, url, start_time, show_progress, verbose,
                 overwrite, keep_old, ssid, psk, ignore, retries=5,
                 connection_delay=5, debug=False):
        """
        Class constructor for the EZShare class

        Args:
            path (str): Local path to store the downloaded files
            url (str): URL of the EZShare SD card
            start_time (datetime.datetime): Date to start syncing from
            show_progress (bool): Print progress
            verbose (bool): If verbose output should be shown
            overwrite (bool): Overwrite existing files
            keep_old (bool): Do not overwrite even if newer version is available
            ssid (str): SSID of the network to connect to
            psk (str): Passphrase of the network to connect to
            ignore (list[str]): List of files to ignore
            retries (int): Number of retries for failed downloads, defaults to 5
            connection_delay (int): Delay in seconds after connecting to the network, defaults to 5
            debug (bool): Sets log level to DEBUG, defaults to False
        """
        if debug:
            log_level = logging.DEBUG
        elif verbose:
            log_level = logging.INFO
        else:
            log_level = logging.WARN
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            level=log_level)
        self.path = pathlib.Path(path).expanduser()
        self.url = url
        self.start_time = start_time
        self.show_progress = show_progress
        self.overwrite = overwrite
        self.keep_old = keep_old
        self.ssid = ssid
        self.psk = psk
        self.connection_id = None
        self.existing_connection_id = None
        self.platform_system = platform.system()
        self.interface_name = None
        self.connected = False
        self.session = requests.Session()
        self.ignore = ['.', '..', 'back to photo'] + ignore
        self.retries = retries
        self.retry = retry.Retry(total=retries, backoff_factor=0.25)
        self.connection_delay = connection_delay
        self.session.mount('http://', adapters.HTTPAdapter(max_retries=self.retry))

    @property
    def wifi_profile(self):
        """
        str: Windows WiFi profile formatted in XML for the specified SSID and password
        """
        if self.ssid and self.psk:
            return textwrap.dedent(f"""\
                <?xml version="1.0"?>
                <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
                    <name>{self.ssid}_script_profile</name>
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
                    <name>{self.ssid}_script_profile</name>
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

    def print(self, message):
        """
        Checks if progress should be shown and if so prints the message

        Args:
            message (str): message to print
        """
        if self.show_progress:
            print(message)

    def connect_to_wifi(self):
        """
        Wifi Connect - Connect to EZShare Wi-Fi network specified in ssid
        
        Raises:
            RuntimeError: When automatically connecting to WiFi is not supported on
        the system or it fails to connect
        """
        if self.platform_system == 'Darwin':
            self.connect_to_wifi_macos()
        elif self.platform_system == 'Linux' and self.has_network_manager():
            self.connect_to_wifi_linux()
        elif self.platform_system == 'Windows':
            self.connect_to_wifi_windows()
        else:
            raise RuntimeError('Automatic Wi-Fi connection is not supported on this system.')

        self.print(f'Connected to {self.ssid} successfully.')

    def connect_to_wifi_macos(self):
        """
        Wifi Connect - macOS logic for WiFi 
        
        Raises:
            RuntimeError: When automatically connecting to WiFi fails
        """
        get_interface_cmd = 'networksetup -listallhardwareports'
        try:
            get_interface_result = subprocess.run(get_interface_cmd,
                                                    shell=True,
                                                    capture_output=True,
                                                    text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Error getting Wi-Fi interface name. Return code: {e.returncode}, error: {e.stderr}') from e

        interface_lines = get_interface_result.stdout.split('\n')
        for index, line in enumerate(interface_lines):
            if 'Wi-Fi' in line:
                self.interface_name = interface_lines[index + 1].split(':')[1].strip()
                break
        if not self.interface_name:
            raise RuntimeError('No Wi-Fi interface found')
   
        connect_cmd = f'networksetup -setairportnetwork {self.interface_name} "{self.ssid}"'
        if self.psk:
            connect_cmd += f' "{self.psk}"'
        try:
            connect_result = subprocess.run(connect_cmd, shell=True,
                                            capture_output=True,
                                            text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Error connecting to {self.ssid}. Return code: {e.returncode}, error: {e.stderr}') from e
        if connect_result.stdout.startswith('Failed to join network'):
            raise RuntimeError(f'Error connecting to {self.ssid}. Error: {connect_result.stdout}')
        self.connection_id = self.ssid
        self.connected = True

    def connect_to_wifi_linux(self):
        """
        Wifi Connect - Linux logic for WiFi 
        
        Raises:
            RuntimeError: When automatically connecting to WiFi fails
        """
        if self.psk:
            connect_cmd = f'nmcli d wifi connect "{self.ssid}" password "{self.psk}"'
        else:
            connect_cmd = f'nmcli connection up "{self.ssid}"'
        try:
            connect_result = subprocess.run(connect_cmd, shell=True,
                                            capture_output=True, text=True,
                                            check=True)
        except subprocess.CalledProcessError as e:
            self.connection_id = self.ssid
            raise RuntimeError(f'Error connecting to {self.ssid}. Return code: {e.returncode}, error: {e.stderr}') from e

        # Regular expression pattern to match the string after "activated with"
        pattern = r"activated with '([^']*)'"

        # Search for the pattern in the message
        match = re.search(pattern, connect_result.stdout)

        if match:
            # Extract the string after "activated with"
            self.connection_id = match.group(1)
            self.connected = True

    def connect_to_wifi_windows(self):
        """
        Wifi Connect - Windows logic for WiFi 
        
        Raises:
            RuntimeError: When automatically connecting to WiFi fails
        """
        existing_profile_cmd = 'netsh wlan show interfaces'
        try:
            existing_profile_result = subprocess.run(existing_profile_cmd,
                                                        shell=True,
                                                        capture_output=True,
                                                        text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Error checking network existing network profile. Return code: {e.returncode}, error: {e.stderr}') from e
        for line in existing_profile_result.stdout.split('\n'):
            if line.strip().startswith('Profile'):
                self.existing_connection_id = line.split(':')[1].strip()
                break

        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml',
                                            delete=False) as wifi_profile_file:
            wifi_profile_file.write(self.wifi_profile)
            temp_profile_filename = wifi_profile_file.name
        profile_cmd = f'netsh wlan add profile filename={wifi_profile_file.name}'
        try:
            subprocess.run(profile_cmd, shell=True, capture_output=True,
                            text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Error creating network profile for {self.ssid}. Return code: {e.returncode}, error: {e.stderr}') from e
        finally:
            os.remove(temp_profile_filename)
        connection_id = f'{self.ssid}_script_profile'
        connect_cmd = f'netsh wlan connect name="{connection_id}"'
        try:
            subprocess.run(connect_cmd, shell=True, capture_output=True,
                            text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Error connecting to {self.ssid}. Return code: {e.returncode}, error: {e.stderr}') from e
        self.connection_id = connection_id

    def wifi_connected(self):
        """
        Checks if WiFi is connected

        Returns:
            bool: True if connected to specified WiFi network, False if not
        """
        if self.connected:
            return True
        if self.platform_system == 'Windows':
            existing_profile_cmd = 'netsh wlan show interfaces'
            try:
                current_profile_result = subprocess.run(existing_profile_cmd,
                                                            shell=True,
                                                            capture_output=True,
                                                            text=True, check=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f'Error checking network existing network profile. Return code: {e.returncode}, error: {e.stderr}') from e
            for line in current_profile_result.stdout.split('\n'):
                if line.strip().startswith('Profile'):
                    if line.split(':')[1].strip() == self.connection_id:
                        self.connected = True
                        return True
        else:
            return False

    def has_network_manager(self):
        """
        Checks if nmcli is present on the system and if it can manage the WiFi network

        Returns:
            bool: True if NetworkManager can manage WiFi, False if ncmcli is 
            missing, NetworkManager is not active, wifi device is not present,
            wifi devicis not in a connected or disconnected status, or nmcli
            is unable to list networks available on the wifi device
        """
        if shutil.which('nmcli') is None:
            return False

        network_manager_is_active_cmd = 'systemctl is-active --quiet NetworkManager'
        try:
            subprocess.run(network_manager_is_active_cmd, shell=True,
                           capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError:
            return False

        get_device_cmd = 'nmcli device status'
        get_device_result = subprocess.run(get_device_cmd, shell=True,
                                           capture_output=True, text=True,
                                           check=True)
        for line in get_device_result.stdout.split('\n'):
            if 'wifi' in line and 'wifi-p2p' not in line:
                self.interface_name = line.split()[0]
                break
        if self.interface_name is None:
            return False

        managed_cmd = f'nmcli device show "{self.interface_name}"'
        managed_result = subprocess.run(managed_cmd, shell=True,
                                        capture_output=True, text=True,
                                        check=True)
        for line in managed_result.stdout.split('\n'):
            if line.startswith('GENERAL.STATE:'):
                if 'connected' not in line:
                    self.interface_name = None
                    return False
                break

        nmcli_works_cmd = f'nmcli device wifi list ifname "{self.interface_name}"'
        try:
            subprocess.run(nmcli_works_cmd, shell=True, capture_output=True,
                           text=True, check=True)
        except subprocess.CalledProcessError:
            self.interface_name = None
            return False

        return True

    def run(self):
        """
        Entry point for the EZShare class

        Raises:
            SystemExit: When the path does not exist and create_missing is False
        """
        if self.ssid:
            self.print(f'Connecting to {self.ssid}.')
            try:
                self.connect_to_wifi()
            except RuntimeError as e:
                logger.warning('Failed to connect to %s. Error: %s', self.ssid, str(e))
            else:
                self.print('Waiting a few seconds for connection to establish...')
                time.sleep(self.connection_delay)

        if not self.wifi_connected():
            if sys.__stdin__.isatty():
                response = input('Unable to connect automatically, please connect manually and press "C" to continue or any other key to cancel: ')
                if response.lower() != 'c':
                    sys.exit('Cancled')
            else:
                logger.warning('No Wi-Fi connection was estableshed. Attempting to continue...')

        try:
            self.path.mkdir(parents=True, exist_ok=True)
        except FileExistsError:
            sys.exit(f'Path {self.path} already exists and is a file. Unable to continue.')

        self.recursive_traversal(self.url, self.path)

    def recursive_traversal(self, url, dir_path):
        """
        Recursivly traverse the file system

        Args:
            url (str): URL of the directory to traverse
            dir_path (pathlib.Path): Local path of the directory to traverse
        """
        files, dirs = self.list_dir(url)
        self.check_files(files, url, dir_path)
        self.check_dirs(dirs, url, dir_path)

    def list_dir(self, url):
        """
        Lists names and links to files and directories in the referenced directory
        
        Args:
            url (str): URL to the directory to be listed
        
        Returns:
            Tuple[list,list]: 
                [0] (list[Tuple[str,str,float]]): A list containing a tuple for
                each file in the current directory
                    [0] (str): Name of the file
                    [1] (str): URL component to the file
                    [2] (float): Modification time of the file as a POSIX timestamp
                [1] (list[Tuple[str,str]]): A list containing a tuple for each 
                directory in the directory in the current directory
                    [0] (str): Name of the directory
                    [1] (str): URL component to the directory
        """
        html_content = requests.get(url, timeout=5)
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
                    file_ts = datetime.datetime.strptime(match.group(),
                                                         '%Y-%m-%d   %H:%M:%S').timestamp()
                else:
                    file_ts = 0

                soupline = bs4.BeautifulSoup(line, 'html.parser')
                link = soupline.a
                if link:
                    link_text = link.get_text(strip=True)
                    # Oscar expects STR.edf, not STR.EDF
                    if link_text == 'STR.EDF':
                        link_text = 'STR.edf'

                    link_href = link['href']

                    if link_text in self.ignore or link_text.startswith('.'):
                        continue
                    parsed_url = urllib.parse.urlparse(link_href)
                    if parsed_url.path.endswith('download'):
                        files.append((link_text, parsed_url.query, file_ts))
                    elif parsed_url.path.endswith('dir'):
                        dirs.append((link_text, link_href))
        return files, dirs

    def check_files(self, files, url, dir_path: pathlib.Path):
        """
        Determine if files should be downloaded or skipped and downloads the 
        correct files

        Args:
            files (list[Tuple[str,str,float]]): A list containing a tuple for 
            each file in the current directory
                    [0] (str): Name of the file
                    [1] (str): URL component to the file
                    [2] (float): Modification time of the file in as a POSIX
                    timestamp
            url (str): URL to the current directory
            dir_path (pathlib.Path): Local path to curent directory
        """
        for filename, file_url, file_ts in files:
            local_path = dir_path / filename
            absolute_file_url = urllib.parse.urljoin(url, f'download?{file_url}')
            self.download_file(absolute_file_url, local_path, file_ts=file_ts)

    def download_file(self, url, file_path: pathlib.Path, file_ts=None):
        """
        Grab a single file from the SD card.
    
        Args:
            url (str): url to the file to download
            file_path (pathlib.Path): Path of the file
            file_ts (float): Modification time of the file in as a POSIX 
            timestamp, default None
        
        Raises:
            SystemExit: When the download fails
        """
        mtime = 0
        already_exists = file_path.is_file()
        if already_exists:
            mtime = file_path.stat().st_mtime
        if (self.overwrite or mtime < file_ts) and not (already_exists and self.keep_old):
            logger.debug('Downloading %s from %s', str(file_path), url)
            response = self.session.get(url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024

            with tqdm.tqdm(total=total_size, unit='B', unit_scale=True,
                           desc=file_path.name,
                           disable=not self.show_progress) as progress_bar:
                with file_path.open('wb') as fp:
                    for data in response.iter_content(block_size):
                        progress_bar.update(len(data))
                        fp.write(data)
            if already_exists:
                if mtime < file_ts:
                    logger.info('file at %s is newer than %s, overwritten', url, str(file_path))
                else:
                    logger.info('%s overwritten', str(file_path))
            else:
                logger.info('%s written', str(file_path))
            if file_ts:
                os.utime(file_path, (file_ts, file_ts))
        else:
            logger.info('File %s already exists and has not been updated. Skipping because overwrite is off.',
                        str(file_path))


    def check_dirs(self, dirs, url, dir_path: pathlib.Path):
        """
        Determine if folders should be included or skipped, create new folders
        where necessary

        Args:
            dirs (list[Tuple[str,str]]): A list of tuples for each directory in
            the current directory
                [0] (str): Name of the directory
                [1] (str): URL component to the directory
            url (str): URL to current directory
            dir_path (pathlib.Path): Local path to current directory
        """
        for dirname, dir_url in dirs:
            new_dir_path = dir_path / dirname
            new_dir_path.mkdir(exist_ok=True)
            absolute_dir_url = urllib.parse.urljoin(url, dir_url)
            self.recursive_traversal(absolute_dir_url, new_dir_path)

    def disconnect_from_wifi(self):
        """
        Disconnects from the WiFi specified by self.ssid and attempts to 
        reconnect to the original network if possible

        Raises:
            RuntimeError: When an error occurs disconnecting from the Wi-Fi 
        network or reconnecting to the existing network
        """
        if self.platform_system == 'Darwin':
            if self.connection_id:
                self.print(f'Disconnecting from {self.connection_id}...')

                self.print(f'Removing profile for {self.connection_id}...')
                profile_cmd = f'networksetup -removepreferredwirelessnetwork {self.interface_name} "{self.connection_id}"'
                try:
                    subprocess.run(profile_cmd, shell=True,
                                   capture_output=True, text=True, check=True)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f'Error removing network profile for {self.ssid}. Return code: {e.returncode}, error: {e.stderr}') from e
            try:
                # Turn off the Wi-Fi interface
                subprocess.run(f'networksetup -setairportpower {self.interface_name} off',
                               shell=True, check=True)
                logger.info('Wi-Fi interface %s turned off',
                            self.interface_name)
                # Turn it back on
                subprocess.run(f'networksetup -setairportpower {self.interface_name} on',
                               shell=True, check=True)
                logger.info('Wi-Fi interface %s turned on',
                            self.interface_name)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f'Error toggling Wi-Fi interface power. Return code: {e.returncode}, error: {e.stderr}') from e

        elif self.platform_system == 'Linux' and self.interface_name is not None:
            if self.connected:
                self.print(f'Disconnecting from {self.ssid}')
                disconnect_cmd = f'nmcli connection down {self.connection_id}'
                try:
                    subprocess.run(disconnect_cmd, shell=True,
                                   capture_output=True, text=True, check=True)
                    logger.info('Successfully disconnected from %s', self.ssid)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f'Error disconnecting from {self.ssid}. Return code: {e.returncode}, error: {e.stderr}') from e
            if self.connection_id:
                self.print(f'Removing profile for {self.connection_id}...')
                delete_cmd = f'nmcli connection delete "{self.connection_id}"'
                try:
                    subprocess.run(delete_cmd, shell=True, capture_output=True,
                                   text=True, check=True)
                    logger.info('Successfully removed network profile for %s',
                                self.connection_id)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f'Error removing network profile for {self.ssid}. Return code: {e.returncode}, error: {e.stderr}') from e

        elif self.platform_system == 'Windows':
            if self.connection_id:
                self.print(f'Removing profile for {self.connection_id}...')
                profile_cmd = f'netsh wlan delete profile "{self.connection_id}"'
                try:
                    subprocess.run(profile_cmd, shell=True,
                                   capture_output=True, text=True, check=True)
                    logger.info('Successfully removed network profile for %s',
                                self.connection_id)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f'Error removing network profile for {self.ssid}. Return code: {e.returncode}, error: {e.stderr}') from e
            if self.existing_connection_id:
                self.print(f'Reconnecting to {self.existing_connection_id}...')
                connect_cmd = f'netsh wlan connect name="{self.existing_connection_id}"'
                try:
                    subprocess.run(connect_cmd, shell=True,
                                   capture_output=True, text=True, check=True)
                    logger.info('Successfully reconnected to original network profile: %s',
                                self.existing_connection_id)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f'Error reconnecting to original network profile: {self.existing_connection_id}. Return code: {e.returncode}, error: {e.stderr}') from e


def main():
    """
    Entry point when used as a CLI tool
    """
    CONNECTION_DELAY = 7

    CONFIG_FILES = [
        pathlib.Path(f'{APP_NAME}.ini'),  # In the same directory as the script
        pathlib.Path(f'~/.config/{APP_NAME}.ini').expanduser(),
        pathlib.Path(f'~/.config/{APP_NAME}/{APP_NAME}.ini').expanduser(),
        pathlib.Path(f'~/.config/{APP_NAME}/config.ini').expanduser(),
    ]

    # Iterate through possible paths and use the first one that exists
    config_path = None
    for config_f in CONFIG_FILES:
        if config_f.is_file():
            config_path = config_f
            break

    config = configparser.ConfigParser()
    # If config file is found, read its contents
    if config_path:
        # Create a configparser object and read the config file
        config.read(config_path)

    # Set defaults using the config file or the hardcoded defaults
    path = config.get(f'{APP_NAME}', 'path',
                      fallback=str(pathlib.Path('~/Documents/CPAP_Data/SD_card').expanduser()))
    url = config.get(f'{APP_NAME}', 'url',
                     fallback='http://192.168.4.1/dir?dir=A:')
    start_from = config.get(f'{APP_NAME}', 'start_from', fallback=None)
    day_count = config.getint(f'{APP_NAME}', 'day_count', fallback=None)
    show_progress = config.getboolean(f'{APP_NAME}', 'show_progress',
                                      fallback=False)
    verbose = config.getboolean(f'{APP_NAME}', 'verbose', fallback=False)
    overwrite = config.getboolean(f'{APP_NAME}', 'overwrite', fallback=False)
    keep_old = config.getboolean(f'{APP_NAME}', 'keep_old', fallback=False)
    ignore = config.get(f'{APP_NAME}', 'ignore',
                        fallback='JOURNAL.JNL,ezshare.cfg,System Volume Information')
    ssid = config.get(f'{APP_NAME}', 'ssid', fallback=None)
    psk = config.get(f'{APP_NAME}', 'psk', fallback=None)
    retries = config.getint(f'{APP_NAME}', 'retries', fallback=5)

    # Parse command line arguments
    description = textwrap.dedent(f"""\
    {APP_NAME} wirelessly syncs Resmed CPAP/BiPAP treatment data logs stored on a EZShare WiFi SD card wirelessly to your local device
    
    A configuration file can be used to set defaults
    See documentation for configuration file options, default locations, and precedence 
    Command line arguments will override the configuration file
    """)
    epilog = textwrap.dedent(f"""\
    NOTE: 
    Example:
        {APP_NAME} --ssid ezShare --psk 88888888 --show_progress
    """)
    parser = argparse.ArgumentParser(prog=APP_NAME, description=description,
                                     epilog=epilog,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--path', type=str,
                        help=f'set destination path, defaults to {path}')
    parser.add_argument('--url', type=str,
                        help=f'set source URL, Defaults to {url}')
    parser.add_argument('--start_from', type=str,
                        help=f'start from date in YYYYMMDD format, deaults to {start_from}; this will override day_count if set')
    parser.add_argument('--day_count', '-n', type=int,
                        help=f'number of days to sync, defaults to {day_count}; if both start_from and day_count are unset all files will be synced')
    parser.add_argument('--show_progress', action='store_true',
                        help=f'show progress, defaults to {show_progress}')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help=f'verbose output, defaults to {verbose}')
    parser.add_argument('--debug', '-vvv', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('--overwrite', action='store_true',
                        help=f'force overwriting existing files, defaults to {overwrite}')
    parser.add_argument('--keep_old', action='store_true',
                        help=f'do not overwrite even if newer version is available, defaults to {overwrite}')
    parser.add_argument('--ignore', type=str,
                        help=f'case insensitive comma separated list (no spaces) of files to ignore, defaults to {ignore}')
    parser.add_argument('--ssid', type=str,
                        help=f'set network SSID; WiFi connection will be attempted if set, defaults to {ssid}')
    parser.add_argument('--psk', type=str,
                        help='set network pass phrase, defaults to None')
    parser.add_argument('--retries', type=int,
                        help=f'set number of retries for failed downloads, defaults to {retries}')
    parser.add_argument('--version', action='version',
                        version=f'{APP_NAME} {VERSION}')
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
    if args.keep_old:
        keep_old = True
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
            raise ValueError(f'Invalid date format provided in \'start_from\'. Please use YYYYMMDD. Error: {e}') from e
    elif day_count:
        start_ts = datetime.datetime.now() - datetime.timedelta(days=day_count)
    else:
        start_ts = None

    ezshare = EZShare(path, url, start_ts, show_progress, verbose, overwrite,
                      keep_old, ssid, psk, ignore_list, retries,
                      CONNECTION_DELAY, args.debug)

    try:
        ezshare.run()
    except BaseException as e:
        raise e
    finally:
        ezshare.disconnect_from_wifi()
    ezshare.print('Complete')


if __name__ == '__main__':
    main()
