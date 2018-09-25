#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import requests
from datetime import datetime
from pytz import timezone
from time import sleep, time
from configobj import ConfigObj
from pyowm import OWM
from pymodbus.client.sync import ModbusSerialClient as ModbusClient

# read settings from config file
config = ConfigObj("pvoutput.txt")
SYSTEMID = config['SYSTEMID']
APIKEY = config['APIKEY']
OWMKey = config['OWMKEY']
OWMLon = float(config['Longitude'])
OWMLat = float(config['Latitude'])
LocalTZ = timezone(config['TimeZone'])


# Local time with timezone
def localnow():
    return datetime.now(tz=LocalTZ)


class Inverter(object):
    # Inverter properties
    status = -1
    pv_power = 0.0
    pv_volts = 0.0
    ac_volts = 0.0
    ac_power = 0.0
    wh_today = 0
    wh_total = 0
    temp = 0.0
    firmware = ''
    control_fw = ''
    model_no = ''
    serial_no = ''
    dtc = -1
    cmo_str = ''

    def __init__(self, address, port):
        """Return a Inverter object with port set to *port* and
         values set to their initial state."""
        self.inv = ModbusClient(method='rtu', port=port, baudrate=9600, stopbits=1,
                                parity='N', bytesize=8, timeout=1)
        self.unit = address
        self.date = timezone('UTC').localize(datetime(1970, 1, 1, 0, 0, 0))

    def read_inputs(self):
        """Try read input properties from inverter, return true if succeed"""
        ret = False

        if self.inv.connect():
            # by default read first 45 registers (from 0 to 44)
            # they contain all basic information needed to report
            rr = self.inv.read_input_registers(0, 45, unit=self.unit)
            if not rr.isError():
                ret = True

                self.status = rr.registers[0]
                if self.status != -1:
                    self.cmo_str = 'Status: '+str(self.status)
                # my setup will never use high nibble but I will code it anyway
                self.pv_power = float((rr.registers[1] << 16)+rr.registers[2])/10
                self.pv_volts = float(rr.registers[3])/10
                self.ac_power = float((rr.registers[11] << 16)+rr.registers[12])/10
                self.ac_volts = float(rr.registers[14])/10
                self.wh_today = float((rr.registers[26] << 16)+rr.registers[27])*100
                self.wh_total = float((rr.registers[28] << 16)+rr.registers[29])*100
                self.temp = float(rr.registers[32])/10
                self.date = localnow()

            else:
                self.status = -1
                ret = False

            self.inv.close()
        else:
            print 'Error connecting to port'
            ret = False

        return ret

    def version(self):
        """Read firmware version"""
        ret = False

        if self.inv.connect():
            # by default read first 45 holding registers (from 0 to 44)
            # they contain more than needed data
            rr = self.inv.read_holding_registers(0, 45, unit=self.unit)
            if not rr.isError():
                ret = True
                # returns G.1.8 on my unit
                self.firmware = \
                    str(chr(rr.registers[9] >> 8) + chr(rr.registers[9] & 0x000000FF) +
                        chr(rr.registers[10] >> 8) + chr(rr.registers[10] & 0x000000FF) +
                        chr(rr.registers[11] >> 8) + chr(rr.registers[11] & 0x000000FF))

                # does not return any interesting thing on my model
                self.control_fw = \
                    str(chr(rr.registers[12] >> 8) + chr(rr.registers[12] & 0x000000FF) +
                        chr(rr.registers[13] >> 8) + chr(rr.registers[13] & 0x000000FF) +
                        chr(rr.registers[14] >> 8) + chr(rr.registers[14] & 0x000000FF))

                # does match the label in the unit
                self.serial_no = \
                    str(chr(rr.registers[23] >> 8) + chr(rr.registers[23] & 0x000000FF) +
                        chr(rr.registers[24] >> 8) + chr(rr.registers[24] & 0x000000FF) +
                        chr(rr.registers[25] >> 8) + chr(rr.registers[25] & 0x000000FF) +
                        chr(rr.registers[26] >> 8) + chr(rr.registers[26] & 0x000000FF) +
                        chr(rr.registers[27] >> 8) + chr(rr.registers[27] & 0x000000FF))

                # as per Growatt protocol
                mo = (rr.registers[28] << 16) + rr.registers[29]
                self.model_no = (
                    'T' + str((mo & 0XF00000) >> 20) + ' Q' + str((mo & 0X0F0000) >> 16) +
                    ' P' + str((mo & 0X00F000) >> 12) + ' U' + str((mo & 0X000F00) >> 8) +
                    ' M' + str((mo & 0X0000F0) >> 4) + ' S' + str((mo & 0X00000F))
                )

                # 134 for my unit meaning single phase/single tracker inverter
                self.dtc = rr.registers[43]
            else:
                self.firmware = ''
                self.control_fw = ''
                self.model_no = ''
                self.serial_no = ''
                self.dtc = -1
                ret = False

            self.inv.close()
        else:
            print 'Error connecting to port'
            ret = False

        return ret


class Weather(object):
    API = ''
    lat = 0.0
    lon = 0.0
    temperature = 0.0
    cloud_pct = 0
    cmo_str = ''

    def __init__(self, API, lat, lon):
        self.API = API
        self.lat = lat
        self.lon = lon
        self.owm = OWM(self.API)

    def get(self):
        obs = self.owm.weather_at_coords(self.lat, self.lon)
        w = obs.get_weather()
        status = w.get_detailed_status()
        self.temperature = w.get_temperature(unit='celsius')['temp']
        self.cloud_pct = w.get_clouds()
        self.cmo_str = ('%s with cloud coverage of %s percent' % (status, self.cloud_pct))


