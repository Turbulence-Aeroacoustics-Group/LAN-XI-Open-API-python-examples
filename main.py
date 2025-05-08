from acquire_DAQ import acquire_data_minutes

def main():
    ip = "169.254.230.53"
    frequency = 51200
    num_channels = 2
    minutes = 2

    data = acquire_data_minutes(ip, frequency, num_channels, minutes)
    # You can add further processing or saving here if needed
    print(f"Data shape: {data.shape}")

if __name__ == "__main__":
    main()