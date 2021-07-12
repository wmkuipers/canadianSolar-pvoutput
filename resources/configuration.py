#!/usr/bin/env python
from os import getenv as read_env
from os import environ

        # config = ConfigObj("pvoutput.txt")
        # SYSTEMID = config['SYSTEMID']
        # APIKEY = config['APIKEY']
        # OWMKey = config['OWMKEY']
        # OWMLon = float(config['Longitude'])
        # OWMLat = float(config['Latitude'])
        # LocalTZ = timezone(config['TimeZone'])

#Checking the required environment variables, exit container it they are missing
REQUIRED_ENVIRONMENT_VARIABLES = ['PVOUTPUT_SYSTEMID', 'PVOUTPUT_APIKEY']
missing_vars = [var for var in REQUIRED_ENVIRONMENT_VARIABLES if var not in environ]
if len(missing_vars) > 0:
    raise Exception(f"Missing required variables: {missing_vars}")

# Register at pvoutput.org to get your SYSTEMID and APIKEY
SYSTEMID=read_env('PVOUTPUT_SYSTEMID')
APIKEY=read_env('PVOUTPUT_APIKEY')

# Numbers of inverters (not used but kept for backwards compatibility)
Inverters=1

# Register at openweather.org to get your APIKEY
# If OWMKEY and Longitude and Latitude is not supplied
# no weather will be read, and tried uploaded to
# pvoutput.org - together with your energy data.
OWMKey=read_env('OWM_KEY', None)
OWMLat=float(read_env('LAT',''))
OWMLon=-float(read_env('LON',''))

# Set your timezone string so pytz can grab your localtime inside docker
TimeZone='Europe/Amsterdam'

# Devault inverter device
INVERTER_DEVICE_ADDRESS= read_env("INVERTER_DEVICE_ADDRESS", '/dev/ttyUSB0')
