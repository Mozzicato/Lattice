import requests

url = "http://127.0.0.1:8000/api/v1/documents/upload"
files = {'file': ('test_upload.pdf', open('temp_test_upload.pdf', 'rb'), 'application/pdf')}

try:
    response = requests.post(url, files=files)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
