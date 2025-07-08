import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# --- GLOBAL VARIABLES AND CONSTANTS ---
# Logging setup
LOGGING_LEVEL = logging.INFO
LOGGING_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# Selenium WebDriver Parameters
DEFAULT_WAIT_TIMEOUT = 20  # Maximum wait time for elements in seconds
HEADLESS_MODE = False  # Set to True to run without a browser GUI
MAXIMIZE_WINDOW = True  # Maximize browser window on startup

# Element Selectors
FIRST_BUTTON_XPATH = '//*[@id="STR_DOWNLOAD_PDF"]'
SECOND_BUTTON_XPATH = '//*[@id="dialogButtons"]/button[1]'

# Paths to ChromeDriver and Chrome executable (replace with your actual paths)
# If these variables are not set (None), Selenium will try to find ChromeDriver in PATH.
CHROME_DRIVER_PATH = r"chromedriver-win64\chromedriver.exe"
CHROME_BINARY_LOCATION = r"chrome-win64\chrome.exe"
# CHROME_DRIVER_PATH = None
# CHROME_BINARY_LOCATION = None

# Directory for saving downloaded files
DOWNLOAD_DIRECTORY_NAME = "pdfs_to_process"  # Name of the download folder

# Test URLs for demonstration
TEST_URLS = [
    "https://portal.laserfiche.com/Portal/DocView.aspx?id=27355&repo=r-5c10bb82&searchid=7b07ff98-49ce-4a06-b47d-e2a6b370e720",
    "https://portal.laserfiche.com/Portal/DocView.aspx?id=12344&repo=r-5c10bb82&searchid=0017990e-2fef-4c88-80db-66fc81e314d8",
    "https://portal.laserfiche.com/Portal/DocView.aspx?id=21226&repo=r-5c10bb82&searchid=bc37b316-e88a-4ac6-a0e1-826183439a50",
    "https://portal.laserfiche.com/Portal/DocView.aspx?id=22194&repo=r-5c10bb82&searchid=bc37b316-e88a-4ac6-a0e1-826183439a50"
]

# --- LOGGING CONFIGURATION ---
logging.basicConfig(level=LOGGING_LEVEL, format=LOGGING_FORMAT)


def setup_chrome_driver(chrome_driver_path, chrome_binary_location, download_dir, headless_mode, maximize_window):
    """
    Configures and returns a WebDriver instance for Chrome.
    """
    options = webdriver.ChromeOptions()

    # Configure download directory and PDF behavior
    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True  # Important for downloading, not viewing PDFs
    }
    options.add_experimental_option("prefs", prefs)

    # Headless mode and other arguments
    if headless_mode:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Set path to Chrome binary
    if chrome_binary_location:
        if not os.path.exists(chrome_binary_location):
            logging.critical(f"CRITICAL ERROR: Chrome executable not found at path: {chrome_binary_location}")
            raise FileNotFoundError(f"Chrome binary not found: {chrome_binary_location}")
        options.binary_location = chrome_binary_location

    driver_service = None
    if chrome_driver_path:
        if not os.path.exists(chrome_driver_path):
            logging.critical(f"CRITICAL ERROR: ChromeDriver not found at path: {chrome_driver_path}")
            raise FileNotFoundError(f"ChromeDriver not found: {chrome_driver_path}")
        driver_service = ChromeService(executable_path=chrome_driver_path)

    try:
        if driver_service:
            driver = webdriver.Chrome(service=driver_service, options=options)
        else:
            driver = webdriver.Chrome(options=options)
        logging.info("WebDriver successfully initialized.")
        if maximize_window and not headless_mode:
            driver.maximize_window()
        return driver
    except Exception as e:
        logging.critical(f"Error initializing WebDriver: {e}", exc_info=True)
        raise


