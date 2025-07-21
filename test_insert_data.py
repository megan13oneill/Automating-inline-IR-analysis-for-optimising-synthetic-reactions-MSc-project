from db_utils import setup_database  # or from db_utils if you put it there
from db_utils import insert_probe_sample_and_spectrum
import sqlite3
import os

# Set the test database path
db_path = "test_probe.db"

# Remove any old version
if os.path.exists(db_path):
    os.remove(db_path)

# Step 1: Set up the database schema
setup_database(db_path)

# Step 2: Insert a dummy document
with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Documents (DocumentID, Name, ExperimentID) VALUES (?, ?, ?)", (1, 'TestDoc', None))
    conn.commit()

# Step 3: Prepare metadata and fake spectrum
metadata = {
    "ProbeTemperatureCelsius": 25.0,
    "LastUpdatedTime": "2025-07-21T15:00:00Z",
    "CurrentSamplingInterval": 1000
}

document_ids = {"DocumentID": 1}

spectrum_csv_path = "test_spectrum.csv"
with open(spectrum_csv_path, "w") as f:
    f.write("wavenumber,transmittance\n")
    f.write("4000,50\n")
    f.write("3999,51\n")

# Step 4: Call your insert function
try:
    insert_probe_sample_and_spectrum(
        db_path=db_path,
        document_id=document_ids["DocumentID"],
        metadata_dict=metadata,
        spectrum_csv_path=spectrum_csv_path
    )
    print("✅ Data inserted successfully.")
except Exception as e:
    print(f"❌ Error during insert: {e}")

# Step 5: Confirm the data is there
with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Samples;")
    print("Samples:", cursor.fetchone()[0])
    cursor.execute("SELECT COUNT(*) FROM Spectra;")
    print("Spectra:", cursor.fetchone()[0])
