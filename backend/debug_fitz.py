
import sys
import os
import fitz

print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")
print(f"Fitz version: {fitz.__version__}")

filename = "1770287214905_test_for_lattice.pdf"
filepath = os.path.join("uploads", filename)

print(f"Testing file: {filepath}")
if not os.path.exists(filepath):
    print("File does not exist!")
    sys.exit(1)

try:
    doc = fitz.open(filepath)
    print(f"Opened PDF. Pages: {len(doc)}")
    
    page = doc.load_page(0)
    pix = page.get_pixmap()
    output = "debug_output.png"
    pix.save(output)
    print(f"Saved page 0 to {output}")
    doc.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
