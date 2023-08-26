This script assists in using a WiFi enabled SD card by EzShare in your CPAP/BiPap device.
This is coded for use with most ResMed devices from version 9 and up. 
Feel free to fork it for use with Philips Respironics and other devices.

Most of the program is platform-independent, but there's a bit of extra convenience built in for Mac users.

The program runs on Python 3, and requires the Requests and Beautiful Soup 4 libraries.

####################################################################################################
Python & Libraries installation:
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

#################################################################################################
Data Location:
#################################################################################################

The default code (os.path.join etc) will place the file in the path below. 
Windows:      C:\Users\MY_USERNAME\Documents\CPAP_Data
MacOS:        /home/MY_USERNAME/Documents/CPAP_Data
Linux et al:  /home/MY_USERNAME/Documents/CPAP_Data

You may need to create a directory named CPAP_Data in your Documents folder. 

You can store it wherever you want to, as long as OSCAR can read from it. Just modify the configuration block with the location you prefer.


#################################################################################################
Configuration options & defaults
#################################################################################################

START_FROM -- This has three options:
1) an integer indicating the number of days of history to download 
2) a YYYYMMDD date indicating which date to start from 
3) A string, 'ALL', removing date restrictions and downloading all available data

OVERWRITE -- This has two options:
False - Don't overwrite any of the date-specific files. (other files must always be overwritten)
True - delete and replace. This is mostly useful if you either accidentally deleted a partial date in OSCAR, or if you ran this and then went back to sleep before noon and wanted to ensure that the full day was captured

SHOW_PROGRESS -- This has three options:
False - Shows fairly minimal output
True - Shows date folder output
Verbose - Shows what happens to every file


####################################################################################################
EZCard Setup
####################################################################################################
By default, EzCard creates a wifi network named "Ez Card" with a password of 88888888 (that's eight eights)
You can change the network name and password via the card's web interface: 
http://ezshare.card/config?vtype=0 (default card admin password is "admin").

If necessary, deleting the ezshare.cfg file will change the network information back to the default.

EZSHARE_NETWORK = "Ez Card"
EZSHARE_PASSWORD = "88888888"


#################################################################################################
Retrieving files from the card
#################################################################################################
This may be called from its folder directly, with or without arguments to overwrite the defaults:
python ezshare_resmed.py 
python ezshare_resmed.py --start_from 20230101 --show_progress Verbose --overwrite
It may also be called from a shell script, so you can put that on your desktop 
while keeping the python code in a less accessible location:
./run_foo.sh
./run_foo.sh --start_from 20230101 --show_progress Verbose --overwrite

#################################################################################################
Use with OSCAR
#################################################################################################
It's very easy to use this with OSCAR. On the Welcome tab, simply click on the CPAP importer icon (looks like an SD card) and navigate to the folder specified in the data location configuration. It will likely save that location and use it going forward.
