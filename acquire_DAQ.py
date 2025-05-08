def acquire_loopback_5seconds():
    import requests
    import socket
    import numpy as np
    from openapi.openapi_header import *
    from openapi.openapi_stream import *
    import HelpFunctions.utility as utility
    
    # Hardcoded parameters (like in loopback.py)
    ip = "169.254.230.53"  # Default LAN-XI IP
    sample_rate = 51200     # Default sample rate
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
    
    # Hardcoded to collect 5 seconds of data
    N = sample_rate * 5  # Collect 5 seconds of samples
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
            # Parse the data again
            package = OpenapiStream.from_bytes(data)
            if package.header.message_type == OpenapiStream.Header.EMessageType.e_signal_data:
                for signal in package.content.signals:
                    if signal != None:
                        sensitivity = 1
                        array = np.append(array, np.array([x.calc_value * sensitivity for x in signal.values]))
    
    # Stop measurements
    response = requests.put(host + "/rest/rec/measurements/stop")
    s.close()
    
    # No output, no plot, no print statements

# Simply call the function with no parameters
# acquire_loopback_5seconds()