def wait_for_file_download_completion(download_dir, initial_files, file_download_timeout):
    """
    Waits for a new file to finish downloading in the specified directory.
    Returns the full path to the downloaded file or None in case of a timeout.
    """
    download_complete = False
    downloaded_filepath = None
    start_download_wait_time = time.time()
    last_size = -1  # To track file size changes

    while time.time() - start_download_wait_time < file_download_timeout and not download_complete:
        current_files = set(os.listdir(os.path.abspath(download_dir)))
        new_files = current_files - initial_files

        potential_downloads = [
            f for f in new_files
            if f.endswith(".pdf") or f.endswith(".crdownload") or f.endswith(".tmp")  # Account for temporary files
        ]

        if potential_downloads:
            # Assume we are interested in the first PDF that appears
            for filename in potential_downloads:
                current_file_path = os.path.join(os.path.abspath(download_dir), filename)

                # Check if the file exists and is not empty
                if os.path.exists(current_file_path) and os.path.getsize(current_file_path) > 0:
                    # If the file is still downloading (has a temporary extension)
                    if filename.endswith(".crdownload") or filename.endswith(".tmp"):
                        # Check if the file size has stabilized over the last second
                        current_size = os.path.getsize(current_file_path)
                        if current_size == last_size and current_size > 0:
                            # Size has stabilized, the file likely finished downloading,
                            # but still has a temporary extension.
                            # This can be an issue: sometimes Chrome removes .crdownload only after closing.
                            logging.info(
                                f"Temporary file {filename} has stable size: {current_size} bytes. Waiting for final name...")
                            downloaded_filepath = current_file_path
                            download_complete = True  # Consider the download complete in terms of data
                            break
                        last_size = current_size
                    else:  # File already has a .pdf extension
                        logging.info(f"PDF file detected: {filename}")
                        downloaded_filepath = current_file_path
                        # Additional check for completion (file size stable)
                        stable_check_count = 0
                        for _ in range(5):  # Check 5 times with a small delay
                            time.sleep(0.5)
                            new_size = os.path.getsize(downloaded_filepath)
                            if new_size == last_size and new_size > 0:
                                stable_check_count += 1
                            else:
                                stable_check_count = 0  # Reset if size changed
                            last_size = new_size
                            if stable_check_count >= 3:
                                download_complete = True
                                break
                        if download_complete:
                            logging.info(f"PDF file successfully downloaded and stabilized: {downloaded_filepath}")
                            break
        if not download_complete:
            time.sleep(1)
    return downloaded_filepath


