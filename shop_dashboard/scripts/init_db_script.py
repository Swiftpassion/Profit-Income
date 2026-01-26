
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.database import init_db

if __name__ == "__main__":
    print("Initializing Database...")
    try:
        init_db()
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")
