import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import scipy.signal as signal

# Candidate EEG channel names
EEG_CHANNELS = [
    "Fz", "Cz", "P3", "C3", "F3", "F4", "C4", "P4", "Fp1", "Fp2",
    "T3", "T4", "T5", "T6", "O1", "O2", "F7", "F8", "A1", "A2", "Pz"
]
IGNORE_KEYWORDS = ["X3", "Trigger", "Time_Offset", "ADC_Status",
                   "ADC_Sequence", "Event", "Comments"]

# Streamlit page setup
st.set_page_config(
    page_title="EEG & ECG Viewer",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom CSS
try:
    with open("style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except Exception:
    pass

# App header
st.markdown("""
<div class="header">
  <h1>EEG & ECG Interactive Viewer</h1>
  <p>Upload a CSV file (with metadata lines starting with '#') and inspect signals interactively.</p>
</div>
""", unsafe_allow_html=True)

# File uploader
uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

if uploaded_file:
    # Load CSV (skip metadata lines)
    df = pd.read_csv(uploaded_file, comment="#")

    # Detect time column
    time_col = None
    for c in ["Time", "time", "Seconds", "seconds"]:
        if c in df.columns:
            time_col = c
            break
    if time_col is None:
        for c in df.columns:
            if np.issubdtype(df[c].dtype, np.number):
                time_col = c
                break
    if not time_col:
        st.error("❌ Could not find a Time column in this file.")
        st.stop()

    # Detect EEG, ECG, CM channels
    eeg = [c for c in df.columns if c in EEG_CHANNELS and not any(k in c for k in IGNORE_KEYWORDS)]
    ecg = [c for c in df.columns if ("X1" in c or "X2" in c or "LEOG" in c.upper() or "REOG" in c.upper())
           and not any(k in c for k in IGNORE_KEYWORDS)]
    cm_col = "CM" if "CM" in df.columns else None

    # Sidebar options
    st.sidebar.header("⚙️ Plot Options")
    selected_eeg = st.sidebar.multiselect("EEG Channels", eeg, default=eeg[:5])
    selected_ecg = st.sidebar.multiselect("ECG Channels", ecg, default=ecg)
    include_cm = st.sidebar.checkbox("Include CM", value=bool(cm_col))
    eeg_units = st.sidebar.radio("EEG Units", ["µV", "mV"], horizontal=True)

    time = df[time_col].values

    # Colors
    eeg_colors = ["#c1121f", "#ff4d6d", "#ba181b", "#e5383b", "#f07167"]
    ecg_colors = ["#d00000", "#e85d04"]
    cm_color = "#6c757d"

    # Build figure
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # EEG traces
    for i, ch in enumerate(selected_eeg):
        y = df[ch].values
        if eeg_units == "mV":
            y = y / 1000.0
        fig.add_trace(
            go.Scatter(
                x=time, y=y,
                mode="lines",
                name=f"{ch} ({eeg_units})",
                line=dict(width=1.6, color=eeg_colors[i % len(eeg_colors)]),
                hovertemplate=f"{ch} ({eeg_units}): %{{y:.3f}}<br>t=%{{x}}s"
            ),
            secondary_y=False
        )

    # ECG traces
    for i, ch in enumerate(selected_ecg):
        y = df[ch].values / 1000.0
        fig.add_trace(
            go.Scatter(
                x=time, y=y,
                mode="lines",
                name=f"{ch} (mV)",
                line=dict(width=2, color=ecg_colors[i % len(ecg_colors)]),
                hovertemplate=f"{ch} (mV): %{{y:.3f}}<br>t=%{{x}}s"
            ),
            secondary_y=True
        )

    # CM trace
    if include_cm and cm_col:
        y = df[cm_col].values / 1000.0
        fig.add_trace(
            go.Scatter(
                x=time, y=y,
                mode="lines",
                name=f"{cm_col} (mV)",
                line=dict(width=1.5, dash="dot", color=cm_color),
                hovertemplate=f"{cm_col} (mV): %{{y:.3f}}<br>t=%{{x}}s"
            ),
            secondary_y=True
        )

    # Layout
    fig.update_layout(
        title=dict(
            text="EEG & ECG Time-Series Viewer",
            x=0.5, xanchor="center", font=dict(size=20, color="#ba181b")
        ),
        xaxis=dict(
            title=dict(
                text="Time (s)",
                font=dict(size=13, color="black")   # 👈 axis title font/color
            ),
            rangeslider=dict(visible=True),
            tickfont=dict(size=11, color="black"),
            showline=True, linecolor="black", linewidth=1, mirror=True,
            ticks="outside", ticklen=6
        ),
        yaxis=dict(
            title=dict(
                text=f"EEG ({eeg_units})",
                font=dict(size=13, color="black")   # 👈 axis title font/color
            ),
            tickfont=dict(size=11, color="black"),
            showline=True, linecolor="black", linewidth=1, mirror=True,
            ticks="outside", ticklen=6,
            gridcolor="rgba(0,0,0,0.05)"
        ),
        yaxis2=dict(
            title="ECG / CM (mV)",
            overlaying="y", side="right",
            tickfont=dict(size=11, color="black"),
            showline=True, linecolor="black", linewidth=1, mirror=True,
            ticks="outside", ticklen=6,
            gridcolor="rgba(0,0,0,0.05)"
        ),
        legend=dict(
            orientation="h",
            yanchor="top", y=-0.25,
            xanchor="center", x=0.5,
            bgcolor="rgba(255,255,255,0.98)",
            bordercolor="lightgrey", borderwidth=1,
            font=dict(size=11, color="black")
        ),
        hovermode="x unified",
        template="simple_white",
        margin=dict(t=80, b=120, l=60, r=60),
        height=700,
        plot_bgcolor="white",
        paper_bgcolor="white"
    )

    # Show chart
    st.plotly_chart(fig, use_container_width=True)

    # =======================
    # Automated Report
    # =======================
    st.subheader("📊 Automated Signal Report")

    report = []

    # --- ECG irregularity check ---
    if selected_ecg:
        ecg_data = df[selected_ecg[0]].values / 1000.0
        peaks, _ = signal.find_peaks(ecg_data, distance=200)
        if len(peaks) > 1:
            rr_intervals = np.diff(time[peaks])
            avg_interval = np.mean(rr_intervals)
            report.append(f"ECG: Average beat interval = {avg_interval:.2f} seconds")
            if np.std(rr_intervals) > 0.15:
                report.append("⚠️ ECG shows irregular beat spacing (variable timing).")
        else:
            report.append("ECG: Not enough peaks detected for analysis.")

    # --- EEG irregularity check ---
    if selected_eeg:
        for ch in selected_eeg:
            data = df[ch].values
            if eeg_units == "mV":
                data = data * 1000
            mean_val, std_val = np.mean(data), np.std(data)
            spikes = np.where(np.abs(data - mean_val) > 5 * std_val)[0]
            if len(spikes) > 0:
                report.append(f"EEG {ch}: {len(spikes)} unusual high-amplitude events detected.")
            else:
                report.append(f"EEG {ch}: No unusual events detected.")

    if report:
        st.markdown("### 📝 Machine-Generated Summary")
        for line in report:
            st.write("- " + line)
        report_text = "\n".join(report)
        st.download_button("⬇️ Download Report", data=report_text, file_name="session_report.txt")
    else:
        st.write("✅ No unusual signal behavior detected.")
else:
    st.info("👆 Upload a CSV to begin.")
