This script assists in using a WiFi enabled SD card by EzShare in your CPAP/BiPap device.
This is coded for use with most ResMed devices from version 9 and up. 
Feel free to fork it for use with Philips Respironics and other devices.

Most of the program is platform-independent, but there's a bit of extra convenience built in for Mac users.

The program runs on Python 3, and requires the Requests and Beautiful Soup 4 libraries.

####################################################################################################
Python & Libraries installation
####################################################################################################
Download and install Python 3 from the official website: https://www.python.org/downloads/
Make sure to check the option to add Python to PATH during the installation process.
(Mac users may prefer to use the HomeBrew* package manager)

Open Terminal (Mac)/ Command Prompt (Windows) and run the following command to install the additional required libraries:

pip install requests beautifulsoup4

### Alternate MacOS instructions using HomeBrew (run commands in Terminal):
Skip first line of HomeBrew is already installed.

/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python
pip install requests beautifulsoup4

####################################################################################################
EZCard Setup & Usage
####################################################################################################
By default, EzCard creates a wifi network named "Ez Card" with a password of 88888888 (that's eight eights)
To change the network name and password, create or edit a file named ezshare.cfg on the card.
You can also do it via the card's web interface: http://ezshare.card/config?vtype=0 (default card admin password is "admin").
If necessary, deleting the ezshare.cfg file will change the network information back to the default.

Create a directory named CPAP_Data in your Documents folder. (You can choose a different name, just edit it in the configuration.)

Edit the configuration section of the .sh file as needed. 

run the program from the command line:
python3 transferCardData.py

