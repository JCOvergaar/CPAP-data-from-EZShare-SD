#!/usr/bin/env python3
import os
import time
import sys
import platform
import argparse
import subprocess
import logging


def connect_to_wifi(ssid=None, psk=None):
    """Wifi Connect - If enabled, check OS, and if MacOS, switch wifi to the EZShare SSID
    
    Returns:
        bool: True when succesfully connected or user manually continues, False when user cancels
    """
    if platform.system() == 'Darwin':
        cmd = f'networksetup -setairportnetwork en0 {ssid}'
        if psk:
            cmd += f' {psk}'

        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode == 0:
            log.info(f"Connected to {ssid} successfully.")
            return True
        else:
            self.log.warning(f"Failed to connect to {ssid}. Error: {result.stderr.decode('utf-8')}")
            if sys.__stdin__.isatty():
                response = input("Unable to connect automatically, please connect manually and press 'C' to continue or any other key to cancel: ")
                if response.lower() == 'c':
                    return True
                else:
                    return False
            else:
                return False
    elif platform.system() == 'Linux' and platform.freedesktop_os_release()["VERSION_CODENAME"] == 'bookworm':
        if self.psk:
            cmd = f'nmcli d wifi connect "{self.ssid}" password {self.psk}'
        else:
            cmd = f'nmcli connection up "{self.ssid}"'

        for attempt in range(3):
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
                break
            except requests.exceptions.RequestException as e:
                time.sleep(1) # Wait a second before retrying

        if result.returncode == 0:
            # Regular expression pattern to match the string after "activated with"
            pattern = r"activated with '([^']*)'"

            # Search for the pattern in the message
            match = re.search(pattern, result.stdout)

            if match:
                # Extract the string after "activated with"
                self.connection_id = match.group(1)

            self.log.info(f"Connected to {self.ssid} successfully.")
            return True
        else:
            self.log.warning(f"Failed to connect to {self.ssid}. Error: {result.stderr.decode('utf-8')}")
            if sys.__stdin__.isatty():
                response = input("Unable to connect automatically, please connect manually and press 'C' to continue or any other key to cancel: ")
                if response.lower() == 'c':
                    return True
                else:
                    return False
            else:
                return False
    else:
        self.log.warning(f'Wifi connection is not supported on this OS.')
        self.log.warning(f'You appear to be running {platform.system()}.')
        if sys.__stdin__.isatty():
            response = input(f"""Please connect manually and press 'C' and then 'Enter' to continue, or any other key and 'Enter' to cancel: """)
            if response.lower() == 'c':
                return True
            else:
                return False
        else:
            return False


def main():
    pass

if __name__ == '__main__':
    main()