import os
import pandas as pd


def process_and_store_data(csv_path, apply_smoothing=True, smoothing_window=51, polyorder=3, save_processed=True, plot=True):
   
    """ open csv and process the data by applying smoothing and then save the processed data."""

    try:

        df = pd.read_csv(csv_path)
        print(f"loaded {len(df)} spectra from csv_path")

        spectra = df.drop(columns=)


