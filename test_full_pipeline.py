import requests
import time
import sys
import os

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_pipeline():
    # 1. Upload
    print("Uploading sample_note.png...")
    upload_url = f"{BASE_URL}/documents/upload"
    
    if not os.path.exists("backend/sample_note.png"):
        print("Error: backend/sample_note.png not found")
        return

    with open("backend/sample_note.png", "rb") as f:
        files = {'file': ('sample_note.png', f, 'image/png')}
        res = requests.post(upload_url, files=files)
    
    if res.status_code != 200:
        print(f"Upload failed: {res.text}")
        return
        
    doc = res.json()
    doc_id = doc['id']
    print(f"Uploaded Document ID: {doc_id}")
    
    # 2. Start Beautify
    print("Triggering beautification...")
    beautify_url = f"{BASE_URL}/documents/{doc_id}/beautify"
    res = requests.post(beautify_url)
    
    if res.status_code != 200:
        print(f"Beautify trigger failed: {res.text}")
        # Continue if possible? No.
        return
        
    job_info = res.json()
    job_id = job_info.get("job_id")  # Assuming my change in API returns this or headers
    if not job_id:
        # Check header
        job_id = res.headers.get("X-Beautify-Job")
        
    print(f"Job triggered. Job ID: {job_id}")
    
    # 3. Poll Status (Actually, the endpoint waits?)
    # My code in documents.py returns JSONResponse immediately AFTER creating session?
    # No, documents.py `beautify_document` uses `run_in_process` or `background_tasks`.
    # It returns JSONResponse with job_id immediately.
    
    print("Polling document status...")
    for i in range(30):
        time.sleep(2)
        status_url = f"{BASE_URL}/documents/{doc_id}"
        res = requests.get(status_url)
        current_doc = res.json()
        status = current_doc['status']
        print(f"Status: {status}")
        
        if status == 'beautified':
            print("Beautification Complete!")
            break
        if status == 'error':
            print("Beautification Failed.")
            return
            
    if status != 'beautified':
        print("Timed out waiting for beautification.")
        return

    # 4. Download PDF
    print("Downloading PDF...")
    pdf_url = f"{BASE_URL}/documents/{doc_id}/download-pdf"
    res = requests.get(pdf_url)
    
    if res.status_code == 200:
        with open("backend/final_output.pdf", "wb") as f:
            f.write(res.content)
        print("PDF Downloaded to backend/final_output.pdf")
        print("Test PASSED.")
    else:
        print(f"PDF Download failed: {res.status_code} {res.text}")

if __name__ == "__main__":
    test_pipeline()
