import json
import numpy as np
import mne
import pyxdf

# ==================================================
# FILE PATHS
# ==================================================
xdf_path = r"D:\Sheeg\sessions\sub_amir2\ses_20260203_165444\sub-P001\ses-S001\eeg\sub-P001_ses-S001_task-Default_run-001_eeg.xdf"
marker_json_path = r"D:\Sheeg\sessions\sub_amir2\ses_20260203_165444\lsl_stream.json"

# ==================================================
# LOAD CGX EEG AND SCALE TO VOLTS
# ==================================================
def load_cgx_xdf(xdf_path, default_adc_uv=0.195):
    streams, _ = pyxdf.load_xdf(xdf_path)

    eeg_stream = next(
        s for s in streams if s["info"]["type"][0].lower() == "eeg"
    )

    data = np.array(eeg_stream["time_series"]).T.astype(np.float64)
    sfreq = float(eeg_stream["info"]["nominal_srate"][0])
    eeg_times = np.array(eeg_stream["time_stamps"])
    t0 = eeg_times[0]

    ch_names = [ch["label"][0] for ch in eeg_stream["info"]["desc"][0]["channels"][0]["channel"]]

    # Auto-scaling
    peak = np.nanmax(np.abs(data))
    if peak > 1e3:
        data *= default_adc_uv * 1e-6  # ADC counts → volts
        print("Scaling: ADC → volts")
    elif peak > 1:
        data *= 1e-6  # µV → volts
        print("Scaling: µV → volts")
    else:
        print("Data already in volts")

    info = mne.create_info(ch_names, sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data, info, verbose=False)

    # Remove DC offset
    raw._data -= raw._data.mean(axis=1, keepdims=True)
    # Light high-pass filter for visualization
    raw.filter(0.1, None, verbose=False)

    print(f"EEG peak amplitude after scaling: {np.max(np.abs(raw.get_data()))*1e6:.1f} µV")
    return raw, t0

raw, eeg_t0 = load_cgx_xdf(xdf_path)

# ==================================================
# LOAD MARKERS AND ADD AS ANNOTATIONS
# ==================================================
with open(marker_json_path, "r") as f:
    markers = json.load(f)

onsets = []
descriptions = []

for m in markers:
    if "lsl_time" in m:
        onset = m["lsl_time"] - eeg_t0
        if onset < 0:
            continue  # skip markers before EEG start
        label = m["event"]
        if m.get("value"):
            label += f": {m['value']}"
        onsets.append(onset)
        descriptions.append(label)

durations = [0.0] * len(onsets)
annotations = mne.Annotations(onset=onsets, duration=durations, description=descriptions)
raw.set_annotations(annotations)

# ==================================================
# PLOT EEG RAW WITH EVENTS
# ==================================================
raw.plot(
    duration=20,          # seconds per screen
    n_channels=16,        # number of channels visible at once
    scalings=dict(eeg=20e-6),  # µV scaling
    show_scrollbars=True,
    block=True
)
