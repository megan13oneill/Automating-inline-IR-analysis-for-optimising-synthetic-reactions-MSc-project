import sqlite3
import os
from datetime import datetime


db_path = "test_probe.db"

def setup_database(db_path="test_probe.db"):
# Connect to SQLite DB
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

# Create tables if they don't exist
        cursor.executescript("""
        -- Create Users table
        CREATE TABLE IF NOT EXISTS Users (
            UserID INTEGER PRIMARY KEY,
            Username TEXT NOT NULL UNIQUE
        );

        -- Create Projects table
        CREATE TABLE IF NOT EXISTS Projects (
            ProjectID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL,
            UserID INTEGER,
            FOREIGN KEY (UserID) REFERENCES Users(UserID)
        );

        -- Create Experiments table
        CREATE TABLE IF NOT EXISTS Experiments (
            ExperimentID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL,
            ProjectID INTEGER,
            FOREIGN KEY (ProjectID) REFERENCES Projects(ProjectID)
        );

        -- Create Documents table
        CREATE TABLE IF NOT EXISTS Documents (
            DocumentID INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL,
            ExperimentID INTEGER,
            FOREIGN KEY (ExperimentID) REFERENCES Experiments(ExperimentID)
        );

        -- Create Probes table
        CREATE TABLE IF NOT EXISTS Probes (
            ProbeID INTEGER PRIMARY KEY,
            Description TEXT NOT NULL,
            DocumentID INTEGER,
            LatestTemperatureCelsius REAL,
            LatestTemperatureTime TEXT,
            FOREIGN KEY (DocumentID) REFERENCES Documents(DocumentID)
        );

        -- Create Samples table
        CREATE TABLE IF NOT EXISTS Samples (
            SampleID INTEGER PRIMARY KEY,
            ProbeID INTEGER,
            SampleCount INTEGER,
            LastSampleTime TEXT,
            CurrentSamplingInterval INTEGER,
            FOREIGN KEY (ProbeID) REFERENCES Probes(ProbeID)
        );

        -- Create Spectra table
        CREATE TABLE IF NOT EXISTS Spectra (
            SpectraID INTEGER PRIMARY KEY,
            SampleID INTEGER,
            Type TEXT CHECK (Type IN ('raw', 'background')),
            FilePath TEXT NOT NULL,
            RecordedAt TEXT,
            FOREIGN KEY (SampleID) REFERENCES Samples(SampleID)
        );

        -- Create Reagents table
        CREATE TABLE IF NOT EXISTS Reagents (
            ReagentID INTEGER PRIMARY KEY,
            DocumentID INTEGER,
            CommonName TEXT NOT NULL,
            InChI TEXT,
            CASNumber TEXT,
            FOREIGN KEY (DocumentID) REFERENCES Documents(DocumentID)
        );
        """)

        conn.commit()
    # conn.close()
        print("Database setup completed.")

def create_new_document(db_path: str, description: str = None) -> int:
    """ Insert a new document entry and return the new DocumentID."""
    timestamp = datetime.now().isoformat()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """ INSERT INTO Documents (Timestamp, Description)
            VALUES (?, ?)
            """,
            (timestamp, description)
        )
        conn.comit()
        return cursor.lastrowid

def get_or_create(cursor, table, unique_col, unique_val, defaults=None):

    """ Get the ID if exists, otherwise insert and return the new ID."""

    table_id_column = f"{table[:-1]}ID" if table.endswith("s") else f"{table}ID"
    cursor.execute(f"SELECT {table_id_column} FROM {table} WHERE {unique_col} = ?", (unique_val,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        columns = [unique_col] + (list(defaults.keys()) if defaults else [])
        values = [unique_val] + (list(defaults.values()) if defaults else [])
        placeholders = ', '.join(['?'] * len(values))
        cursor.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            values
        )
        return cursor.lastrowid

def setup_experiment_metadata(db_path, username, project_name, experiment_name, document_name):

    """ Called once at the start before logging. Returns all parent-level IDs (User, Project, Eperiment, Document.)"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Insert or get each ID
    user_id = get_or_create(cursor, "Users", "Username", username)
    project_id = get_or_create(cursor, "Projects", "Name", project_name, {"UserID": user_id})
    experiment_id = get_or_create(cursor, "Experiments", "Name", experiment_name, {"ProjectID": project_id})
    document_id = get_or_create(cursor, "Documents", "Name", document_name, {"ExperimentID": experiment_id})

    conn.commit()
    conn.close()

    return {
        "UserID": user_id,
        "ProjectID": project_id,
        "ExperimentID": experiment_id,
        "DocumentID": document_id
    }

# during exp - inserting each spectrum + metadata

def insert_probe_sample_and_spectrum(db_path, document_id, metadata_dict, spectrum_csv_path):

    """Called during the experiment for each spectrum to insert. Probe, Sample, Spectrum file path and timestamp."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Insert Probes
        description = metadata_dict.get("Probe Description", "No description")
        cursor.execute("INSERT INTO Probes (Description, DocumentID, LatestTemperatureCelsius, LatestTemperatureTime) VALUES (?, ?, ?, ?)",
            (
                description,
                document_id,
                metadata_dict.get("LatestTemperatureCelsius"),
                metadata_dict.get("LatestTemperatureTime")
            )
        )
        probe_id = cursor.lastrowid

        # 2. Insert Samples
        cursor.execute(
            "INSERT INTO Samples (ProbeID, SampleCount, LastSampleTime, CurrentSamplingInterval) VALUES (?, ?, ?, ?)",
            (
                probe_id,
                metadata_dict.get("Sample Count", 0),
                metadata_dict.get("Last Sample Time", None),
                metadata_dict.get("Current Sampling Interval", None)
            )
        )
        sample_id = cursor.lastrowid

        # 3. Insert Spectrum File Reference
        base = os.path.basename(spectrum_csv_path)
        try:
            ts_str = base.split("_", 2)[2].rsplit('.', 1)[0]
            recorded_at = datetime.strptime(ts_str, "%d-%m-%Y_%H-%M-%S_%f").isoformat()
        except Exception:
            recorded_at = datetime.now().isoformat()

        cursor.execute(
            "INSERT INTO Spectra (SampleID, Type, FilePath, RecordedAt) VALUES (?, ?, ?, ?)",
            (
                sample_id,
                'raw',
                spectrum_csv_path,
                recorded_at
            )
        )

        conn.commit()
        print(f"✅ Inserted metadata + spectrum path: {base}")

    except Exception as e:
        print(f"❌ Error during DB insert: {e}")
        conn.rollback()

    finally:
        conn.close()


