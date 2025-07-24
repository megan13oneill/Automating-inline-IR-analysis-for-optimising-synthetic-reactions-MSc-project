import sqlite3
import os
from datetime import datetime
import time
from opcua import Client


db_path = "ReactIR.db"

def setup_database(db_path="ReactIR.db"):
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

        -- Create Trends table (represents a collection session e.g. user selects "Start Recording')
        CREATE TABLE IF NOT EXISTS Trends (
            TrendID INTEGER PRIMARY KEY AUTOINCREMENT,
            DocumentID INTEGER,
            StartTime TEXT,
            EndTime TEXT,
            Usernote TEXT,
            FOREIGN KEY (DocumentID) REFERENCES Documents(DocumentID)
        );

        -- Create Probe Temps table linked to Trends (Stores time-series probe data linked to a trend)
        CREATE TABLE IF NOT EXISTS ProbeTempSamples (
            SampleID INTEGER PRIMARY KEY AUTOINCREMENT,
            TrendID INTEGER,
            Timestamp TEXT,
            Description TEXT,
            Source TEXT,
            Value REAL,
            TreatedValue REAL,
            FOREIGN KEY (TrendID) REFERENCES Trends(TrendID)
        );
        
        -- Create Peak table (stores time-series user peak data (multiple OPC nodes per sample))
        CREATE TABLE IF NOT EXISTS PeakSamples (
            SampleID INTEGER PRIMARY KEY AUTOINCREMENT,
            TrendID integer,
            Timestamp TEXT,
            NodeID TEXT,
            Value REAL,
            Label TEXT,
            FOREIGN KEY (TrendID) REFERENCES Trends(TrendID)
        );
        """)

        conn.commit()
    # conn.close()
        print("Database setup completed.")

def create_new_document(db_path: str, name: str, experiment_id: int) -> int:
    """ Insert a new document entry and return the new DocumentID."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """ INSERT INTO Documents (Name, ExperimentID) VALUES (?, ?)""",
            (name, experiment_id)
        )
        conn.commit()
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

def create_new_trend(db_path, document_id, user_note=("")):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Trends (DocumentID, StartTime, UserNote)
        VALUES (?, ?, ?)
    """, (document_id, datetime.now().isoformat(), user_note))
    trend_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trend_id

def start_trend_sampling(db_path, trend_id, probe_node, treated_node, probe_description, peak_nodes, interval_sec=2):
    
    """ Samples both probe and peak values at a fixed interval and stores in db."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print("Sampling started ... Press Ctrl + C to stop.")

    try:
        while True:
            timestamp = datetime.now().isoformat()

            # Read probe temp
            probe_value = probe_node.get_value()
            treated_value = treated_node.get_value()

            cursor.execute("""
                INSERT INTO ProbeTempSamples (TrendID, Timestamp, Description, Source, Value, TreatedValue)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                trend_id,
                timestamp,
                probe_description, 
                probe_node.nodeid.to_string(),
                probe_value,
                treated_value
            ))

            for node_obj, label in peak_nodes:
                peak_val = node_obj.get_value()
                cursor.execute("""
                    INSERT INTO PeakSamples (TrendID, Timestamp, NodeID, Value, Label)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    trend_id,
                    timestamp,
                    node_obj.nodeid.to_string(),
                    peak_val,
                    label
                ))

            conn.commit()
            time.sleep(interval_sec)
       
    except KeyboardInterrupt:
        print("Sampling stopped.")
        end_time = datetime.now().isoformat()
        cursor.execute("UPDATE Trends SET EndTime = ? WHERE TrendID = ?", (end_time, trend_id))
        conn.commit()
    
    except Exception as e: 
        print(f"Error during sampling: {e}")
        conn.rollback()

    finally:
        conn.close()




