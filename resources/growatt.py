# import asyncio
import logging
from sys import argv
import json

from growattRS232 import GrowattRS232

from flask import Flask

app = Flask(__name__)



# defaults
# USB port of RS232 converter
DEFAULT_PORT = "/dev/ttyUSB0"
# Growatt modbus address
DEFAULT_ADDRESS = 0x3

logging.basicConfig(level=logging.DEBUG)


async def read_data_from_growatt():
    port = str(argv[1]) if len(argv) > 1 else DEFAULT_PORT
    address = int(argv[2]) if len(argv) > 2 else DEFAULT_ADDRESS
    growattRS232 = GrowattRS232(port, address)
    try:
        data = await growattRS232.async_update()
        return data
    except Exception as error:
        print("Error: " + repr(error))
        return None


@app.route("/status")
async def get_data():
    data = await read_data_from_growatt()
    return json.dumps(data, indent=4) if data is not None else "[ERROR] reading growatt"