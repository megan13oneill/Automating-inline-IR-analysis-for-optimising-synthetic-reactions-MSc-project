from connect import try_connect
from acquire_metadata import get_probe1_data
from measure_spectra import continuous_raw_spectrum_logger

PROBE_1_NODE_ID = "ns=2;s=Local.iCIR.Probe1"

if __name__ == "__main__":
    client = try_connect()
    if not client:
        exit(1)

    probe_data = get_probe1_data(client, PROBE_1_NODE_ID)

    print("\n Probe 1 Metadata:")
    for name, value in probe_data:
        print(f"{name}: {value}")

    continuous_raw_spectrum_logger(
        client,
        probe_status_id=)

    client.disconnect()
 