class PVOutputAPI(object):
    wh_today_last = 0

    def __init__(self, API, systemID):
        self.API = API
        self.systemID = systemID

    def add_status(self, payload):
        """Add live output data. Data should contain the parameters as described
        here: http://pvoutput.org/help.html#api-addstatus ."""
        self.__call("https://pvoutput.org/service/r2/addstatus.jsp", payload)

    def add_output(self, payload):
        """Add end of day output information. Data should be a dictionary with
        parameters as described here: http://pvoutput.org/help.html#api-addoutput ."""
        self.__call("http://pvoutput.org/service/r2/addoutput.jsp", payload)

    def __call(self, url, payload):
        headers = {
            'X-Pvoutput-Apikey': self.API,
            'X-Pvoutput-SystemId': self.systemID,
            'X-Rate-Limit': '1'
        }

        # Make tree attempts
        for i in range(3):
            try:
                r = requests.post(url, headers=headers, data=payload, timeout=10)
                reset = round(float(r.headers['X-Rate-Limit-Reset']) - time())
                if int(r.headers['X-Rate-Limit-Remaining']) < 10:
                    print("Only {} requests left, reset after {} seconds".format(
                        r.headers['X-Rate-Limit-Remaining'],
                        reset))
                if r.status_code == 403:
                    print("Forbidden: " + r.reason)
                    sleep(reset + 1)
                else:
                    r.raise_for_status()
                    break
            except requests.exceptions.HTTPError as errh:
                print(localnow().strftime('%Y-%m-%d %H:%M'), " Http Error:", errh)
            except requests.exceptions.ConnectionError as errc:
                print(localnow().strftime('%Y-%m-%d %H:%M'), "Error Connecting:", errc)
            except requests.exceptions.Timeout as errt:
                print(localnow().strftime('%Y-%m-%d %H:%M'), "Timeout Error:", errt)
            except requests.exceptions.RequestException as err:
                print(localnow().strftime('%Y-%m-%d %H:%M'), "OOps: Something Else", err)

            sleep(5)
        else:
            print(localnow().strftime('%Y-%m-%d %H:%M'),
                  "Failed to call PVOutput API after {} attempts.".format(i))

    def send_status(self, date, energy_gen=None, power_gen=None, energy_imp=None,
                    power_imp=None, temp=None, vdc=None, cumulative=False, vac=None,
                    temp_inv=None, energy_life=None, comments=None, power_vdc=None):
        # format status payload
        payload = {
            'd': date.strftime('%Y%m%d'),
            't': date.strftime('%H:%M'),
        }

        # Only report total energy if it has changed since last upload
        # this trick avoids avg power to zero with inverter that reports
        # generation in 100 watts increments (Growatt and Canadian solar)
        if ((energy_gen is not None) and (self.wh_today_last != energy_gen)):
            self.wh_today_last = int(energy_gen)
            payload['v1'] = int(energy_gen)

        if power_gen is not None:
            payload['v2'] = float(power_gen)
        if energy_imp is not None:
            payload['v3'] = int(energy_imp)
        if power_imp is not None:
            payload['v4'] = float(power_imp)
        if temp is not None:
            payload['v5'] = float(temp)
        if vdc is not None:
            payload['v6'] = float(vdc)
        if cumulative is not None:
            payload['c1'] = 1
        if vac is not None:
            payload['v8'] = float(vac)
        if temp_inv is not None:
            payload['v9'] = float(temp_inv)
        if energy_life is not None:
            payload['v10'] = int(energy_life)
        if comments is not None:
            payload['m1'] = str(comments)[:30]
        # calculate efficiency
        if (power_gen is not None) and (power_vdc is not None):
            payload['v12'] = float(power_gen) / float(power_vdc)

        # Send status
        self.add_status(payload)


def main_loop():
    # init
    inv = Inverter(0x1, '/dev/ttyUSB0')
    inv.version()
    if OWMKey:
        owm = Weather(OWMKey, OWMLat, OWMLon)
        owm.fresh = False
    else:
        owm = False

    pvo = PVOutputAPI(APIKEY, SYSTEMID)

    # start and stop monitoring (hour of the day)
    shStart = 5
    shStop = 21
    # Loop until end of universe
    while True:
        if shStart <= localnow().hour < shStop:
            # get fresh temperature from OWM
            if owm:
                try:
                    owm.get()
                    owm.fresh = True
                except Exception as e:
                    print 'Error getting weather: {}'.format(e)
                    owm.fresh = False

            # get readings from inverter, if success send  to pvoutput
            inv.read_inputs()
            if inv.status != -1:
                # pvoutput(inv, owm)
                pvo.send_status(date=inv.date, energy_gen=inv.wh_today,
                                power_gen=inv.ac_power, vdc=inv.pv_volts,
                                vac=inv.ac_volts, temp=owm.temperature,
                                temp_inv=inv.temp, energy_life=inv.wh_total,
                                power_vdc=inv.pv_power)
                sleep(300)  # 5 minutes
            else:
                # some error
                sleep(60)  # 1 minute before try again
        else:
            # it is too late or too early, let's sleep until next shift
            hour = localnow().hour
            minute = localnow().minute
            if 24 > hour >= shStop:
                # before midnight
                snooze = (((shStart - hour) + 24) * 60) - minute
            elif shStart > hour <= 0:
                # after midnight
                snooze = ((shStart - hour) * 60) - minute
            print localnow().strftime('%Y-%m-%d %H:%M') + ' - Next shift starts in ' + \
                str(snooze) + ' minutes'
            sys.stdout.flush()
            snooze = snooze * 60  # seconds
            sleep(snooze)


if __name__ == '__main__':
    try:
        main_loop()
    except KeyboardInterrupt:
        print >> sys.stderr, '\nExiting by user request.\n'
        sys.exit(0)
