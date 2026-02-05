
try:
    import fitz
    print(f"PyMuPDF version: {fitz.__doc__}")
    print(f"File: {fitz.__file__}")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
