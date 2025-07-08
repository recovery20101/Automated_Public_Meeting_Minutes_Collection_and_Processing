import os
import re
import sys
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, \
    WebDriverException
from bs4 import BeautifulSoup
import time

# --- GLOBAL VARIABLES AND CONSTANTS ---
# Logging setup
LOGGING_LEVEL = logging.INFO
LOGGING_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# Selenium WebDriver Parameters
DEFAULT_WAIT_TIMEOUT = 20  # Maximum wait time for elements in seconds
HEADLESS_MODE = False  # Set to True to run without a browser GUI

# URLs and Patterns
BASE_WEBSITE_URL = "https://www.stcharlesil.gov/Government/Meetings/Meeting-Minutes-Archive"
BASE_DOC_VIEW_URL_TEMPLATE = "https://portal.laserfiche.com/Portal/DocView.aspx?id={doc_id}&repo=r-5c10bb82"

# Element Selectors
MODAL_CLOSE_BUTTON_CSS = "button.prefix-overlay-close.prefix-overlay-action-later"
IFRAME_CSS_SELECTOR = "iframe[title='portal-laserfiche']"
DROPDOWN_INPUT_ID = "MeetingMinutesSearch_Input0"
SUBMIT_BUTTON_CSS = "input.CustomSearchSubmitButton"
DOCUMENT_LINK_CSS_SELECTOR = "a[href*='/Portal/DocView.aspx?id=']"
RESULT_TEXT_ID = "resultText"
NO_RESULTS_TEXT = "0 - 0 of 0"

# Paths to ChromeDriver and Chrome executable (replace with your actual paths)
# If these variables are not set, Selenium will try to find ChromeDriver in PATH.
CHROME_DRIVER_PATH = r"chromedriver-win64\chromedriver.exe"
CHROME_BINARY_LOCATION = r"chrome-win64\chrome.exe"
#CHROME_DRIVER_PATH = None
#CHROME_BINARY_LOCATION = None

# List of categories to process (None for dynamic extraction)
CATEGORIES_TO_PROCESS = None  # Example: ["City Council", "Finance Committee"]

# --- LOGGING CONFIGURATION ---
logging.basicConfig(level=LOGGING_LEVEL, format=LOGGING_FORMAT)

class results_are_loaded:
    """
    Custom Selenium explicit wait condition to determine when search results are loaded
    or when the "No results found" message appears.
    """
    def __init__(self, driver):
        self.driver = driver

    def __call__(self, driver):
        # Check for "0 - 0 of 0" message
        try:
            result_text_element = driver.find_element(By.ID, RESULT_TEXT_ID)
            if NO_RESULTS_TEXT in result_text_element.text.strip():
                logging.debug(f"Found '{NO_RESULTS_TEXT}'")
                return True  # Zero results message found
        except NoSuchElementException:
            pass  # Element might not be present, which is normal

        # Check for document links
        doc_links = driver.find_elements(By.CSS_SELECTOR, DOCUMENT_LINK_CSS_SELECTOR)
        if doc_links:
            logging.debug(f"Found {len(doc_links)} new document links.")
            return True  # New links found

        logging.debug("Waiting for results to load...")
        return False  # Nothing found, continue waiting

