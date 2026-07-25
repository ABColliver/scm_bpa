import os
import json
import gzip
import time
import requests
import http.client
from urllib.parse import urlparse

# =============================================
# Palo Alto SCM Posture API - July 2026 
# On-Demand BPA (Python)
# Andrew Colliver - ab.colliver@gmail.com
# =============================================
# CONFIGURATION
# =============================================
CLIENT_ID = "username@yourtsid.iam.panserviceaccount.com"
CLIENT_SECRET = "clientsecrethere"
XML_FILE_PATH = "firewall_config.xml"
OUTPUT_JSON_PATH = "bpa_result.json"

# API Endpoints
AUTH_URL = "https://auth.apps.paloaltonetworks.com/am/oauth2/access_token"
API_BASE_URL = "https://api.strata.paloaltonetworks.com"
# =============================================
def get_access_token():
    print("[1/4] Authenticating with Strata Cloud Manager Posture API...")
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    response = requests.post(AUTH_URL, data=data)
    response.raise_for_status()

    token_data = response.json()
    print("      Authentication successful.")
    return token_data["access_token"]

def request_upload_url(token):
    print("[2/4] Requesting secure upload URL...")
    url = f"{API_BASE_URL}/posture/checks/v1/reports/config-file-upload"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, json={})
    response.raise_for_status()
    data = response.json()

    # Set Upload URL and Task ID
    upload_url = data.get("upload_url")
    task_id = data.get("task_id")

    if not upload_url or not task_id:
        raise Exception(f"Failed to parse upload URL or Task ID. Response: {data}")

    print(f"      Task ID generated: {task_id}")
    print(f"      Upload URL: {upload_url}")
    return upload_url, task_id

def upload_to_gcs(upload_url, file_path):
    print("[3/4] Uploading configuration XML...")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    # Read the raw XML file
    with open(file_path, "rb") as f:
        file_buffer = f.read()

    parsed_url = urlparse(upload_url)
    hostname = parsed_url.hostname
    path = parsed_url.path + ("?" + parsed_url.query if parsed_url.query else "")

    # STRICT HEADERS: GCS V4 requires specific headers and correct mime type. Keep content-encoding as gzip to satisfy the signature.
    # Set content length to match file buffer.
    headers = {
        "content-type": "text/plain",
        "content-encoding": "gzip",
        "host": hostname,
        "content-length": str(len(file_buffer))
    }

    # Send the raw file buffer
    conn = http.client.HTTPSConnection(hostname)
    conn.request("PUT", path, body=file_buffer, headers=headers)
    response = conn.getresponse()
    # Check it hasn't failed
    if response.status not in (200, 201):
        error_body = response.read().decode("utf-8")
        raise Exception(f"GCS Upload failed: {response.status} {response.reason} - {error_body}")

    print("      XML Upload complete.")

def poll_and_download(token, task_id):
    print("[4/4] Polling API for completion status...")
    url = f"{API_BASE_URL}/posture/checks/v1/reports/{task_id}/bpa-result"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    attempts = 0
    max_attempts = 60

    while attempts < max_attempts:
        attempts += 1
        response = requests.get(url, headers=headers)

        # 202 Accepted usually means processing has started but isn't finished
        if response.status_code == 202:
            print(f"      [{attempts}/{max_attempts}] Status: 202 ACCEPTED. Waiting 10s...")
            time.sleep(10)
            continue

        response.raise_for_status()
        data = response.json()

        # Extract status string safely - have seen undocumented active_states returned
        status = data.get("status", data.get("data", {}).get("status", "")).upper()
        active_states = ['QUEUED', 'PENDING', 'RUNNING', 'IN_PROGRESS', 'PROCESSING', 'SCHEDULED', 'STARTING']

        if status in active_states:
            print(f"      [{attempts}/{max_attempts}] Status: {status}... Waiting 10s...")
            time.sleep(10)
        elif status in ['FAILED', 'ERROR']:
            raise Exception(f"Job failed on the server. Details: {json.dumps(data)}")
        elif status in ['COMPLETED', 'SUCCESS']:
            print("      Status: COMPLETED. Locating report URL...")

            # Search for the report URL across known Palo Alto API response structures
            # Sometimes report_url is returned like documented sometimes its blank, sometimes custom_check_url is returned instead
            # This handles both cases seen so far
            result_obj = data.get("result", {})
            data_obj = data.get("data", {})
            possible_urls = [
                result_obj.get("report_url"),
                result_obj.get("custom_check_url"),
                data.get("report_url"),
                data_obj.get("report_url"),
                data_obj.get("custom_check_url"),
                data_obj.get("url"),
                data.get("url"),
                result_obj.get("url")
            ]

            # Find the first URL that is actually returned and is a populated string
            report_url = next((u for u in possible_urls if u and isinstance(u, str) and u.strip()), None)

            if not report_url:
                raise Exception(f"Job completed, but no report URL was found. Response: {json.dumps(data)}")

            print(f"      Report URL: {report_url}")
            print("      Downloading final BPA JSON report...")

            report_response = requests.get(report_url)
            report_response.raise_for_status()

            with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(report_response.json(), f, indent=2)

            print(f"      Success! Report saved to {OUTPUT_JSON_PATH}")
            return
        else:
            # Fallback for payloads that directly return the data without a status field
            print("      Unexpected status or direct payload received. Saving output...")
            with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"      Success! Data saved to {OUTPUT_JSON_PATH}")
            return

    raise Exception("Polling timed out. The job may still be processing.")

def main():
    try:
        token = get_access_token()
        upload_url, task_id = request_upload_url(token)
        upload_to_gcs(upload_url, XML_FILE_PATH)
        poll_and_download(token, task_id)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")

if __name__ == "__main__":
    main()
