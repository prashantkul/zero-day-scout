import functions_framework
import arxiv
import datetime
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
SEARCH_CATEGORY = "cs.CR" # Arxiv category for Cryptography and Security
DOWNLOAD_DIR = "/ragpapers/arxiv_security_papers" # Directory to save downloaded papers
MAX_RESULTS = 100 # Max results to fetch from Arxiv for the category initially
# --- End Configuration ---

def download_papers_last_day(category: str, download_dir: str, max_results: int):
    """
    Finds and downloads papers from a specific Arxiv category published yesterday.

    Args:
    category: The Arxiv category code (e.g., 'cs.CR').
    download_dir: The directory path to save downloaded PDFs.
    max_results: The maximum number of results to initially fetch from Arxiv.
    """
    # Create the download directory if it doesn't exist
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        logging.info(f"Created download directory: {download_dir}")

    # Calculate yesterday's date
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    logging.info(f"Searching for papers published on: {yesterday}")

    # Construct the search object
    # Sort by last updated date to potentially get recent papers faster
    search = arxiv.Search(
        query=f"cat:{category}",
        max_results=max_results,
        sort_by=arxiv.SortCriterion.LastUpdatedDate
        # Note: Arxiv API v1 doesn't directly support filtering by *published* date range in the query.
        # We need to fetch recent results and filter them locally.
    )

    download_count = 0
    # Iterate through the results from the Arxiv API
    client = arxiv.Client() # Reuse client for efficiency
    results = client.results(search)

    logging.info(f"Checking recent papers in category '{category}'...")

    try:
        for result in results:
            # Arxiv dates are in UTC. result.published is a datetime object.
            published_date = result.published.date()

            # Check if the paper was published yesterday
            if published_date == yesterday:
                logging.info(f"Found paper published yesterday: '{result.title}' (ID: {result.entry_id})")
                try:
                    # Format the publication date for the filename prefix
                    date_prefix = published_date.strftime("%Y_%m_%d")

                    # Define filename using Arxiv ID and prepended datestamp
                    # Example filename: 2023_05_15_2305.12345v1.pdf (if yesterday was 2023-05-15)
                    pdf_filename = f"{date_prefix}_{result.get_short_id()}.pdf"
                    filepath = os.path.join(download_dir, pdf_filename)

                    # Check if already downloaded
                    if os.path.exists(filepath):
                        logging.info(f"Paper {result.get_short_id()} already downloaded. Skipping.")
                        continue

                    # Download the PDF to the specified directory
                    result.download_pdf(dirpath=download_dir, filename=pdf_filename)
                    logging.info(f"Successfully downloaded: {filepath}")
                    download_count += 1
                except Exception as e:
                    logging.error(f"Failed to download paper {result.entry_id}: {e}")
            elif published_date < yesterday:
                # Since results are sorted by LastUpdatedDate (or SubmittedDate if preferred),
                # once we see a paper older than yesterday, we can potentially stop
                # checking further *if* we assume publish date correlates well with update date.
                # However, updates can happen long after publication, so it's safer
                # to check all `max_results` if needed. Let's log and continue for now.
                pass # Continue checking other results just in case

    except Exception as e:
        logging.error(f"An error occurred during the search or iteration: {e}")


    if download_count == 0:
        logging.info(f"No papers found in category '{category}' published on {yesterday}.")
    else:
        logging.info(f"Finished downloading. Total papers downloaded: {download_count}")

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

    # Download and save the Arxiv papers
    download_papers_last_day(SEARCH_CATEGORY, DOWNLOAD_DIR, MAX_RESULTS)

    return 'Papers downloaded. Thanks, {}!'.format(name)
