from acquire_DAQ import acquire_data_loopback

def main():
    ip = "169.254.230.53"
    frequency = 51200
    num_channels = 2
    minutes = 2

    # This will perform the acquisition silently (no output, no return)
    acquire_data_loopback(ip, frequency, num_channels, minutes)

if __name__ == "__main__":
    main()