# Palo Alto SCM Posture API - On-Demand BPA Tool

This Python script provides a simple, standalone method for interacting with the Palo Alto Networks Strata Cloud Manager (SCM) Posture API. This tool automates the process of uploading an XML configuration and retrieving a Best Practices Assessment (BPA) report in JSON format.
See Palo Alto Posture API Documentation at [pan.dev](https://pan.dev/scm/api/config/posture-management/initiate-config-upload/)

## Key Features

*   **Authentication:** Handles Auth to the SCM OAuth2 endpoint using a Service Account Client ID and Secret.
*   **XML Configuration Upload:** Sends PUT to GCS Storage Bucket.
*   **GCS V4 Signature Compliance:** Uses `http.client` to execute the XML file upload to satisfy Google Cloud Storage V4 signed URL requirements with required headers & mime type. [GCS Signed URLs](https://docs.cloud.google.com/storage/docs/access-control/signed-urls)
*   **Job Polling:** After Upload automatically polls the Strata Cloud Manager Posture API every 10 seconds to track the assessment's progress. It handles various active status states (including `QUEUED`, `IN_PROGRESS` etc.) before completing.
*   **URL Extraction:** Because the Palo Alto API occasionally shifts the final download link between variables, the script scans the response schema for both `report_url` and `custom_check_url` for download URL.

## Prerequisites

*   Python 3.x
*   The `requests` library
*   An SCM Tenant with a Service Account configured with the appropriate permissions.

Install the required library via pip:
```bash
pip install requests
```
## Configuration
```
Before running the script, open it in your preferred editor and update the CONFIGURATION block at the top of the file
CLIENT_ID = "username@yourtsid.iam.panserviceaccount.com" # Replace with your SCM Service Account ID
CLIENT_SECRET = "clientsecrethere"                        # Replace with your Client Secret
XML_FILE_PATH = "firewall_config.xml"                     # Path to your exported Palo Alto firewall XML config
OUTPUT_JSON_PATH = "bpa_result.json"                      # Desired output path for the finalized BPA report
```

## Usage

*   Place your target firewall configuration file (e.g., firewall_config.xml) in the same directory as the script, or provide an absolute path in the configuration block.
*   Execute the script from your terminal:
```
python scm_bpa.py
```

## Expected Output
```
[1/4] Authenticating: Retrieves the access token from Strata Cloud Manager
[2/4] Requesting URL: Generates a task ID and secures a signed Google Cloud Storage upload URL
[3/4] Uploading: Directly PUTs the raw XML configuration into the cloud bucket with strict header matching
[4/4] Polling & Downloading: Waits for the backend analysis to finish, locates the generated report URL, and saves the final JSON file locally. 
```
Posture API Typically responds with JSON in 10-40 seconds depending on config size.
