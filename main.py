from connect import try_connect
from metadata_utils import get_probe1_data
from spectrum_logger import raw_spectrum_logger
from processing_utils import process_and_store_data

PROBE_1_NODE_ID = "ns=2;s=Local.iCIR.Probe1"

def main():
    with try_connect() as client:
        if not client: 
            print("Failed to connect to OPC UA server.")
            return
        
        # Get probe metadata once connected
        probe_data = get_probe1_data(client, PROBE_1_NODE_ID)
        print("\nProbe 1 Metadata:")
        for name, value in probe_data:
            print(f"{name}: {value}")

        # Start logging raw spectrum data
        raw_spectrum_logger(
            client,
            probe_status_id="ns;s=Local.iCIR.Probe1.ProbeStatus",
            raw_spectrum_id="ns;s=Local.iCIR.Probe1.SpectraRaw",
            sampling_interval_id="ns;s=Local.iCIR.Probe1.CurrentSamplingInterval",
            output_dir="logs"
        )

        # Process and store the logged data
        process_and_store_data(
            input_dir="logs",
            output_dir="processed",
            smooth=True,
            window_length=11,
            polyorder=2
        )

if __name__ == "__main__":
    main()
