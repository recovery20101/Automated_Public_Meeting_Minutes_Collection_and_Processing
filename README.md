# Automated Public Meeting Minutes Collection and Processing
## Context
This project was developed in response to a specific client requirement on Upwork, aiming to provide an automated solution for collecting, organizing, and summarizing public meeting minutes. It demonstrates a practical application of web scraping and AI summarization techniques.

This project provides a comprehensive solution for automating the collection, downloading, and summarization of public meeting minutes from the stcharlesil.gov website. It leverages Selenium for web scraping, pdfplumber for text extraction from PDFs, and the Google Gemini API for AI-powered summarization. The project is structured for easy deployment and re-running.

## Features
* **Document ID Extraction:** Automatically discovers and extracts unique document IDs for meeting minutes from the specified archive page.

* **Dynamic Category Extraction:** Ability to dynamically determine all available meeting minutes categories (e.g., "City Council", "Finance Committee") if not explicitly provided.

* **PDF Download**: Automatically navigates to document links and downloads corresponding PDF files to a specified local directory.

* **PDF Text Extraction:** Extracts the full text content from downloaded PDF documents.

* **AI-Powered Summarization:** Utilizes the Google Gemini API to generate concise and objective summaries of each document.

* **Large Document Handling:** Mechanism to break down large documents into chunks before summarization with Gemini to comply with API limits.

* **Structured Saving:** Organizes downloaded PDFs and generated summaries into separate, logically named folders.

* **Logging:** Detailed logging of the process for monitoring and debugging.

## Project Structure
```
.
├── chromedriver-win64/    # Directory for ChromeDriver
│   └── chromedriver.exe
├── chrome-win64/          # Directory for Chrome Browser
│   └── chrome.exe
├── pdfs_to_process/       # Downloaded PDF files will be saved here
├── summaries/             # Generated summaries will be saved here
├── automation_workflow.log # Log file for the entire automation workflow
├── id_extractor.py        # Script for extracting document IDs and generating links
├── main.py                # Main script orchestrating the entire workflow
├── pdf_downloader.py      # Script for downloading PDF files
├── requirements.txt       # Install necessary Python libraries
└── summarize_text.py      # Script for PDF text extraction and AI summarization
```

## Requirements
* Python 3.x
* Google Chrome Browser
* ChromeDriver (ensure the version matches your Chrome version)
* Google Gemini API Key

## Installation
1. Clone the repository:

```
git clone <YOUR_REPOSITORY_URL>
cd <project_folder_name>
```

2. Create and activate a virtual environment (recommended):

```
python -m venv .venv
# For Windows:
.venv\Scripts\activate
# For macOS/Linux:
source .venv/bin/activate
```

3. Install necessary Python libraries:

```
pip install -r requirements.txt
```

4. Set up Chrome Browser and ChromeDriver (Chrome for Testing v. 138.0.7204.94 was used):

    * Download Google Chrome.

    * Download the chromedriver.exe corresponding to your Chrome version from Google Chrome for Testing.

    * Place chromedriver.exe into the chromedriver-win64 folder within your project root.

    * Ensure the path to your Chrome executable (chrome.exe) is correctly specified. By default, the project expects it in chrome-win64\chrome.exe. 

5. Configure your Google Gemini API Key:

    * Obtain an API key from Google AI Studio.

    * Set it as an environment variable named GOOGLE_API_KEY or replace the placeholder "YOUR_GEMINI_API_KEY_HERE" in main.py with your actual key.
```
Python

# In main.py
GEMINI_API_KEY = os.getenv('GOOGLE_API_KEY')
# OR (for quick setup, but not recommended for production)
# GEMINI_API_KEY = "YOUR_ACTUAL_KEY_HERE"
```

## Usage
To run the full automation workflow:

```
python main.py
```
### Configuration
All configurable parameters are gathered at the top of the main.py file. You can modify them to suit your needs:

* CHROME_DRIVER_PATH: Path to the ChromeDriver executable.

* CHROME_BINARY_LOCATION: Path to the Chrome Browser executable.

* WEBSITE_URL: URL of the meeting minutes archive website.

* CATEGORIES_TO_PROCESS: List of categories to process. Set to None to dynamically extract all categories from the page.

* DOWNLOAD_DIR: Directory for saving downloaded PDF files.

* NUM_LINKS_TO_DOWNLOAD: Number of links to download. Set to None to download all.

* HEADLESS_MODE: Set to True to run the browser in the background (without a GUI).

* GEMINI_API_KEY: Your Google Gemini API key.

* GEMINI_MODEL_NAME: Name of the Gemini model to use (e.g., 'gemini-1.5-flash', 'gemini-1.5-pro').

* GEMINI_MAX_OUTPUT_TOKENS: Maximum number of tokens in Gemini's summarization response.

* SUMMARIES_OUTPUT_FOLDER: Directory for saving generated summaries.

* DEFAULT_WAIT_TIMEOUT: Timeout for Selenium elements.

### Execution Log
The automation process keeps a detailed log in the automation_workflow.log file. This file contains information about each step, including successfully downloaded files, errors, and summarization status.

## Author
Oleksandr Smyrnov

(This project was developed as a submission for a potential Upwork client. My goal was to demonstrate proficiency in web scraping, and AI text summarization for real-world applications.)
