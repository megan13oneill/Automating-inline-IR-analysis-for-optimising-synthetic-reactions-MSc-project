import os
import csv
import numpy as np
from scipy.signal import savgol_filter
import matplotlib.pyplot as plt

def adjust_window_length(window_length, data_length):

    """Ensure the window_length is an odd number, less than data_length, and at least 3."""

    if window_length >= data_length:
        window_length = data_length - 1
    if window_length %2 == 0:
        window_length -= 1
    if window_length < 3:
        window_length = 3
    return window_length

def plot_and_save_spectrum(wavenumbers, transmittance, output_path):
    """ plotting the transmittance vs wavenumber and saving that file as a pdf and a png within the specified directory."""
    
    plt.figure(figsize=(14, 9))  
    plt.plot(wavenumbers, transmittance, color='darkblue', linewidth=2)

    # Axis configuration as IR spectra typically show wavenumber decreasing left to right
    plt.gca().invert_xaxis() 

    plt.title("Infrared Spectrum", fontsize=28, weight='bold')
    plt.xlabel("Wavenumber (cm⁻¹)", fontsize=24, labelpad=15)
    plt.ylabel("Transmittance (%)", fontsize=24, labelpad=15)

    plt.xticks(fontsize=20)
    plt.yticks(fontsize=20)
    plt.grid(False)

    # Tight layout for full visibility
    plt.tight_layout()

    # Save to file
    base, ext = os.path.splitext(output_path)
    plt.savefig(f"{base}.png", dpi=300)
    plt.savefig(f"{base}.pdf", dpi=300)
    plt.close()

def process_and_store_data(input_dir: str = "logs",
                           output_dir: str = "processed",
                           smooth: bool = False,
                           window_length: int = 11,
                           polyorder: int = 2) -> None:
   
    """ open csv and process the data by applying smoothing and then save the processed data."""

    os.makedirs(output_dir, exist_ok=True)

    files = sorted([f for f in os.listdir(input_dir) if f.endswith(".csv")])
    if not files:
        print(f"No CSV files found in {input_dir}")
        return
    print(f"Processing {len(files)} spectra ...")

    for file_name in files: 
        input_path = os.path.join(input_dir, file_name)
        base_filename = os.path.splitext(file_name)[0]
        output_csv_path = os.path.join(output_dir, f"processed_{file_name}")
        output_plot_path = os.path.join(output_dir, f"{base_filename}.png")

        try: 
            #load spectrum data
            wavenumbers = []
            transmittance = []

            with open(input_path, 'r', newline='') as file: 
                # look through the first bit of file and check if there is a header, then go back to the beginning to read carefully.
                sample_data = file.read(1024)
                file.seek(0)
                has_header = csv.Sniffer().has_header(sample_data)
                reader = csv.reader(file)

                if has_header:
                    next(reader)

                for row in reader: 
                    try:
                        wavenumbers.append(float(row[0]))
                        transmittance.append(float(row[1]))
                    except (ValueError, IndexError):
                        continue
            
            wavenumbers = np.array(wavenumbers)
            transmittance = np.array(transmittance)

            #smooth if requested
            if smooth and len(transmittance) >= window_length:
                # need to make sure window_length is odd.
                window_length = adjust_window_length(window_length, len(transmittance))

                transmittance = savgol_filter(transmittance, window_length, polyorder)

            # save processed spectrum to CSV
            with open(output_csv_path, 'w', newline='') as file_out:
                writer = csv.writer(file_out)
                writer.writerow(["wavenumber", "transmittance"])
                for wn, tr in zip(wavenumbers, transmittance):
                    writer.writerow([wn,tr])

            plot_and_save_spectrum(wavenumbers, transmittance, output_plot_path)
            print(f"Processed and Plotted: {base_filename}")

        except Exception as e:
            print(f"Error processing '{file_name}': {e}")

    print("All spectra have been processed!")
