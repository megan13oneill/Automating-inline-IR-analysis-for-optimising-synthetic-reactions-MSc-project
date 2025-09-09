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

  ```pip install opcua pandas numpy scipy matplotlib```

  ## Directory Structure
  ```project_root/
│
├─ main.py                   (Main orchestrator)

├─ connect.py                (OPC UA connection utility)

├─ db_utils.py               (Database creation, insertion, and trend sampling)

├─ common_utils.py           (Utility functions (timestamps, CSV writing))

├─ metadata_utils.py         (Probe metadata querying)

├─ spectrum_logger.py        (Continuous spectrum logging)

├─ processing_utils.py       (Spectrum post-processing and plotting)

├─ error_logger.py           (Error logging utilities)

├─ ReactIR.db                (SQLite database (generated at runtime))

├─ logs/                     (Log files, raw/processed spectra)


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
connect.py
Handles OPC UA server connection with retry logic and error logging.

db_utils.py
Creates and manages the SQLite database.
Inserts probe, sample, spectra, and trend data.
Handles real-time sampling and batch inserts for trends and peaks.

common_utils.py
Timestamp generation for file naming.
CSV writing for spectral data.

metadata_utils.py
Retrieves metadata from Probe1 node (e.g., experiment name, temperatures, spectra info).

spectrum_logger.py
Continuous logging of raw and optionally treated spectra.
Supports dynamic sampling intervals.
Inserts spectra into the database with associated probe/sample metadata.

processing_utils.py
Post-processes CSV spectra.
Optional smoothing using the Savitzky-Golay filter.
Generates plots (PDF and PNG) of transmittance vs wavenumber.

error_logger.py
Centralised error logging system.
Configurable log paths.
Captures stack traces and context messages.

## Database Schema
Key tables:
- Users, Projects, Experiments, Documents
- Probes, Samples, Spectra
- Trends, ProbeTempSamples, PeakSamples
- Reagents
Indexes and PRAGMA settings are included for improved performance and concurrency.

## Error Handling
- Errors are logged in a dedicated .txt file under logs/.
- The logger captures:
  - Context messages
  - Exception messages
  - Stack traces
- Errors do not stop logging; the system attempts to continue when possible.


## Example Workflow
1. Connect to the OPC UA server.
2. Verify trends node readiness.
3. Retrieve probe metadata.
4. Start a new trend in the database.
5. Begin continuous spectrum logging and trend sampling.
6. Stop logging manually or when the probe status indicates completion.
7. Post-process collected spectra (optional smoothing & plotting).

## Notes
- Ensure the OPC UA server endpoint is correctly set in connect.py.
- Database file (ReactIR.db) is created automatically if it does not exist.
- All logs and processed data are organised under logs/<experiment_name>/.

## Licence
The project is open-source and can be modified for research or industrial IR probe logging.