def download_pdf_from_webpage(urls, first_button_xpath, second_button_xpath,
                              chrome_driver_path, chrome_binary_location, download_dir="downloads",
                              wait_timeout=DEFAULT_WAIT_TIMEOUT, file_download_timeout=DEFAULT_WAIT_TIMEOUT,
                              headless_mode=HEADLESS_MODE, maximize_window=MAXIMIZE_WINDOW):
    """
    Automatically navigates to a page, clicks two sequential buttons to initiate print/download,
    and waits for the PDF file download to complete.

    Args:
        urls (list): List of URLs from which to download PDFs.
        first_button_xpath (str): XPath of the first button to initiate the action ("Print PDF").
        second_button_xpath (str): XPath of the second button that appears after the first ("Download and Print").
        chrome_driver_path (str): Path to the ChromeDriver executable.
        chrome_binary_location (str): Path to the Chrome executable.
        download_dir (str, optional): Directory to save downloaded files. Defaults to "downloads".
        wait_timeout (int): Maximum wait time for elements in seconds.
        file_download_timeout (int): Maximum wait time for file download to complete in seconds.
        headless_mode (bool): Whether to run the browser in headless mode.
        maximize_window (bool): Whether to maximize the browser window.
    """
    if not urls:
        logging.info("List of URLs to download is empty. Skipping function execution.")
        return

    # Check and create the download directory
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        logging.info(f"Created download directory: {os.path.abspath(download_dir)}")
    else:
        logging.info(f"Using existing download directory: {os.path.abspath(download_dir)}")

    driver = None
    try:
        driver = setup_chrome_driver(chrome_driver_path, chrome_binary_location, download_dir, headless_mode,
                                     maximize_window)

        for i, url in enumerate(urls):
            logging.info(f"\n--- Processing page {i + 1}/{len(urls)}: {url} ---")

            try:
                # 1. Record current files in the download directory before starting a new download
                initial_files = set(os.listdir(os.path.abspath(download_dir)))
                logging.debug(f"Initial state of download directory before new link: {initial_files}")

                # 2. Navigate to the current page
                logging.info(f"Opening page: {url}")
                driver.get(url)

                # 3. Wait for the first button to be clickable and click it
                logging.info(f"Looking for the first button ({first_button_xpath})...")
                first_button = WebDriverWait(driver, wait_timeout).until(
                    EC.element_to_be_clickable((By.XPATH, first_button_xpath))
                )
                first_button.click()
                logging.info("Clicked the first button.")

                # 4. Wait for the second button to be clickable and click it
                logging.info(f"Looking for the second button ({second_button_xpath})...")
                second_button = WebDriverWait(driver, wait_timeout).until(
                    EC.element_to_be_clickable((By.XPATH, second_button_xpath))
                )
                second_button.click()
                logging.info("Clicked the second button. Waiting for download to start...")

                # 5. Wait for file download to complete
                downloaded_filepath = wait_for_file_download_completion(download_dir, initial_files,
                                                                        file_download_timeout)

                if not downloaded_filepath:
                    logging.warning(
                        f"Timeout waiting for PDF file download for {url}. The file might not have downloaded completely or at all.")
                else:
                    logging.info(f"Download for {url} completed. File: {downloaded_filepath}")

            except TimeoutException as te:
                logging.error(f"Timeout waiting for element on page {url}: {te}")
                screenshot_name = f"timeout_error_{url.replace('/', '_').replace(':', '').replace('?', '_').replace('=', '_').replace('&', '_')}.png"
                if driver: driver.save_screenshot(screenshot_name)
            except NoSuchElementException as nse:
                logging.error(f"Element not found on page {url}: {nse}")
                screenshot_name = f"element_not_found_error_{url.replace('/', '_').replace(':', '').replace('?', '_').replace('=', '_').replace('&', '_')}.png"
                if driver: driver.save_screenshot(screenshot_name)
            except WebDriverException as wde:
                logging.critical(f"Critical WebDriver error while processing {url}: {wde}")
                screenshot_name = f"webdriver_error_{url.replace('/', '_').replace(':', '').replace('?', '_').replace('=', '_').replace('&', '_')}.png"
                if driver: driver.save_screenshot(screenshot_name)
            except Exception as e:
                logging.error(f"An unexpected error occurred while processing {url}: {e}", exc_info=True)
                screenshot_name = f"general_error_{url.replace('/', '_').replace(':', '').replace('?', '_').replace('=', '_').replace('&', '_')}.png"
                if driver: driver.save_screenshot(screenshot_name)

    except Exception as e:
        logging.critical(f"General error during PDF download process: {e}", exc_info=True)
    finally:
        if driver:
            driver.quit()
            logging.info("Browser closed after processing all pages.")


# --- Main execution block ---
if __name__ == "__main__":
    download_pdf_from_webpage(
        urls=TEST_URLS,
        first_button_xpath=FIRST_BUTTON_XPATH,
        second_button_xpath=SECOND_BUTTON_XPATH,
        chrome_driver_path=CHROME_DRIVER_PATH,
        chrome_binary_location=CHROME_BINARY_LOCATION,
        download_dir=DOWNLOAD_DIRECTORY_NAME,
        wait_timeout=DEFAULT_WAIT_TIMEOUT,
        file_download_timeout=DEFAULT_WAIT_TIMEOUT,
        headless_mode=HEADLESS_MODE,
        maximize_window=MAXIMIZE_WINDOW
    )