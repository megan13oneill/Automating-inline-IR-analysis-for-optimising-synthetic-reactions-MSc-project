import os
import sqlite3
import tempfile
import csv
from db_utils import insert_probe_sample_and_spectrum

def create_dummy_csv(file_path):
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['wavenumber', 'transmittance'])
        for i in range(4000, 650, -10):  # Simulated descending wavenumber
            writer.writerow([i, 100 - i % 100])  # Dummy transmittance data

def setup_temp_db():
    # Create a temporary SQLite DB
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Simulate your expected schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS probe_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT,
            metadata_key TEXT,
            metadata_value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spectra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id INTEGER,
            wavenumber REAL,
            transmittance REAL,
            FOREIGN KEY (sample_id) REFERENCES probe_samples(id)
        )
    """)
    conn.commit()
    return conn

def test_insert_probe_sample_and_spectrum():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up temp CSV file
        csv_path = os.path.join(tmpdir, "dummy_spectrum.csv")
        create_dummy_csv(csv_path)

        # Simulate metadata and document ID
        dummy_metadata = {
            "Product Name": "TestChemical",
            "Operator": "TestUser",
            "Batch Number": "ABC123"
        }
        document_id = "DOC-TEST-001"

        # Set up in-memory DB and patch db_path in function
        conn = setup_temp_db()

        # Monkey patch insert function to use our in-memory DB
        def patched_insert(**kwargs):
            kwargs["db_path"] = ":memory:"
            insert_probe_sample_and_spectrum(**kwargs)

        # Write a version of insert function that uses the in-memory conn
        insert_probe_sample_and_spectrum(
            db_path=":memory:",
            document_id=document_id,
            metadata_dict=dummy_metadata,
            spectrum_csv_path=csv_path,
            conn=conn  # assuming you modify your insert function to accept this
        )

        # Validate inserts
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM probe_samples")
        print("Sample rows:", cursor.fetchone()[0])

        cursor.execute("SELECT COUNT(*) FROM spectra")
        print("Spectrum rows:", cursor.fetchone()[0])

        # Cleanup
        conn.close()

if __name__ == "__main__":
    test_insert_probe_sample_and_spectrum()
