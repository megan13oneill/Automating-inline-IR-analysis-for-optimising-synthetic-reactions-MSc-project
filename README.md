# Automating-inline-IR-analysis-for-optimising-synthetic-reactions-MSc-project
# ReactIR OPC UA Logging System
## Overview

ReactIR is a Python-based system for automated logging, storage, and processing of infrared (IR) spectra from Mettler Toledo IR flow cells via OPC UA. The system connects to an OPC UA server, retrieves live probe data, logs raw and processed spectra, and stores them in an SQLite database with detailed experiment metadata.
The system supports real-time sampling of probe data, spectral acquisition, error logging, and post-processing (smoothing, plotting, and CSV export).

## Features
- Connects to an OPC UA server for Mettler Toledo IR probes.
- Real-time probe monitoring and sampling.
- Raw spectrum logging and optional treated spectrum logging.
- Automatic database storage with metadata hierarchy:
- Users → Projects → Experiments → Documents → Probes → Samples → Spectra → Trends → ProbeTempSamples → PeakSamples.
- Error logging with configurable file paths.
- Post-processing of spectra:
  - CSV export.
  - Smoothing with the Savitzky-Golay filter.
  - High-resolution plots (PNG and PDF).
