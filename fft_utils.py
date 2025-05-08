import numpy as np

def compute_pwelch(data, sample_rate, nperseg=1024, noverlap=None):
    """
    Compute the Power Spectral Density (PSD) using Welch's method.
    """
    from scipy.signal import welch
    if noverlap is None:
        noverlap = nperseg // 2
    freq, psd = welch(data, fs=sample_rate, nperseg=nperseg, noverlap=noverlap)
    psd_db = 10 * np.log10(psd)
    return freq, psd_db