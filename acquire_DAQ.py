import requests
import socket
import numpy as np
import time
from openapi.openapi_header import *
from openapi.openapi_stream import *

def acquire_data_minutes(ip, frequency, num_channels, minutes):
    """
    Acquires data for the specified number of minutes from the LAN-XI device.
    Sets up default channel config (which streams to SD card), then switches to socket streaming.
    """
    host = f"http://{ip}"

    # Open recorder application
    resp = requests.put(host + "/rest/rec/open")
    if resp.status_code != 200:
        print(f"Failed to open recorder: {resp.status_code} {resp.text}")
        return None

    # Get default channel setup (default is SD card destination)
    resp = requests.get(host + "/rest/rec/channels/input/default")
    try:
        setup = resp.json()
    except Exception:
        print(f"Failed to get default channel setup: {resp.status_code} {resp.text}")
        return None

    # Disable all channels
    import HelpFunctions.utility as utility
    utility.update_value("enabled", False, setup)

    # Enable specified channels and switch destination from SD card to socket
    for ch in range(num_channels):
        setup["channels"][ch]["enabled"] = True
        # The default is usually "sdcard", so we switch it to "socket"
        # Set both for maximum compatibility
        setup["channels"][ch]["destination"] = "socket"
        setup["channels"][ch]["destinations"] = ["socket"]
        setup["channels"][ch]["sampleRate"] = frequency

    # Alternatively, update all with utility if you prefer:
    # utility.update_value("destination", "socket", setup)
    # utility.update_value("destinations", ["socket"], setup)

    # Create input channels with the setup (now destination is socket, not SD card)
    resp = requests.put(host + "/rest/rec/channels/input", json=setup)
    if resp.status_code != 200:
        print(f"Failed to set up input channels: {resp.status_code} {resp.text}")
        return None

    # Get streaming socket port
    resp = requests.get(host + "/rest/rec/destination/socket")
    try:
        inputport = resp.json()["tcpPort"]
    except Exception:
        print(f"Failed to get socket port: {resp.status_code} {resp.text}")
        return None

    # Start measurement
    resp = requests.post(host + "/rest/rec/measurements")
    if resp.status_code not in [200, 201, 204]:
        print(f"Failed to start measurement: {resp.status_code} {resp.text}")
        return None

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
    if collected:
        return np.vstack(collected)
    else:
        return np.empty((0, num_channels))