def extract_ids_from_meeting_minutes(url, categories=None, chrome_driver_path=None, chrome_binary_location=None,
                                     wait_timeout=DEFAULT_WAIT_TIMEOUT):
    """
    Extracts IDs from document links for specified categories on the meeting minutes archive page.

    Args:
        url (str): The URL of the meeting minutes archive page.
        categories (list, optional): A list of strings with category names to process.
                                     If None, categories will be extracted dynamically from the page.
        chrome_driver_path (str, optional): Path to the ChromeDriver executable.
        chrome_binary_location (str, optional): Path to the Chrome executable.
        wait_timeout (int): Maximum wait time for elements in seconds.

    Returns:
        dict: A dictionary where keys are category names and values are lists of extracted IDs.
    """
    all_extracted_ids = {}

    chrome_options = webdriver.ChromeOptions()
    if HEADLESS_MODE:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    if chrome_binary_location:
        if not os.path.exists(chrome_binary_location):
            logging.critical(f"CRITICAL ERROR: Chrome executable not found at path: {chrome_binary_location}")
            sys.exit(1)
        chrome_options.binary_location = chrome_binary_location
        logging.info(f"Chrome.exe path specified: {chrome_binary_location}")

    driver_service = None
    if chrome_driver_path:
        if not os.path.exists(chrome_driver_path):
            logging.critical(f"CRITICAL ERROR: ChromeDriver not found at path: {chrome_driver_path}")
            sys.exit(1)
        driver_service = ChromeService(executable_path=chrome_driver_path)
        logging.info(f"ChromeDriver.exe path specified: {chrome_driver_path}")
    else:
        logging.info("ChromeDriver.exe path not specified. Selenium will search for it in PATH.")

    driver = None
    try:
        if driver_service:
            driver = webdriver.Chrome(service=driver_service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
        logging.info("WebDriver successfully initialized.")

        driver.get(url)
        logging.info(f"Page loaded: {url}")

        # Close the "STAY CONNECTED" modal
        try:
            close_button = WebDriverWait(driver, wait_timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, MODAL_CLOSE_BUTTON_CSS))
            )
            close_button.click()
            logging.info("Closed 'STAY CONNECTED' modal by clicking 'Close subscription dialog'.")
            WebDriverWait(driver, wait_timeout).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR,
                                                    "div.prefix-overlay-modal, " + MODAL_CLOSE_BUTTON_CSS))
            )
            logging.info("Modal dialog disappeared from the page.")
        except TimeoutException:
            logging.warning(
                "The 'STAY CONNECTED' modal did not appear or could not be closed within the timeout. Continuing.")
        except Exception as e:
            logging.warning(f"An error occurred while trying to close the modal: {e}. Continuing.")
            driver.save_screenshot("modal_close_error_debug.png")

        # Switch to iframe
        try:
            iframe_element = WebDriverWait(driver, wait_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, IFRAME_CSS_SELECTOR))
            )
            driver.switch_to.frame(iframe_element)
            logging.info(f"Switched to iframe '{IFRAME_CSS_SELECTOR}'.")
        except TimeoutException:
            driver.save_screenshot("iframe_not_found_error.png")
            logging.critical(
                f"CRITICAL ERROR: Could not find or switch to iframe '{IFRAME_CSS_SELECTOR}' within {wait_timeout} seconds. Screenshot saved.")
            sys.exit(1)
        except Exception as e:
            driver.save_screenshot("iframe_not_found_error.png")
            logging.critical(
                f"CRITICAL ERROR: An error occurred while finding/switching to iframe: {e}. Screenshot saved.")
            sys.exit(1)

        # Scroll to element inside iframe and wait for its visibility
        try:
            element_to_scroll_to = WebDriverWait(driver, wait_timeout).until(
                EC.presence_of_element_located((By.ID, DROPDOWN_INPUT_ID))
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element_to_scroll_to)
            logging.info(f"Page scrolled to element '{DROPDOWN_INPUT_ID}' inside iframe.")

            # Ensure the element becomes visible after scrolling
            select_element_selenium = WebDriverWait(driver, wait_timeout).until(
                EC.visibility_of_element_located((By.ID, DROPDOWN_INPUT_ID))
            )
            logging.info("Dropdown element found and visible inside iframe. Continuing.")
        except TimeoutException:
            driver.save_screenshot("dropdown_not_visible_in_iframe_after_scroll.png")
            logging.critical(
                f"CRITICAL ERROR: Dropdown element did not become visible inside iframe after scrolling within {wait_timeout} seconds. Screenshot saved.")
            sys.exit(1)
        except Exception as e:
            driver.save_screenshot("scroll_to_element_in_iframe_error.png")
            logging.critical(
                f"CRITICAL ERROR: Failed to scroll page or wait for visibility of element '{DROPDOWN_INPUT_ID}' inside iframe: {e}. Screenshot saved.")
            sys.exit(1)

        # 1. Dynamic category extraction
        if categories is None:
            logging.info("No category list provided. Extracting categories dynamically from the page.")
            try:
                # Get the HTML of the dropdown
                select_html = select_element_selenium.get_attribute('outerHTML')
                soup_options = BeautifulSoup(select_html, 'html.parser')
                categories = [
                    option.text.strip() for option in soup_options.find_all('option')
                    if option.text.strip() and option.text.strip() != "Select..."
                ]
                if not categories:
                    logging.critical(
                        "CRITICAL ERROR: Failed to extract categories from the dropdown. List is empty.")
                    sys.exit(1)
                logging.info(f"Dynamically retrieved categories: {categories}")
            except Exception as e:
                logging.critical(f"CRITICAL ERROR: Failed to dynamically extract categories: {e}")
                sys.exit(1)
        else:
            logging.info(f"Using provided categories: {categories}")

        for category_index, category in enumerate(categories):
            logging.info(f"\nProcessing category: '{category}'")

            current_visible_links = driver.find_elements(By.CSS_SELECTOR, DOCUMENT_LINK_CSS_SELECTOR)

            try:
                select_element_selenium = WebDriverWait(driver, wait_timeout).until(
                    EC.element_to_be_clickable((By.ID, DROPDOWN_INPUT_ID))
                )
                selector = Select(select_element_selenium)
                selector.select_by_visible_text(category)
                logging.info(f"Selected category: {category}")

            except TimeoutException:
                logging.warning(
                    f"Could not find or click the dropdown for category '{category}' within {wait_timeout} seconds. Skipping.")
                continue
            except NoSuchElementException:
                logging.warning(f"Category '{category}' not found in the dropdown list. Skipping.")
                continue
            except Exception as e:
                logging.warning(f"An error occurred while selecting category '{category}': {e}. Skipping.")
                continue

            try:
                submit_button = WebDriverWait(driver, wait_timeout).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, SUBMIT_BUTTON_CSS))
                )
                submit_button.click()
                logging.info("Clicked the 'Submit' button.")
                time.sleep(0.5)

            except TimeoutException:
                logging.warning(
                    f"Could not click the 'Submit' button for category '{category}' within {wait_timeout} seconds. Skipping.")
                continue
            except Exception as e:
                logging.warning(
                    f"An error occurred while clicking the 'Submit' button for category '{category}': {e}. Skipping.")
                continue

            try:
                if current_visible_links:
                    logging.info("Waiting for previous results to disappear...")
                    try:
                        WebDriverWait(driver, wait_timeout).until(
                            EC.staleness_of(current_visible_links[0])
                        )
                        logging.info("Previous results disappeared.")
                    except TimeoutException:
                        logging.warning(
                            "Previous results did not disappear completely within timeout. DOM might not be fully cleared.")
                    except StaleElementReferenceException:
                        logging.debug("Previous element is already stale.")
                    except Exception as e:
                        logging.warning(f"Error waiting for old results to disappear: {e}.")
                else:
                    logging.info("No previous results, waiting for new ones or 'No results found'.")

                WebDriverWait(driver, wait_timeout).until(results_are_loaded(driver))

                logging.info(f"Page for category '{category}' successfully refreshed or 'No results found' received.")

            except TimeoutException:
                logging.warning(
                    f"Failed to wait for new results or 'No results found' message for category '{category}' within {wait_timeout} seconds. Skipping. Screenshot saved.")
                driver.save_screenshot(f"load_results_timeout_{category}.png")
                continue
            except WebDriverException as we:
                logging.critical(
                    f"Critical WebDriver error for category '{category}': {we}. Browser might have crashed. Exiting.")
                sys.exit(1)
            except Exception as e:
                logging.warning(
                    f"An error occurred while waiting for new results for category '{category}': {e}. Skipping. Screenshot saved.")
                driver.save_screenshot(f"load_results_error_{category}.png")
                continue

            try:
                result_text_element = driver.find_element(By.ID, RESULT_TEXT_ID)
                current_result_text = result_text_element.text.strip()

                if NO_RESULTS_TEXT in current_result_text:
                    logging.info(
                        f"No results found for category '{category}'. Adding an empty list.")
                    all_extracted_ids[category] = []
                    continue
            except NoSuchElementException:
                logging.debug(f"Element '{RESULT_TEXT_ID}' not found or does not contain '{NO_RESULTS_TEXT}'.")
                pass

            current_page_source = driver.page_source
            soup = BeautifulSoup(current_page_source, 'html.parser')

            doc_links = soup.find_all('a', href=re.compile(r'/Portal/DocView.aspx\?id=(\d+)'))

            unique_extracted_ids = set()
            for link in doc_links:
                href = link.get('href')
                match = re.search(r'id=(\d+)', href)
                if match:
                    doc_id = match.group(1)
                    unique_extracted_ids.add(doc_id)

            all_extracted_ids[category] = list(unique_extracted_ids)

            if unique_extracted_ids:
                logging.info(f"Extracted {len(unique_extracted_ids)} UNIQUE IDs for category '{category}'.")
            else:
                logging.info(f"No IDs found for category '{category}'. Page structure might have changed.")

    except Exception as e:
        logging.critical(f"A general critical error occurred: {e}", exc_info=True)
    finally:
        if driver:
            driver.quit()
            logging.info("Browser closed.")

    return all_extracted_ids

