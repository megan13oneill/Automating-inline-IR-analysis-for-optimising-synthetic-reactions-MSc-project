import os
import traceback
from datetime import datetime

current_error_log_path = None

def set_error_log_path(path: str):
    """ Sets the global error log path for all logging operations. Ensures the dir exists."""
    global current_error_log_path
    current_error_log_path = path

    log_dir = os.path.dirname(path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)


def log_error_to_file(context_message="No context provided", exception: Exception=None):
    """Logs error with timestamp, optional context, and stack trace."""
    try:
        if not current_error_log_path:
            print(f"Error logger has not been configured with a path.")
            return 

        timestamp = datetime.now().strftime("%d-%m%Y_%H-%M-%S")

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

        with open(current_error_log_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)

    except Exception as logging_error:
        # need to include so logger doesn't crash
        print("Failed to write to log file.")
        print(f"Context: {context_message}")
        print(f"Original Exception: {exception}")
        print(f"Logging Error: {logging_error}")
