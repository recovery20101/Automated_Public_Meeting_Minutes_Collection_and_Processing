# main.py
import os
import logging
import sys

from id_extractor import extract_ids_from_meeting_minutes, process_and_generate_links
from pdf_downloader import download_pdf_from_webpage
from summarize_text import extract_text_from_pdf, save_text_to_file, get_gemini_model, summarize_text_with_gemini

# ==============================================================================
#                 GLOBAL CONFIGURATION VARIABLES (EDIT THESE)
# ==============================================================================

# --- Chrome WebDriver Paths ---
CHROME_DRIVER_PATH = r"chromedriver-win64\chromedriver.exe"
CHROME_BINARY_LOCATION = r"chrome-win64\chrome.exe"

# --- Website Specific Configuration (id_extractor) ---
# URL of the meeting minutes archive website
WEBSITE_URL = "https://www.stcharlesil.gov/Government/Meetings/Meeting-Minutes-Archive"
# Categories to process. Set to None to dynamically extract all categories from the page.
# Example: ["City Council", "Finance Committee"]
CATEGORIES_TO_PROCESS = None

# --- PDF Download Configuration (pdf_downloader) ---
# Directory where downloaded PDFs will be saved
DOWNLOAD_DIR = "pdfs_to_process"
NUM_LINKS_TO_DOWNLOAD = 7 # Number of links to download. Set to None to download all.
HEADLESS_MODE = False  # Set to True to run without a browser GUI
MAXIMIZE_WINDOW = True  # Maximize browser window on startup

# XPaths for buttons on the document view page
FIRST_DOWNLOAD_BUTTON_XPATH = '//*[@id="STR_DOWNLOAD_PDF"]'
SECOND_DOWNLOAD_BUTTON_XPATH = '//*[@id="dialogButtons"]/button[1]'

# --- Gemini API and Summarization Configuration (summarize_text) ---
# Your Google Gemini API Key.
# API_KEY = os.getenv('GOOGLE_API_KEY')
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE" # Placeholder, replace with your actual key or use os.getenv()

# Gemini model name (e.g., 'gemini-1.5-flash', 'gemini-1.5-pro')
GEMINI_MODEL_NAME = 'gemini-2.0-flash'
# Maximum number of tokens in the Gemini summary response
GEMINI_MAX_OUTPUT_TOKENS = 1000
# Temperature for Gemini generation (0.0 = more deterministic, 1.0 = more creative)
GEMINI_TEMPERATURE = 0.2
# Maximum text length (in characters) for a single request to Gemini.
# Large documents will be chunked if they exceed this.
GEMINI_MAX_TEXT_LENGTH_FOR_SINGLE_CALL = 30000

# Directory where generated text summaries will be saved
SUMMARIES_OUTPUT_FOLDER = 'summaries'

# --- General Automation Settings ---
# Default maximum wait time for Selenium elements in seconds
DEFAULT_WAIT_TIMEOUT = 20
# Log file name for the entire workflow
LOG_FILE_NAME = "automation_workflow.log"
# Logging level (e.g., logging.INFO, logging.DEBUG, logging.WARNING, logging.ERROR, logging.CRITICAL)
LOGGING_LEVEL = logging.INFO

# ==============================================================================
#                 END OF GLOBAL CONFIGURATION
# ==============================================================================


# --- LOGGING SETUP ---
logging.basicConfig(level=LOGGING_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(LOG_FILE_NAME),
                        logging.StreamHandler(sys.stdout)
                    ])


