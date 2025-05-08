import requests
import socket
import numpy as np
from openapi.openapi_header import *
from openapi.openapi_stream import *
import HelpFunctions.utility as utility

def acquire_data_loopback(ip, sample_rate, minutes):
    host = f"http://{ip}"

    # Close recorder application if already open
    requests.put(host + "/rest/rec/close")
    # Open recorder application
    requests.put(host + "/rest/rec/open")
    # Get module info
    requests.get(host + "/rest/rec/module/info")
    # Create a new recording
    requests.put(host + "/rest/rec/create")
    # Get Default setup for channels
    response = requests.get(host + "/rest/rec/channels/input/default")
    setup = response.json()
    # Replace stream destination from default SD card to socket
    utility.update_value("destinations", ["socket"], setup)
    # Set enabled to false for all channels
    utility.update_value("enabled", False, setup)
    # Enable channel 0, which should be connected to generator 0
    setup["channels"][0]["enabled"] = True
    
    # Create input channels with the setup
    response = requests.put(host + "/rest/rec/channels/input", json=setup)
    
    # Get streaming socket port
    response = requests.get(host + "/rest/rec/destination/socket")
    inputport = response.json()["tcpPort"]
    
    # Start measurement
    response = requests.post(host + "/rest/rec/measurements")
    
    # Calculate number of samples to collect
    N = sample_rate * minutes * 60  # Collect n minutes of samples
    array = np.array([])
    interpretations = [{}]
    
    # Stream and parse data
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((ip, inputport))
        while array.size <= N:
            # First get the header of the data
            data = s.recv(28)
            wstream = OpenapiHeader.from_bytes(data)
            content_length = wstream.content_length + 28
            # We use the header's content_length to collect the rest of a package
            while len(data) < content_length:
                packet = s.recv(content_length - len(data))
                data += packet
            # Here we parse the data into a StreamPackage
            package = OpenapiStream.from_bytes(data)
            if package.header.message_type == OpenapiStream.Header.EMessageType.e_interpretation:
                for interpretation in package.content.interpretations:
                    interpretations[interpretation.signal_id - 1][interpretation.descriptor_type] = interpretation.value 
            # Here we parse the data into a StreamPackage
            package = OpenapiStream.from_bytes(data)
            if package.header.message_type == OpenapiStream.Header.EMessageType.e_signal_data:  # If the data contains signal data
                for signal in package.content.signals:  # For each signal in the package
                    if signal != None:
                        # Sensitivity can not come from TEDS, set it to a default value
                        sensitivity = 1
                        # We append the data to an array and continue
                        array = np.append(array, np.array([x.calc_value * sensitivity for x in signal.values]))
    
    # Stop measurements
    response = requests.put(host + "/rest/rec/measurements/stop")
    s.close()
    
    # No output, no plot, no print statements

# Example usage:
# acquire_data_loopback("169.254.230.53", 51200, 2)