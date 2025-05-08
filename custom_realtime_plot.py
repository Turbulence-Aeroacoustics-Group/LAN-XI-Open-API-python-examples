import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import socket
import time
import os
from fft_utils import compute_pwelch
from openapi.openapi_header import *
from openapi.openapi_stream import *

class RealTimePlotter:
    def __init__(self, data_acquisition, save_data=False, save_path=None, chunk_size=2**12):
        self.data_acq = data_acquisition
        self.chunk_size = chunk_size
        self.buffer = np.zeros(self.chunk_size)
        self.start_time = None
        self.save_data = save_data
        self.save_path = save_path or "acquired_data"
        self.collected_data = []
        self.collected_timestamps = []
        self.is_collecting = False
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1)
        self.setup_plots()
        self.setup_keyboard_controls()

    def setup_plots(self):
        # Time axis in seconds for the time-domain plot
        self.time_axis = np.arange(self.chunk_size) / self.data_acq.sample_rate
        self.line1, = self.ax1.plot(self.time_axis, np.zeros(self.chunk_size))
        self.ax1.set_title("Time Domain")
        self.ax1.set_xlabel("Time [s]")
        self.ax1.set_ylabel("Voltage")
        self.ax1.grid(True)

        # Frequency axis for the PSD plot (will be updated in update_plot)
        freq_init = np.linspace(1, self.data_acq.sample_rate / 2, self.chunk_size // 2 + 1)
        self.line2, = self.ax2.plot(freq_init, np.ones_like(freq_init))
        self.ax2.set_title("PSD (Welch, dB)")
        self.ax2.set_xlabel("Frequency [Hz]")
        self.ax2.set_ylabel("Amplitude [dB]")
        self.ax2.set_xscale('log')
        self.ax2.set_yscale('log')
        self.ax2.grid(True)

    def setup_keyboard_controls(self):
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)

    def on_key_press(self, event):
        if event.key == 's':
            if not self.is_collecting:
                self.is_collecting = True
                self.collected_data = []
                self.collected_timestamps = []
                print("\nStarted collecting data...")
            else:
                self.is_collecting = False
                self.save_to_file()
                print("\nStopped collecting data")
        elif event.key == 'q':
            plt.close()

    def save_to_file(self):
        if not self.collected_data:
            print("No data to save")
            return
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)
        np.save(os.path.join(self.save_path, "data.npy"), np.array(self.collected_data))
        np.save(os.path.join(self.save_path, "timestamps.npy"), np.array(self.collected_timestamps))
        print(f"Saved data to {self.save_path}")

    def update_plot(self, frame):
        try:
            # Acquire data from the socket
            data = self.socket.recv(28)
            wstream = OpenapiHeader.from_bytes(data)
            content_length = wstream.content_length + 28
            while len(data) < content_length:
                packet = self.socket.recv(content_length - len(data))
                data += packet
            package = OpenapiStream.from_bytes(data)
            for signal in package.content.signals:
                if signal is not None:
                    new_data = np.array(list(map(lambda x: x.calc_value, signal.values)))
                    # Optionally scale new_data here if needed
                    self.buffer = np.roll(self.buffer, -len(new_data))
                    self.buffer[-len(new_data):] = new_data
                    if self.is_collecting:
                        self.collected_data.append(new_data.copy())
                        self.collected_timestamps.append(time.time())
            # Update time-domain plot
            self.line1.set_xdata(self.time_axis)
            self.line1.set_ydata(self.buffer)
            # Update frequency-domain plot (Welch PSD)
            freq, fft_db = compute_pwelch(self.buffer, self.data_acq.sample_rate, nperseg=self.chunk_size)
            self.line2.set_xdata(freq)
            self.line2.set_ydata(fft_db)
            self.fig.suptitle('Recording...' if self.is_collecting else 'Press S to start recording', 
                              color='red' if self.is_collecting else 'black')
            return self.line1, self.line2
        except Exception as e:
            print(f"Error in update_plot: {e}")
            return self.line1, self.line2

    def start_plotting(self):
        # Open socket connection
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.data_acq.ip, self.data_acq.inputport))
        # Set refresh interval to match chunk size
        interval = int((self.chunk_size / self.data_acq.sample_rate) * 1000)
        self.fig.suptitle('Press S to start recording', color='black')
        self.fig.text(0.99, 0.01, 'S: Start/Stop Recording | Q: Quit', 
                      ha='right', va='bottom', fontsize=8)
        ani = FuncAnimation(self.fig, self.update_plot, interval=interval)
        plt.show()


class CustomDataAcquisition:
    def __init__(self, ip, channels, frequency):
        self.ip = ip
        self.channels = channels
        self.frequency = frequency
        self.sample_rate = frequency  # Placeholder; replace with actual logic

    def initialize_module(self):
        # Initialize connection or hardware here
        print(f"Initializing data acquisition on {self.ip} for channels {self.channels} at {self.frequency} Hz")
        # Add actual initialization logic as needed

    def cleanup(self):
        if self.is_collecting:
            self.save_to_file()
        if hasattr(self, 'socket'):
            self.socket.close()
        requests.put(self.data_acq.host + "/rest/rec/measurements/stop")
        requests.put(self.data_acq.host + "/rest/rec/finish")
        requests.put(self.data_acq.host + "/rest/rec/close")


def run_custom_realtime_plot(ip_address, channels, frequency, acq_time,
                             chunk_size=8192, save_path="acquired_data"):
    """
    Runs the custom real-time plotter.
    """
    data_acq = CustomDataAcquisition(ip_address, channels, frequency)
    data_acq.initialize_module()
    plotter = RealTimePlotter(data_acq, save_data=True, save_path=save_path, chunk_size=chunk_size)
    plotter.start_plotting()