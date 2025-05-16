import functions_framework
import requests
import json
import os
import logging
from datetime import datetime, timedelta, timezone

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
CVE_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
OUTPUT_DIR = "/ragpapers/cves"
# Optional: If you have an API key from NIST NVD
NVD_API_KEY = "ca001a5b-91e1-4c99-9e89-f4c96132d19a"  # Replace with your API key as a string if you have one, e.g., "your_api_key_here"
MAX_CVES_TO_DOWNLOAD = 100  # Maximum number of CVEs to download

# --- Helper Functions ---
def get_date_strings():
    """Generates ISO 8601 formatted date strings for the last 24 hours."""
    now_utc = datetime.now(timezone.utc)
    start_time_utc = now_utc - timedelta(days=1)
    
    pub_start_date = start_time_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    pub_end_date = now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    return pub_start_date, pub_end_date

# Added max_to_fetch parameter
def fetch_cves(start_date, end_date, api_key=None, max_to_fetch=None):
    """Fetches CVEs from the NVD API for the given date range, up to a maximum number."""
    params = {
        "pubStartDate": start_date,
        "pubEndDate": end_date
    }
    headers = {}
    if api_key:
        headers["apiKey"] = api_key

    logging.info(f"Fetching CVEs from {start_date} to {end_date}...")
    if max_to_fetch is not None:
        logging.info(f"Will download a maximum of {max_to_fetch} CVEs.")
    
    cves = []
    start_index = 0
    results_per_page = 0 
    total_results = -1   

    try:
        while total_results == -1 or start_index < total_results:
            # Check if we already have enough CVEs before making an API call
            if max_to_fetch is not None and len(cves) >= max_to_fetch:
                logging.info(f"Already met or exceeded download limit of {max_to_fetch} CVEs before new API call. Stopping.")
                break

            params["startIndex"] = start_index
            response = requests.get(CVE_BASE_URL, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if total_results == -1: 
                total_results = data.get("totalResults", 0)
                results_per_page = data.get("resultsPerPage", 0)
                logging.info(f"Total CVEs found in time range by API: {total_results}")
                if total_results == 0:
                    break # No CVEs reported by API for the time range
            
            current_cves_data = data.get("vulnerabilities", [])
            if not current_cves_data:
                # This might happen if start_index >= total_results due to pagination logic,
                # or if API returns empty list unexpectedly. The outer loop condition should handle normal termination.
                logging.info("No more vulnerabilities found in the current batch.")
                break

            for cve_item_wrapper in current_cves_data:
                # Stop adding if max_to_fetch limit is reached
                if max_to_fetch is not None and len(cves) >= max_to_fetch:
                    logging.info(f"Reached download limit of {max_to_fetch} CVEs during page processing.")
                    break  # Break from iterating through current_cves_data
                
                cve_item = cve_item_wrapper.get("cve")
                if cve_item:
                    cves.append(cve_item)
                else:
                    logging.warning(f"Warning: Found an item without a 'cve' key: {cve_item_wrapper}")
            
            logging.info(f"Fetched {len(cves)} CVEs so far...")
            
            # Break outer while loop if limit is reached after processing the current page's items
            if max_to_fetch is not None and len(cves) >= max_to_fetch:
                break # Exit while loop

            if results_per_page == 0: 
                logging.warning("Warning: resultsPerPage is 0, cannot paginate further. This might occur if totalResults was also 0.")
                break
            start_index += results_per_page
            
            # Respect NVD rate limits (original script's commented-out code):
            # time.sleep(6 if not api_key else 0.6) # Consider adding 'import time'

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching CVEs: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Response content: {e.response.text}")
        return None # Indicate failure by returning None
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON response: {e}")
        if 'response' in locals() and response: # Check if response variable exists
            logging.error(f"Response content: {response.text}")
        return None # Indicate failure by returning None
        
    # Ensure we don't return more than max_to_fetch (safeguard).
    # The loops should ideally prevent this, but this guarantees the constraint.
    if max_to_fetch is not None and len(cves) > max_to_fetch:
        logging.info(f"Trimming CVE list from {len(cves)} to {max_to_fetch} as a final step.")
        cves = cves[:max_to_fetch]
        
    return cves

def save_cve(cve_data, directory):
    """Saves a single CVE data as a JSON file."""
    try:
        cve_id = cve_data.get("id")
        if not cve_id:
            logging.warning(f"Warning: CVE data missing 'id': {cve_data.get('sourceIdentifier', 'Unknown Source')}")
            return

        # Get current date and format it as YYYY_MM_DD
        current_date_str = datetime.now().strftime('%Y_%m_%d')
        # Prepend datestamp to filename
        filename = f"{current_date_str}_{cve_id}.json"
        
        if not os.path.exists(directory):
            os.makedirs(directory)
            logging.info(f"Created directory: {directory}")

        file_path = os.path.join(directory, filename)
        if os.path.exists(file_path):
            logging.info(f"CVE: {file_path} already downloaded. Skipping.")
        else:
            with open(file_path, 'w') as f:
                json.dump(cve_data, f, indent=4)
            logging.info(f"Saved CVE: {file_path}")
    except Exception as e:
        logging.error(f"Error saving CVE {cve_id if 'cve_id' in locals() else 'Unknown ID'}: {e}")

@functions_framework.http
def main(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    request_json = request.get_json(silent=True)
    request_args = request.args

    if request_json and 'name' in request_json:
        name = request_json['name']
    elif request_args and 'name' in request_args:
        name = request_args['name']
    else:
        name = 'World'

    # Download and save the CVE papers
    logging.info("Starting CVE download process...")
    
    start_date_str, end_date_str = get_date_strings()
    
    # Pass the MAX_CVES_TO_DOWNLOAD to fetch_cves
    downloaded_cves = fetch_cves(start_date_str, end_date_str, 
                                 api_key=NVD_API_KEY, 
                                 max_to_fetch=MAX_CVES_TO_DOWNLOAD)
    
    if downloaded_cves is not None: # Check if fetch_cves encountered an error (returned None)
        logging.info(f"\nSuccessfully fetched {len(downloaded_cves)} CVEs (limit was {MAX_CVES_TO_DOWNLOAD}).")
        if not downloaded_cves: # If list is empty (e.g., no CVEs in range, or limit was 0)
            logging.info("No new CVEs to process based on criteria or limit.")
        
        # Create output directory if it doesn't exist AND we have CVEs to save
        if downloaded_cves and not os.path.exists(OUTPUT_DIR):
            try:
                os.makedirs(OUTPUT_DIR)
                logging.info(f"Created output directory: {OUTPUT_DIR}")
            except OSError as e:
                logging.error(f"Error creating directory {OUTPUT_DIR}: {e}")
                logging.error("Please ensure the directory path is valid and you have write permissions.")
                # Consider exiting if directory creation fails and is critical: exit(1)
        
        for cve in downloaded_cves:
            save_cve(cve, OUTPUT_DIR)
        
        if downloaded_cves: # Only log this if actual CVEs were processed and stored
            logging.info(f"Processed CVEs have been stored in {OUTPUT_DIR}")
    else:
        logging.error("CVE fetching failed. No CVEs were downloaded due to an error during the fetch process.")

    logging.info("CVE download process finished.")

    return 'Papers downloaded. Thanks, {}!'.format(name)
