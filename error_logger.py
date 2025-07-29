import traceback
from datetime import datetime
import os

def log_error_to_file(error_log_path, context_message, exception=None):
    """Logs error with timestamp, optional context, and stack trace."""
    try:
        os.makedirs(os.path.dirname(error_log_path), exist_ok=True)

        with open(error_log_path, 'a') as f:
            f.write(f"\n[ERROR] {datetime.now().isoformat()}\n")
            f.write(f"Context: {context_message}\n")
            if exception: 
                f.write(f"Exception: {str(exception)}\n")
                f.write(traceback.format_exc())
            f.write("-" * 60 + "\n")
    except Exception:
        # need to include so logger doesn't crash
        pass
