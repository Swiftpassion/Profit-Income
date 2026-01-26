
import sys
import os
from modules.database import init_db

if __name__ == "__main__":
    print("Initializing Database...")
    try:
        init_db()
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")
