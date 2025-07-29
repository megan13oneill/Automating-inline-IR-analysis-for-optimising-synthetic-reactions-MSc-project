import traceback
from datetime import datetime
import os

log_file_path = "error_log.txt"

def log_error_to_file(error_log_path=log_file_path, context_message="No context provided", exception=None):
    """Logs error with timestamp, optional context, and stack trace."""
    try:
        os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
        timestamp = datetime.now().strftime("%d-%m%Y_%H:%M:%S")

        log_entry = (
            f"\n--- ERROR LOG ---\n"
            f"Timestamp: {timestamp}\n"
            f"Context: {context_message}\n"
        )

        if exception:
            log_entry += (
                f"Exception: {str(exception)}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
        
        log_entry += "-" * 60 + "\n"

        with open(error_log_path, 'a') as f:
            f.write(log_entry)

    except Exception:
        # need to include so logger doesn't crash
        print("Failed to write to log file.")
