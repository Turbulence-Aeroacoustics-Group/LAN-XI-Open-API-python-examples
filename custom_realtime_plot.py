import requests
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import socket
from openapi.openapi_header import *
from openapi.openapi_stream import *
import HelpFunctions.utility as utility
import time
import os

from fft_analyzer import compute_fft  # Only import compute_fft, not run_fft_analyzer

class CustomDataAcquisition:
    def __init__(self, ip_address, channels, frequency, acq_time=None):
        self.ip = ip_address
        self.host = "http://" + ip_address
        self.channels = channels
        self.target_frequency = frequency
        self.acq_time = acq_time  # Total acquisition time in seconds (None for infinite)
        self.setup = None
        self.sample_rate = None
        self.inputport = None
        self.array = np.array([])
        self.interpretations = [{},{},{},{},{},{}]
        self.start_time = None

    def initialize_module(self):
        response = requests.put(self.host + "/rest/rec/open")
        response = requests.get(self.host + "/rest/rec/module/info")
        self.module_info = response.json()
        response = requests.put(self.host + "/rest/rec/create")
        response = requests.get(self.host + "/rest/rec/channels/input/default")
        self.setup = response.json()
        utility.update_value("destinations", ["socket"], self.setup)
        utility.update_value("enabled", False, self.setup)
        for channel in self.channels:
            self.setup["channels"][channel]["enabled"] = True
        supported_rates = self.module_info["supportedSampleRates"]
        self.sample_rate = min(supported_rates, key=lambda x:abs(x - self.target_frequency))
        response = requests.put(self.host + "/rest/rec/channels/input", json=self.setup)
        response = requests.get(self.host + "/rest/rec/destination/socket")
        self.inputport = response.json()["tcpPort"]
        response = requests.post(self.host + "/rest/rec/measurements")

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

    def setup_plots(self):
        self.line1, = self.ax1.plot(np.zeros(self.chunk_size))
        self.ax1.set_title("Time Domain")
        self.ax1.set_xlabel("Samples")
        self.ax1.set_ylabel("Amplitude")
        self.ax1.grid(True)
        self.line2, = self.ax2.plot(np.zeros(self.chunk_size//2+1))
        self.ax2.set_title("FFT (dB)")
        self.ax2.set_xlabel("Frequency [Hz]")
        self.ax2.set_ylabel("Amplitude [dB]")
        self.ax2.grid(True)

    def update_plot(self, frame):
        try:
            if self.data_acq.acq_time is not None:
                if self.start_time is None:
                    self.start_time = time.time()
                elif time.time() - self.start_time >= self.data_acq.acq_time:
                    if self.is_collecting:
                        self.save_to_file()
                    plt.close()
                    return self.line1, self.line2
            data = self.socket.recv(28)
            wstream = OpenapiHeader.from_bytes(data)
            content_length = wstream.content_length + 28
            while len(data) < content_length:
                packet = self.socket.recv(content_length - len(data))
                data += packet
            package = OpenapiStream.from_bytes(data)
            if package.header.message_type == OpenapiStream.Header.EMessageType.e_signal_data:
                for signal in package.content.signals:
                    if signal is not None:
                        new_data = np.array([x.calc_value for x in signal.values])
                        if self.is_collecting:
                            self.collected_data.extend(new_data)
                            self.collected_timestamps.extend([time.time()] * len(new_data))
                        self.buffer = np.roll(self.buffer, -len(new_data))
                        self.buffer[-len(new_data):] = new_data
                        self.line1.set_ydata(self.buffer)
                        freq, fft_db = compute_fft(self.buffer, self.data_acq.sample_rate)
                        self.line2.set_ydata(fft_db)
                        self.fig.suptitle('Recording...' if self.is_collecting else 'Press S to start recording', 
                                        color='red' if self.is_collecting else 'black')
            return self.line1, self.line2
        except Exception as e:
            print(f"Error in update_plot: {e}")
            return self.line1, self.line2

    def start_plotting(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.data_acq.ip, self.data_acq.inputport))
        self.fig.suptitle('Press S to start recording', color='black')
        self.fig.text(0.99, 0.01, 'S: Start/Stop Recording | Q: Quit', 
                     ha='right', va='bottom', fontsize=8)
        ani = FuncAnimation(self.fig, self.update_plot, interval=50)
        plt.show()

    def cleanup(self):
        if self.is_collecting:
            self.save_to_file()
        if hasattr(self, 'socket'):
            self.socket.close()
        requests.put(self.data_acq.host + "/rest/rec/measurements/stop")
        requests.put(self.data_acq.host + "/rest/rec/finish")
        requests.put(self.data_acq.host + "/rest/rec/close")

def run_custom_realtime_plot(ip_address, channels_to_enable, target_frequency, acq_time, chunk_size=2**12, save_path="acquired_data"):
    try:
        data_acq = CustomDataAcquisition(ip_address, channels_to_enable, target_frequency, acq_time)
        data_acq.initialize_module()
        plotter = RealTimePlotter(data_acq, save_data=True, save_path=save_path, chunk_size=chunk_size)
        plotter.start_plotting()
    except KeyboardInterrupt:
        print("\nStopping acquisition...")
    finally:
        if 'plotter' in locals():
            plotter.cleanup()

def main():
    ip_address = "169.254.230.53"
    channels_to_enable = [0]
    target_frequency = 51200
    acq_time = 10
    run_custom_realtime_plot(ip_address, channels_to_enable, target_frequency, acq_time)

if __name__ == "__main__":
    main()