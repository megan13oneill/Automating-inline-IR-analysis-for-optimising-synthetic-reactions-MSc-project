import os
import csv
import numpy as np
from scipy.signal import savgol_filter
import matplotlib.pyplot as plt

def plot_and_save_spectrum(wavenumbers, transmittance, output_path):
    plt.figure(figsize=(14, 9))  # Larger figure size

    plt.plot(wavenumbers, transmittance, color='darkblue', linewidth=2)

    # Axis configuration
    plt.gca().invert_xaxis()  # IR spectra typically show wavenumber decreasing left to right

    plt.title("Infrared Spectrum", fontsize=28, weight='bold')
    plt.xlabel("Wavenumber (cm⁻¹)", fontsize=24, labelpad=15)
    plt.ylabel("Transmittance (%)", fontsize=24, labelpad=15)

    # Tick font sizes
    plt.xticks(fontsize=20)
    plt.yticks(fontsize=20)

    # Grid for clarity
    plt.grid(True, which='both', linestyle='--', linewidth=0.6)

    # Tight layout for full visibility
    plt.tight_layout()

    # Save to file
    plt.savefig(output_path, dpi=300)
    plt.close()

def process_and_store_data(input_dir="logs",
                           output_dir="processed",
                           smooth=False,
                           window_length=11,
                           polyorder=2
):
   
    """ open csv and process the data by applying smoothing and then save the processed data."""

    os.makedirs(output_dir, exist_ok=True)

    files = sorted([f for f in os.listdir(input_dir) if f.endswith(".csv")])
    if not files:
        print(f"No CSV files found in {output_dir}")
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

            with open(input_path, 'r') as file: 
                reader = csv.reader(file)
                next(reader)
                for row in reader: 
                    wavenumbers.append(float(row[0]))
                    transmittance.append(float(row[1]))
                
            wavenumbers = np.array(wavenumbers)
            transmittance = np.array(transmittance)

            #smooth if requested
            if smooth and len(transmittance) >= window_length:
                transmittance = savgol_filter(transmittance, window_length, polyorder)

            # save processed spectrum to CSV
            with open(output_csv_path, 'w', newline='') as file_out:
                writer = csv.writer(file_out)
                writer.writerow(["wavenumber", "transmittance"])
                for wn, tr in zip(wavenumbers, transmittance):
                    writer.writerow([wn,tr])

            plot_and_save_spectrum(wavenumbers, transmittance, output_plot_path)
            print(f"Processed + plotted: {base_filename}")

        except Exception as e:
            print(f"Error processing '{file_name}': {e}")




