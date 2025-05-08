import requests
import socket
import numpy as np
import time
from openapi.openapi_header import *
from openapi.openapi_stream import *

def acquire_data_loopback(ip, frequency, num_channels, minutes):
    host = f"http://{ip}"

    # Open recorder application
    requests.put(host + "/rest/rec/open")

    # Get module info (optional, but in loopback.py)
    requests.get(host + "/rest/rec/module/info")

    # Create a new recording
    requests.put(host + "/rest/rec/create")

    # Get default channel setup
    response = requests.get(host + "/rest/rec/channels/input/default")
    setup = response.json()

    # Disable all channels
    import HelpFunctions.utility as utility
    utility.update_value("enabled", False, setup)

    # Enable specified channels and set destination to socket
    for ch in range(num_channels):
        setup["channels"][ch]["enabled"] = True
        # Set both for compatibility
        setup["channels"][ch]["destination"] = "socket"
        setup["channels"][ch]["destinations"] = ["socket"]
        setup["channels"][ch]["sampleRate"] = frequency

    # Create input channels with the setup
    requests.put(host + "/rest/rec/channels/input", json=setup)

    # Get streaming socket port
    response = requests.get(host + "/rest/rec/destination/socket")
    inputport = response.json()["tcpPort"]

    # Start measurement
    requests.post(host + "/rest/rec/measurements")

    # Acquire data for the specified duration
    duration_sec = minutes * 60
    collected = []
    start_time = time.time()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, inputport))
        while (time.time() - start_time) < duration_sec:
            data = s.recv(28)
            wstream = OpenapiHeader.from_bytes(data)
            content_length = wstream.content_length + 28
            while len(data) < content_length:
                packet = s.recv(content_length - len(data))
                data += packet
            package = OpenapiStream.from_bytes(data)
            if package.header.message_type == OpenapiStream.Header.EMessageType.e_signal_data:
                row = []
                for ch in range(num_channels):
                    signal = package.content.signals[ch]
                    if signal is not None:
                        new_data = [x.calc_value for x in signal.values]
                        row.append(new_data)
                if row:
                    collected.append(np.array(row).T)
    # No print, no return, no file save, no output

# Example usage:
# acquire_data_loopback("169.254.230.53", 51200, 2, 2)