def run_full_automation_workflow():
    """
    Orchestrates the entire automation workflow:
    1. Extracts document IDs and generates download links.
    2. Downloads PDFs using the generated links.
    3. Extracts text from downloaded PDFs and summarizes them using Gemini.
    """
    logging.info("--- Starting the full automation workflow ---")

    # --- 0. Initial Setup & Validation ---
    # Check if Chrome paths are valid
    if not os.path.exists(CHROME_DRIVER_PATH):
        logging.critical(f"ChromeDriver not found at: {CHROME_DRIVER_PATH}. Please check the path.")
        sys.exit(1)
    if not os.path.exists(CHROME_BINARY_LOCATION):
        logging.critical(f"Chrome browser not found at: {CHROME_BINARY_LOCATION}. Please check the path.")
        sys.exit(1)

    # Create necessary directories
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(SUMMARIES_OUTPUT_FOLDER, exist_ok=True)
    logging.info(f"Download directory set to: {os.path.abspath(DOWNLOAD_DIR)}")
    logging.info(f"Summaries output directory set to: {os.path.abspath(SUMMARIES_OUTPUT_FOLDER)}")

    # --- 1. Extract IDs and Generate Links ---
    logging.info("\n--- Step 1: Extracting document IDs and generating download links ---")

    extracted_data = extract_ids_from_meeting_minutes(
        url=WEBSITE_URL,
        categories=CATEGORIES_TO_PROCESS,
        chrome_driver_path=CHROME_DRIVER_PATH,
        chrome_binary_location=CHROME_BINARY_LOCATION,
        wait_timeout=DEFAULT_WAIT_TIMEOUT
    )

    if not extracted_data:
        logging.error("Failed to extract any IDs. Aborting PDF download and summarization.")
        sys.exit(1)

    final_links = process_and_generate_links(extracted_data)

    if not final_links:
        logging.warning("No download links were generated. Skipping PDF download and summarization.")
        sys.exit(0)

    logging.info(f"Successfully generated {len(final_links)} unique download links.")

    # --- 2. Download PDFs ---
    logging.info("\n--- Step 2: Starting PDF download process ---")

    links_to_download = final_links
    if NUM_LINKS_TO_DOWNLOAD is not None:
        links_to_download = final_links[:NUM_LINKS_TO_DOWNLOAD]

    logging.info(f"Processing {len(links_to_download)} generated links for download.")

    download_pdf_from_webpage(
        urls=links_to_download,
        first_button_xpath=FIRST_DOWNLOAD_BUTTON_XPATH,
        second_button_xpath=SECOND_DOWNLOAD_BUTTON_XPATH,
        chrome_driver_path=CHROME_DRIVER_PATH,
        chrome_binary_location=CHROME_BINARY_LOCATION,
        download_dir=DOWNLOAD_DIR,
        wait_timeout=DEFAULT_WAIT_TIMEOUT,
        file_download_timeout=DEFAULT_WAIT_TIMEOUT,
        headless_mode = HEADLESS_MODE,
        maximize_window = MAXIMIZE_WINDOW
    )
    logging.info("PDF download process completed (check logs for individual file status).")

    # --- 3. Process and Summarize PDFs ---
    logging.info("\n--- Step 3: Extracting text from PDFs and generating summaries ---")

    # Initialize Gemini model
    gemini_model = get_gemini_model(GEMINI_API_KEY, GEMINI_MODEL_NAME)
    if not gemini_model:
        logging.critical(
            "Gemini model could not be initialized due to missing API key or configuration error. Aborting summarization.")
        sys.exit(1)

    # Get list of downloaded PDF files
    pdf_files_to_summarize = [f for f in os.listdir(DOWNLOAD_DIR) if f.lower().endswith('.pdf')]

    if not pdf_files_to_summarize:
        logging.warning(f"No PDF files found in '{DOWNLOAD_DIR}' for summarization. Skipping summarization step.")
    else:
        for pdf_file_name in pdf_files_to_summarize:
            pdf_path = os.path.join(DOWNLOAD_DIR, pdf_file_name)
            logging.info(f"\n--- Processing PDF for summarization: {pdf_file_name} ---")

            extracted_full_text = extract_text_from_pdf(pdf_path)

            if extracted_full_text:
                logging.info(f"Text extracted from {pdf_file_name} (first 200 chars): {extracted_full_text[:200]}...")

                summary = summarize_text_with_gemini(
                    model=gemini_model,
                    text_to_summarize=extracted_full_text,
                    max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
                    temperature=GEMINI_TEMPERATURE
                )

                logging.info(f"\n--- Generated summary for {pdf_file_name} ---")
                logging.info(summary)

                # Save the summary to a text file
                summary_file_name = os.path.splitext(pdf_file_name)[0] + '_summary.txt'
                summary_output_path = os.path.join(SUMMARIES_OUTPUT_FOLDER, summary_file_name)
                save_text_to_file(summary, summary_output_path)
            else:
                logging.error(f"Could not extract text from {pdf_file_name}. Skipping summarization for this file.")

    logging.info("\n--- Full automation workflow completed! ---")

if __name__ == "__main__":
    run_full_automation_workflow()