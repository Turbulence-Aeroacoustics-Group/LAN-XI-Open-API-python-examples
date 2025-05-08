#!/usr/bin/env python3
"""
FFT Analysis module for LAN-XI data.
Provides functions for computing and plotting FFT of time-domain signals.
"""

import numpy as np
import matplotlib.pyplot as plt
from custom_realtime_plot import CustomDataAcquisition
import requests
import argparse
from scipy.signal import welch
from fft_utils import compute_pwelch


def compute_fft(data, sample_rate, window='hamming'):
    """
    Compute FFT of time-domain data.
    """
    if window == 'hamming':
        win = np.hamming(len(data))
    elif window == 'hanning':
        win = np.hanning(len(data))
    elif window == 'blackman':
        win = np.blackman(len(data))
    elif window == 'rectangular':
        win = np.ones(len(data))
    else:
        raise ValueError(f"Unsupported window type: {window}")
    fft_data = np.fft.rfft(data * win)
    fft_db = 20 * np.log10(np.abs(fft_data))
    freq = np.fft.rfftfreq(len(data), 1/sample_rate)
    return freq, fft_db

def plot_fft(data, sample_rate, window='hamming', ax=None, **plot_kwargs):
    """
    Compute and plot FFT of time-domain data.
    """
    freq, fft_db = compute_fft(data, sample_rate, window)
    if ax is None:
        ax = plt.gca()
    line = ax.plot(freq, fft_db, **plot_kwargs)[0]
    ax.set_xlim(0, max(freq))
    ax.set_ylim(-120, 0)
    ax.grid(True)
    ax.set_xlabel('Frequency [Hz]')
    ax.set_ylabel('Amplitude [dB]')
    return line

def plot_spectrogram(data, sample_rate, window_size=2**12, overlap=0.5, window='hamming'):
    """
    Compute and plot spectrogram of time-domain data.
    """
    plt.figure(figsize=(10, 6))
    if window == 'hamming':
        win = np.hamming(window_size)
    elif window == 'hanning':
        win = np.hanning(window_size)
    elif window == 'blackman':
        win = np.blackman(window_size)
    else:
        win = np.ones(window_size)
    plt.specgram(data, NFFT=window_size, Fs=sample_rate, window=win, 
                noverlap=int(window_size*overlap), cmap='viridis')
    plt.xlabel('Time [s]')
    plt.ylabel('Frequency [Hz]')
    plt.colorbar(label='Amplitude [dB]')
    plt.title('Spectrogram')


def compute_pwelch(data, sample_rate, nperseg=None):
    """
    Compute PSD using Welch's method and return frequency and dB values.
    """
    if nperseg is None:
        nperseg = min(1024, len(data))
    freq, psd = welch(data, fs=sample_rate, nperseg=nperseg)
    psd_db = 10 * np.log10(psd + 1e-20)
    return freq, psd_db


def run_fft_analyzer(ip, channels, frequency):
    try:
        data_acq = CustomDataAcquisition(ip, channels, frequency)
        data_acq.initialize_module()
        actual_sample_rate = data_acq.sample_rate
        print(f"Using sample rate: {actual_sample_rate} Hz")
        duration = 0.1
        t = np.linspace(0, duration, int(duration * actual_sample_rate))
        f1, f2 = 1000, 5000
        signal = np.sin(2*np.pi*f1*t) + 0.5*np.sin(2*np.pi*f2*t)
        plt.figure(figsize=(12, 8))
        plt.subplot(211)
        plt.plot(t, signal)
        plt.xlabel('Time [s]')
        plt.ylabel('Amplitude')
        plt.title(f'Time Domain Signal (Sample Rate: {actual_sample_rate} Hz)')
        plt.grid(True)
        plt.subplot(212)
        plot_fft(signal, actual_sample_rate)
        plt.title('Frequency Domain')
        plt.tight_layout()
        plt.show()
        plot_spectrogram(signal, actual_sample_rate)
        plt.title(f'Spectrogram (Sample Rate: {actual_sample_rate} Hz)')
        plt.show()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'data_acq' in locals():
            requests.put(data_acq.host + "/rest/rec/measurements/stop")
            requests.put(data_acq.host + "/rest/rec/finish")
            requests.put(data_acq.host + "/rest/rec/close")

def main():
    parser = argparse.ArgumentParser(description='FFT Analysis example')
    parser.add_argument('--ip', default='169.254.230.53', help='IP address of the LAN-XI device')
    parser.add_argument('--channels', type=str, default='0', help='Comma-separated list of channels')
    parser.add_argument('--frequency', type=int, default=51200, help='Target sampling frequency in Hz')
    args = parser.parse_args()
    channels = [int(ch.strip()) for ch in args.channels.split(',')]
    run_fft_analyzer(args.ip, channels, args.frequency)




if __name__ == "__main__":
    main()