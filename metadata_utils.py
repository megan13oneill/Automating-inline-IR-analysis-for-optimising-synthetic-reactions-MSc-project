import os
import traceback
from datetime import datetime
from opcua import ua
from opcua.ua import uaerrors
from opcua.ua.uaerrors import UaStatusCodeError

from error_logger import log_error_to_file


#def save_spectrum_to_csv(spectrum_data, folder, display_name):
#    """Save spectrum data to a CSV file and return the file path."""
#    os.makedirs(folder, exist_ok=True)
#
#    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#    filename = f"{display_name.replace(' ', '_').lower()}_{timestamp}.csv"
#    file_path = os.path.join(folder, filename)
#
#    try:
#        with open(file_path, "w") as f:
#            for value in spectrum_data:
#                f.write(f"{value}\n")
#    except Exception as e:
#        log_error_to_file(f"Failed to save spectrum to CSV at {file_path}", e)
#        return None
#
#    return file_path


def get_probe1_data(client, probe1_node_id, processed_folder):
    """Queries child nodes of Probe1, replacing spectrum arrays with CSV file paths."""
    probe1_results = []

    try:
        probe_node = client.get_node(probe1_node_id)
        child_nodes = probe_node.get_children()

        for child in child_nodes:
            try:
                display_name = child.get_display_name().Text
                value_of_node = child.get_value()

                # If spectrum array
                if isinstance(value_of_node, (list, tuple)) and len(value_of_node) > 10 and "Spectra" in display_name:
                    # Choose subfolder based on type
                    if "Treated" in display_name:
                        subfolder = os.path.join(processed_folder, "treated")
                    elif "Background" in display_name:
                        subfolder = os.path.join(processed_folder, "background")
                    else:
                        subfolder = os.path.join(processed_folder, "other")

                    file_path = save_spectrum_to_csv(value_of_node, subfolder, display_name)
                    display_value = file_path
                else:
                    display_value = value_of_node

                probe1_results.append((display_name, display_value))

            except uaerrors.BadAttributeIdInvalid as e:
                log_error_to_file(
                    context_message=f"Child node '{child}' does not support attribute 'Value'. Skipped. (BadAttributeIdInvalid)",
                    exception=e
                )
            except UaStatusCodeError as e:
                log_error_to_file(
                    context_message=f"UaStatusCodeError when reading child node '{child}'",
                    exception=e
                )
            except Exception as e:
                log_error_to_file(
                    context_message=f"Unexpected error while reading child node '{child}'",
                    exception=e
                )
    except Exception as e:
        log_error_to_file(
            context_message=f"Failed to read Probe 1 node '{probe1_node_id}'",
            exception=e,
            trace=traceback.format_exc()
        )

    return probe1_results
