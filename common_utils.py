import os
import csv
from datetime import datetime

def get_current_timestamp_str():
    """Returns current timestamp formatted as string."""
    return datetime.now().strftime("%d-%m-%Y_%H-%M-%S_%f")[:-3]

def write_spectrum_csv(wavenumbers, spectrum, filepath):
    """Writes wavenumber and transmittance values to a CSV file."""
    with open(filepath, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["wavenumber", "transmittance"])
        for wn, trans in zip(wavenumbers, spectrum):
            writer.writerow([wn, trans])
        file.flush()
        os.fsync(file.fileno())

        