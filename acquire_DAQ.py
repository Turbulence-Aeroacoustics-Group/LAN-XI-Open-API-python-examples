import requests
import socket
import numpy as np
from openapi.openapi_header import *
from openapi.openapi_stream import *
import HelpFunctions.utility as utility

def acquire_data_loopback(ip, frequency, minutes):
    host = f"http://{ip}"

    # Close and open recorder
    requests.put(host + "/rest/rec/close")
    requests.put(host + "/rest/rec/open")
    requests.get(host + "/rest/rec/module/info")
    requests.put(host + "/rest/rec/create")

    # Get default setup for channels
    response = requests.get(host + "/rest/rec/channels/input/default")
    setup = response.json()

    # Replace stream destination from default SD card to socket
    utility.update_value("destinations", ["socket"], setup)
    # Set enabled to false for all channels
    utility.update_value("enabled", False, setup)
    # Enable channel 0
    setup["channels"][0]["enabled"] = True

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
    interpretations = [{}]

    # Stream and parse data
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, inputport))
        while array.size <= N:
            data = s.recv(28)
            wstream = OpenapiHeader.from_bytes(data)
            content_length = wstream.content_length + 28
            while len(data) < content_length:
                packet = s.recv(content_length - len(data))
                data += packet
            package = OpenapiStream.from_bytes(data)
            if package.header.message_type == OpenapiStream.Header.EMessageType.e_interpretation:
                for interpretation in package.content.interpretations:
                    interpretations[0][interpretation.descriptor_type] = interpretation.value 
            if package.header.message_type == OpenapiStream.Header.EMessageType.e_signal_data:
                for signal in package.content.signals:
                    if signal is not None:
                        sensitivity = 1
                        array = np.append(
                            array,
                            np.array([x.calc_value * sensitivity for x in signal.values])
                        )
    # No output, no return, no file save, no plot—completely silent

# Example usage (will do nothing visible):
# acquire_data_loopback("169.254.230.53", 51200, 2)