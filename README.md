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

## Installation

Requirements: 
- Python 3.8+
- packages:
  pip install opcua pandas numpy scipy matplotlib

  ## Directory Structure
  project_root/
│
├─ main.py                  # Main orchestrator
├─ connect.py               # OPC UA connection utility
├─ db_utils.py              # Database creation, insertion, and trend sampling
├─ common_utils.py          # Utility functions (timestamps, CSV writing)
├─ metadata_utils.py        # Probe metadata querying
├─ spectrum_logger.py       # Continuous spectrum logging
├─ processing_utils.py      # Spectrum post-processing and plotting
├─ error_logger.py          # Error logging utilities
├─ ReactIR.db               # SQLite database (generated at runtime)
├─ logs/                    # Log files, raw/processed spectra

## Usage
1. Run the experiment logging system:
  python main.py

This script will: 
- Connect to the OPC UA server.
- Initialise database and error logging.
- Continuously log raw spectra while the probe is running.
- Record trends and peak values.
- Post-process spectra into CSV and plots.

2. Optional: Preview the database

  from main import load_and_preview_db

  load_and_preview_db("ReactIR.db", num_rows=5)

## Key Modules 

