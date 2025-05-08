from custom_realtime_plot import run_custom_realtime_plot
# from fft_analyzer import run_fft_analyzer  # Not needed if you only want the plot

def main():
    ip_address = "169.254.230.53"
    channels_to_enable = [0]
    target_frequency = 51200
    acq_time = 10
    chunk_size = 8192  # Example: 2**13
    save_path = "my_custom_data"  # Example: custom directory

    # Call custom real-time plot
    run_custom_realtime_plot(
        ip_address, channels_to_enable, target_frequency, acq_time,
        chunk_size=chunk_size, save_path=save_path
    )

    # If you want to run FFT analyzer as well, uncomment below:
    # run_fft_analyzer(ip_address, channels_to_enable, target_frequency)

if __name__ == "__main__":
    main()