def process_and_generate_links(extracted_data):
    """
    Extracts IDs from the received data and generates links.

    Args:
        extracted_data (dict): A dictionary with categories and lists of IDs.

    Returns:
        list: A list of formed URL links.
    """
    generated_links = []

    if not extracted_data:
        logging.warning("No data to process. The link list will be empty.")
        return []

    for category, ids in extracted_data.items():
        if not ids:
            logging.info(f"No IDs to generate links for category '{category}'.")
            continue
        for doc_id in ids:
            link = BASE_DOC_VIEW_URL_TEMPLATE.format(doc_id=doc_id)
            generated_links.append(link)
            logging.info(f"Formed link: {link} for category '{category}'")
    return generated_links

# --- Function Usage ---
if __name__ == "__main__":
    results = extract_ids_from_meeting_minutes(
        BASE_WEBSITE_URL,
        categories=CATEGORIES_TO_PROCESS,
        chrome_driver_path=CHROME_DRIVER_PATH,
        chrome_binary_location=CHROME_BINARY_LOCATION,
        wait_timeout=DEFAULT_WAIT_TIMEOUT
    )

    logging.info("\n--- Extracted IDs by Category ---")
    if not results:
        logging.info("No IDs were extracted for any category.")
    for category, ids in results.items():
        logging.info(f"Category: {category}")
        logging.info(f"  Number of IDs: {len(ids)}")
        logging.info("-" * 30)

    logging.info("Generating links based on extracted data...")
    final_links = process_and_generate_links(results)
    logging.info("Link generation complete.")

    logging.info("\n--- Generated Links ---")
    if not final_links:
        logging.info("No links generated.")
    else:
        for link in final_links:
            logging.info(link)