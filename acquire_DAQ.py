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
    requests.get(host + "/rest/rec/module/info")
    requests.put(host + "/rest/rec/create")
    response = requests.get(host + "/rest/rec/channels/input/default")
    setup = response.json()

    # Print available channels for debugging
    print(f"Total channels in setup: {len(setup['channels'])}")
    for idx, ch in enumerate(setup['channels']):
        print(f"Channel {idx}: enabled={ch['enabled']}, number={ch.get('number', idx)}")

    # Disable all channels
    import HelpFunctions.utility as utility
    utility.update_value("enabled", False, setup)

    # Enable specified channels and set destination to socket
    available_channels = [i for i, ch in enumerate(setup["channels"])]
    for ch in available_channels[:num_channels]:
        setup["channels"][ch]["enabled"] = True
        setup["channels"][ch]["destination"] = "socket"
        setup["channels"][ch]["destinations"] = ["socket"]
        setup["channels"][ch]["sampleRate"] = frequency

    requests.put(host + "/rest/rec/channels/input", json=setup)
    response = requests.get(host + "/rest/rec/destination/socket")
    inputport = response.json()["tcpPort"]
    requests.post(host + "/rest/rec/measurements")

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
                # Build a 2D array: shape (n_samples, n_channels)
                signal_arrays = []
                for signal in package.content.signals:
                    if signal is not None:
                        signal_arrays.append([x.calc_value for x in signal.values])
                # Transpose if needed to get (n_samples, n_channels)
                if signal_arrays:
                    arr = np.array(signal_arrays).T  # shape: (n_samples, n_channels)
                    collected.append(arr)

    if collected:
        data = np.vstack(collected)  # shape: (total_samples, n_channels)
        return data
    else:
        return np.empty((0, num_channels))

# Example usage:
# data = acquire_data_loopback("169.254.230.53", 51200, 2, 2)
# print(data.shape)  # (samples, channels)