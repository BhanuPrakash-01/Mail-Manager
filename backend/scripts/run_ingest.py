import json
import time
import requests

def main():
    print("Loading inbox_test_250.json...")
    with open("inbox_test_250.json", "r") as f:
        emails = json.load(f)
        
    print(f"Loaded {len(emails)} emails.")
    
    payload = {
        "candidate_id": "bhanuprakashaleti06@gmail.com",
        "emails": emails
    }
    
    print("Submitting to POST /ingest...")
    response = requests.post("http://localhost:8000/ingest", json=payload)
    print(f"Response status: {response.status_code}")
    
    try:
        data = response.json()
        print("Response data:", data)
    except Exception as e:
        print("Failed to parse JSON:", response.text)
        return

    if response.status_code != 200:
        return
        
    run_id = data.get("run_id")
    if not run_id:
        print("No run_id found!")
        return
        
    print(f"Polling GET /ingest/{run_id}...")
    while True:
        res = requests.get(f"http://localhost:8000/ingest/{run_id}")
        if res.status_code != 200:
            print(f"Poll failed with {res.status_code}: {res.text}")
            break
            
        status_data = res.json()
        status = status_data.get("status")
        
        print(f"Status: {status} | Processed: {status_data.get('processed_count')} / {len(emails)} | Errors: {status_data.get('error_count')}")
        
        if status == "completed":
            print("\nFinal Result:")
            print(json.dumps(status_data, indent=2))
            break
            
        time.sleep(2)

if __name__ == "__main__":
    main()
