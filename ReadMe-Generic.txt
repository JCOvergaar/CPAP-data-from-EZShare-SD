This script assists in using a WiFi enabled SD card by EzShare. For Resmed devices, use the ResMed specific version for more options. 
Please feel free to create versions supporting Philips and other manufacturers - I wasn't able to get a card from anything but resmed.

Most of the program is platform-independent, but there's a bit of extra convenience built in for Mac users.

The program runs on Python 3, and requires the Requests and Beautiful Soup 4 libraries.

Since I don't know anything about the SD structure of other manufacturers, this version will overwrite everything, every time, so 
it may get to be time consuming if you have a lot of data. You can set an import cutoff date in OSCAR to at least save some time there.

####################################################################################################
Python & Libraries installation:
####################################################################################################
Download and install Python 3 from the official website: https://www.python.org/downloads/
Make sure to check the option to add Python to PATH during the installation process.
(Mac users may prefer to use the HomeBrew* package manager)

Open Terminal (Mac)/ Command Prompt (Windows) and run the following command to install the additional required libraries:

cd CPAP-data-from-EZShare-SD
pip install -r requirements.txt

### Alternate MacOS instructions using HomeBrew (run commands in Terminal):
Skip first line of HomeBrew is already installed.

/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python
cd CPAP-data-from-EZShare-SD
pip install -r requirements.txt

#################################################################################################
Data Location:
#################################################################################################

The default code (os.path.join etc) will place the file in the path below. 
Windows:      C:\Users\MY_USERNAME\Documents\CPAP_Data
MacOS:        /Users/MY_USERNAME/Documents/CPAP_Data
Linux et al:  /home/MY_USERNAME/Documents/CPAP_Data

You may need to create a directory named CPAP_Data in your Documents folder. 

You can store it wherever you want to, as long as OSCAR can read from it. Just modify the configuration block with the location you prefer.


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
python ezshare_generic.py 

#################################################################################################
Use with OSCAR
#################################################################################################
It's very easy to use this with OSCAR. On the Welcome tab, simply click on the CPAP importer icon (looks like an SD card) and navigate to the folder specified in the data location configuration. It will likely save that location and use it going forward.
