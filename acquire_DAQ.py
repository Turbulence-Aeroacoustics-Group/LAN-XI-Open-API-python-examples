import requests
import socket
import numpy as np
from openapi.openapi_header import *
from openapi.openapi_stream import *
import HelpFunctions.utility as utility

def acquire_data_loopback(ip, frequency, num_channels, minutes):
    host = f"http://{ip}"

    # Close recorder application (as in loopback.py)
    requests.put(host + "/rest/rec/close")
    # Open recorder application
    requests.put(host + "/rest/rec/open")
    # Get module info
    requests.get(host + "/rest/rec/module/info")
    # Create a new recording
    requests.put(host + "/rest/rec/create")
    # Get default input channel setup
    response = requests.get(host + "/rest/rec/channels/input/default")
    setup = response.json()
    # Set all channels to stream to socket and disable all
    utility.update_value("destinations", ["socket"], setup)
    utility.update_value("enabled", False, setup)
    # Enable only the requested channels
    for idx in range(num_channels):
        setup["channels"][idx]["enabled"] = True
        setup["channels"][idx]["sampleRate"] = frequency
    # Create input channels with the setup
    requests.put(host + "/rest/rec/channels/input", json=setup)
    # Get streaming socket port
    response = requests.get(host + "/rest/rec/destination/socket")
    inputport = response.json()["tcpPort"]
    # Start measurement
    requests.post(host + "/rest/rec/measurements")

    # Calculate number of samples to collect
    sample_rate = frequency
    seconds = minutes * 60
    N = int(sample_rate * seconds)
    array = np.array([])
    interpretations = [{} for _ in range(num_channels)]

    # Stream and parse data
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, inputport))
        while array.size < N * num_channels:
            data = s.recv(28)
            wstream = OpenapiHeader.from_bytes(data)
            content_length = wstream.content_length + 28
            while len(data) < content_length:
                packet = s.recv(content_length - len(data))
                data += packet
            package = OpenapiStream.from_bytes(data)
            if package.header.message_type == OpenapiStream.Header.EMessageType.e_interpretation:
                for interp in package.content.interpretations:
                    ch_idx = interp.signal_id - 1
                    if 0 <= ch_idx < num_channels:
                        interpretations[ch_idx][interp.descriptor_type] = interp.value
            if package.header.message_type == OpenapiStream.Header.EMessageType.e_signal_data:
                for signal in package.content.signals:
                    if signal is not None:
                        sensitivity = 1  # Use 1 if not using TEDS
                        array = np.append(
                            array,
                            np.array([x.calc_value * sensitivity for x in signal.values])
                        )
    # Reshape to (samples, channels)
    total_samples = array.size // num_channels
    data = array[:total_samples * num_channels].reshape((total_samples, num_channels))
    return data

# Example usage:
# data = acquire_data_loopback("169.254.230.53", 51200, 2, 2)
# print(data.shape)  # (samples, channels)