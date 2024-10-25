import numpy as np
from scipy.signal import butter, filtfilt, find_peaks, savgol_filter
from scipy.fft import fft

# -----------------------------------------------------------------------------------------------------------------------
# Optimized Bandpass Filter
def butter_bandpass(lowcut, highcut, fs, order=4):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='bandpass')
    return b, a

def bandpass_filter(signal, lowcut, highcut, fs, order=4):
    if len(signal) < 27:  # Ensure the signal is long enough
        print("Signal too short for filtering.")
        return signal
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    filtered_signal = filtfilt(b, a, signal)
    return filtered_signal

# -----------------------------------------------------------------------------------------------------------------------
# Optimized Heart Rate Calculation
def calculate_heart_rate(filtered_signal, fs):
    
    # Lissage du signal avec un filtre de Savitzky-Golay
    smoothed_signal = savgol_filter(filtered_signal, window_length=11, polyorder=3)
    
    # Detect peaks with minimum distance and height
    peaks, _ = find_peaks(smoothed_signal, distance=fs/2, height=np.mean(smoothed_signal) * 0.7)
    # Check if there are enough peaks for BPM calculation
    if len(peaks) >= 2:
        peak_intervals = np.diff(peaks) / fs  # Time between peaks in seconds
    else :
        peak_intervals =[]
    
    # FFT pour analyser les fréquences
    n = len(smoothed_signal)
    freqs = np.fft.fftfreq(n, d=1/fs)
    fft_values = fft(smoothed_signal)

    # Filtrer les fréquences positives
    positive_freqs = freqs[:n // 2]
    positive_fft_values = np.abs(fft_values[:n // 2])

    # Trouver la fréquence dominante dans le signal FFT
    dominant_freq_index = np.argmax(positive_fft_values)
    dominant_freq = positive_freqs[dominant_freq_index]
    avg_bpm = dominant_freq * 60   # Conversion en BPM
    
    return avg_bpm , peak_intervals, peaks


# def calculate_heart_rate(filtered_signal, fs):
    
#     # Lissage du signal avec un filtre de Savitzky-Golay
#     smoothed_signal = savgol_filter(filtered_signal, window_length=11, polyorder=3)
    
#     # Detect peaks with minimum distance and height
#     peaks, _ = find_peaks(smoothed_signal, distance=fs/3, height=np.mean(smoothed_signal) * 0.6)
#     # Check if there are enough peaks for BPM calculation
#     if len(peaks) >= 2:
#         peak_intervals = np.diff(peaks) / fs  # Time between peaks in seconds
#     else :
#         peak_intervals =[]
    
#     # FFT pour analyser les fréquences
#     n = len(smoothed_signal)
#     freqs = np.fft.fftfreq(n, d=1/fs)
#     fft_values = fft(smoothed_signal)

#     # Filtrer les fréquences positives
#     positive_freqs = freqs[:n // 2]
#     positive_fft_values = np.abs(fft_values[:n // 2])

#     # Only consider frequencies between 0.67 Hz (40 BPM) and 3.33 Hz (200 BPM) et Trouver la fréquence dominante dans le signal FFT
#     valid_freq_indices = np.where((positive_freqs >= 0.67) & (positive_freqs <= 3.33))[0]
#     dominant_freq_index = valid_freq_indices[np.argmax(positive_fft_values[valid_freq_indices])]
#     dominant_freq = positive_freqs[dominant_freq_index]
#     avg_bpm = dominant_freq * 60  # Convert to BPM
#     # print('le frequence est :', avg_bpm)
#     return avg_bpm , peak_intervals, peaks

# -----------------------------------------------------------------------------------------------------------------------
# HRV (Heart Rate Variability) Calculation
def calculate_hrv(peak_intervals):
    if len(peak_intervals) < 2:
        return 0, 0, 0  # Return zeros if not enough data
    mean_rr = np.mean(peak_intervals)  # Mean of intervals
    sdnn = np.std(peak_intervals)      # Standard deviation
    rmssd = np.sqrt(np.mean(np.diff(peak_intervals)**2))  # RMSSD (root mean square of successive differences)
    return mean_rr, sdnn, rmssd

# -----------------------------------------------------------------------------------------------------------------------
# Stress Level Based on HRV
def calculate_stress_level(peak_intervals):
    if len(peak_intervals) < 2:
        return "Insufficient data"
    rmssd = np.sqrt(np.mean(np.diff(peak_intervals * 1000)**2))  # Convert intervals to ms
    if rmssd > 50:
        return "Very low stress"
    elif 30 <= rmssd < 50:
        return "Mild stress"
    elif 15 <= rmssd <= 30:
        return "Moderate stress"
    else:
        return "High stress"

# -----------------------------------------------------------------------------------------------------------------------
# Blood Pressure Calculation (Basic Estimate)
def calculate_blood_pressure(peak_intervals):
    if len(peak_intervals) < 2:
        return None, None
    systolic_pressure = 85 + (np.mean(peak_intervals) * 40)
    diastolic_pressure = 50 + (np.mean(peak_intervals) * 20)
    return systolic_pressure, diastolic_pressure

# -----------------------------------------------------------------------------------------------------------------------
# SpO2 Calculation Based on Red and Infrared Signals
def calculate_spo2(red_signal, infra_signal, fs):
    def calculate_ac_dc(signal):
        dc = np.mean(signal)
        ac = signal - dc
        return ac, dc
    # Filter signals
    filtered_red = bandpass_filter(red_signal, 0.85, 2.3, fs)
    filtered_infra = bandpass_filter(infra_signal, 0.85, 2.3, fs)
    if len(filtered_red) < 27 or len(filtered_infra) < 27:
        print("Not enough data for SpO2 calculation.")
        return 0
    ac_red, dc_red = calculate_ac_dc(filtered_red)
    ac_infra, dc_infra = calculate_ac_dc(filtered_infra)
    if dc_infra == 0 or dc_red == 0:
        return 0
    r_value = (np.mean(np.abs(ac_red)) / dc_red) / (np.mean(np.abs(ac_infra)) / dc_infra)
    spo2 = 100 - 2 * r_value
    return max(0, min(98, spo2))  # SpO2 should be between 0 and 100%

# -----------------------------------------------------------------------------------------------------------------------
# Respiration Rate Calculation
def calculate_respiration_rate(filtered_signal, fs):
    smoothed_signal = savgol_filter(filtered_signal, window_length=11, polyorder=3)
    peaks_respiration, _ = find_peaks(smoothed_signal, distance=fs * 2, height=np.mean(smoothed_signal) * 0.7)
    peak_interval_respiration = np.diff(peaks_respiration) / fs
    if len(peak_interval_respiration) == 0:
        return 0
    avg_breaths_per_minute = 60 / np.mean(peak_interval_respiration)
    return avg_breaths_per_minute

# -----------------------------------------------------------------------------------------------------------------------
# Signal Strength Verification (Ensure valid PPG signal)
def verify_signal_strength(signal, threshold=0.1):
    signal_range = np.max(signal) - np.min(signal)
    return signal_range > threshold
