import sqlite3
import os
from datetime import datetime
import time
from opcua import Client
import traceback

from error_logger import log_error_to_file

db_path = "ReactIR.db"
PROBE_COLUMNS = ["Description", "DocumentID", "LatestTemperatureCelsius", "LatestTemperatureTime"]
SAMPLE_COLUMNS = ["ProbeID", "SampleCount", "LastSampleTime", "CurrentSamplingInterval"]
SPECTRA_COLUMNS = ["SampleID", "Type", "FilePath", "RecordedAt"]

def setup_database(db_path="ReactIR.db"):
    try:
        # Connect to SQLite DB
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
        
        # PRAGMA commands to boost performance.
        cursor.execute("PRAGMA journal_mode=WAL;") # better concurrency
        cursor.execute("PRAGMA synchronous=NORMAL;") # faster writes, still resonably safe
        cursor.execute("PRAGMA temp_store=MEMORY;") # Temp tables stay in RAM

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
            ErrorLogPath TEXT,
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
            Type TEXT CHECK (Type IN ('raw', 'background', 'processed', 'reference')),
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

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_probe_temp_trend ON ProbeTempSamples (TrendID;)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_peak_samples_trend ON PeakSamples (TrendID;)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_probe_temp_timestamp ON ProbeTempSamples (Timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_peak_samples_timestamp ON PeakSamples (Timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_experiment ON Documents (ExperimentID);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_probes_document ON Probes (DocumentID);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trends_document ON Trends (DocumentID);")

        conn.commit()
        print("Database setup completed.")

    except Exception as e: 
        log_error_to_file(e, "Error in setup_database()")

def create_new_document(db_path: str, name: str, experiment_id: int, error_log_path=None) -> int:
    """ Insert a new document entry and return the new DocumentID."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """ INSERT INTO Documents (Name, ExperimentID, ErrorLogPath) VALUES (?, ?, ?)""",
                (name, experiment_id, error_log_path)
            )
            conn.commit()
            document_id = cursor.lastrowid
            conn.close()
            return document_id
    except Exception as e:
        log_error_to_file(e, "Error in create_new_document()")
        return -1

def get_or_create(cursor, table, unique_col, unique_val, defaults=None):
    """ Get the ID if exists, otherwise insert and return the new ID."""
    
    try: 
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
    except Exception as e: 
        log_error_to_file(e, f"Error in get_or_create() for table '{table}' with value '{unique_val}'")
        raise

def setup_experiment_metadata(db_path, username, project_name, experiment_name, document_name):
    """ Called once at the start before logging. Returns all parent-level IDs (User, Project, Eperiment, Document.)"""
    try: 
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
    except Exception as e:
        log_error_to_file(e, "Error in setup_experiment_metadata()")
        return {}

# during exp - inserting each spectrum + metadata
def insert_probe_sample_and_spectrum(db_path, document_id, metadata_dict, spectrum_csv_path):
    """Called during the experiment for each spectrum to insert. Probe, Sample, Spectrum file path and timestamp."""

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
       
            # Prepare probe data to be inserted. 
            probe_values = [
                metadata_dict.get("Probe Description", "No description"),
                document_id,
                metadata_dict.get("LatestTemperatureCelsius"),
                metadata_dict.get("LatestTemperatureTime")
            ]
            probe_sql = f"INSERT INTO Probes ({', '.join(PROBE_COLUMNS)}) VALUES ({', '.join('?' for _ in PROBE_COLUMNS)})"
            cursor.execute(probe_sql, probe_values)
            probe_id = cursor.lastrowid

            # Prepare values for Samples
            sample_values = [
                probe_id,
                metadata_dict.get("Sample Count", 0),
                metadata_dict.get("Last Sample Time"),
                metadata_dict.get("Current Sampling Interval")
            ]
            sample_sql = f"INSERT INTO Samples ({', '.join(SAMPLE_COLUMNS)}) VALUES ({', '.join('?' for _ in SAMPLE_COLUMNS)})"
            cursor.execute(sample_sql, sample_values)
            sample_id = cursor.lastrowid

        # Extract timestamp from filename, fallback to now
        try:
            base = os.path.basename(spectrum_csv_path)
            ts_str = base.split("_", 2)[2].rsplit('.', 1)[0]
            recorded_at = datetime.strptime(ts_str, "%d-%m-%Y_%H-%M-%S_%f").isoformat()
        except Exception:
                recorded_at = datetime.now().isoformat()

        # Insert spectrum
        spectra_values = [
            sample_id,
            "raw",
            spectrum_csv_path,
            recorded_at
        ]
        spectral_sql = f"INSERT INTO Spectra ({', '.join(SPECTRA_COLUMNS)}) VALUES  ({', '.join('?' for _ in SPECTRA_COLUMNS)})"
        cursor.execute(spectral_sql, spectra_values)

        conn.commit()
        print(f"✅ Inserted 1 spectrum for DocumentID {document_id}.")

    except Exception as e:
        log_error_to_file(e, "Error in insert_probe_samples_and_spectra_batch()")
        print(f"❌ Error during inserting spectrum: {e}")

    finally:
        conn.close()

def create_new_trend(db_path, document_id, user_note=("")):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Trends (DocumentID, StartTime, Usernote)
            VALUES (?, ?, ?)
        """, (document_id, datetime.now().isoformat(), user_note))
        trend_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return trend_id
    except Exception as e: 
        log_error_to_file(e, "Error in create_new_trend()")
        return -1
    finally:
        conn.close()

def start_trend_sampling(db_path, trend_id, probe_node, treated_node, probe_description, peak_nodes, interval_sec=2, batch_size=1):
    """ Samples both probe and peak values at a fixed interval and stores in db."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    print("Sampling started ... Press Ctrl + C to stop.")

    insert_count = 0
    probe_temp_buffer = []
    peak_sample_buffer= []

    try:
        while True:
            timestamp = datetime.now().isoformat()

            # Read probe temp
            probe_value = probe_node.get_value()
            treated_value = treated_node.get_value()

            probe_temp_buffer.append((
                trend_id,
                timestamp,
                probe_description, 
                probe_node.nodeid.to_string(),
                probe_value,
                treated_value
            ))

            for node_obj, label in peak_nodes:
                peak_val = node_obj.get_value()
                peak_sample_buffer.append((
                    trend_id,
                    timestamp,
                    node_obj.nodeid.to_string(),
                    peak_val,
                    label
                ))

            if len(probe_temp_buffer) >= batch_size:
                cursor.executemany("""
                    INSERT INTO ProbeTempSamples (TrendID, Timestamp, Description, Source, Value, TreatedValue)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, probe_temp_buffer)

                cursor.executemany("""
                    INSERT INTO PeakSamples (TrendID, Timestamp, NodeID, Value, Label)
                    VALUES (?, ?, ?, ?, ?)
                """, peak_sample_buffer)

                conn.commit()
                probe_temp_buffer.clear()
                peak_sample_buffer.clear()

            time.sleep(interval_sec)

    except KeyboardInterrupt:
        print("Sampling stopped.")
        # Flush remaining
        if probe_temp_buffer:
            cursor.executemany("""
                INSERT INTO ProbeTempSamples (TrendID, Timestamp, Description, Source, Value, TreatedValue)
                VALUES (?, ?, ?, ?, ?, ?)
            """, probe_temp_buffer)

        if peak_sample_buffer:
            cursor.executemany("""
                INSERT INTO PeakSamples (TrendID, Timestamp, NodeID, Value, Label)
                VALUES (?, ?, ?, ?, ?)
            """, peak_sample_buffer)

        conn.commit()

        end_time = datetime.now().isoformat()
        cursor.execute("UPDATE Trends SET EndTime = ? WHERE TrendID = ?", (end_time, trend_id))
        conn.commit()

    except Exception as e:
        log_error_to_file(e, "Error in start_trend_sampling()")
        print(f"Error during sampling: {e}")
        conn.rollback()

    finally:
        conn.close()

def end_trend(db_path, trend_id):
    """ Marks the end of trend with a timestamp."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            end_time = datetime.now().isoformat()
            cursor.execute(
                "UPDATE Trends SET EndTime = ? WHERE TrendID = ?",
                (end_time, trend_id)
            )
            conn.commit()
            print(f"Trend {trend_id} marked as ended at {end_time}.")
    except Exception as e: 
        log_error_to_file(e, f"Error in end_trend() for TrendID {trend_id}")
        print(f"Failed to end trend {trend_id}.")

