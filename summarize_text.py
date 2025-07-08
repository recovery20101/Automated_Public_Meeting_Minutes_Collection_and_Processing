import pdfplumber
import google.generativeai as genai
import textwrap
import os
import logging

# --- GLOBAL VARIABLES AND CONSTANTS ---
# Logging setup
LOGGING_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# Folders for input and output files
PDF_INPUT_FOLDER = 'pdfs_to_process'
SUMMARIES_OUTPUT_FOLDER = 'summaries'

# Gemini model settings
# API_KEY = your_key
# API_KEY = os.getenv('GOOGLE_API_KEY')
GEMINI_MODEL_NAME = 'gemini-2.0-flash'
MAX_OUTPUT_TOKENS = 1000  # Maximum number of tokens in the response
TEMPERATURE = 0.2  # Generation temperature

# Maximum text size for a single Gemini request (in characters, approximate)
# This helps break down large documents into chunks
MAX_TEXT_LENGTH_FOR_SINGLE_CALL = 30000

# --- LOGGING SETUP ---
logging.basicConfig(level=LOGGING_LEVEL, format=LOG_FORMAT)


def extract_text_from_pdf(pdf_path: str) -> str | None:
    """
    Extracts all text from the specified PDF file.

    Args:
        pdf_path (str): Path to the PDF file.

    Returns:
        str: All text extracted from the PDF file, or None if an error occurred.
    """
    text_content = ""
    if not os.path.exists(pdf_path):
        logging.error(f"File not found at path: {pdf_path}")
        return None
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content += page_text + "\n"
        return text_content
    except Exception as e:
        logging.error(f"Error extracting text from {pdf_path}: {e}")
        return None


def save_text_to_file(text: str, output_filepath: str):
    """
    Saves the extracted text to a file.

    Args:
        text (str): The text to save.
        output_filepath (str): The path to the file to save to.
    """
    try:
        with open(output_filepath, "w", encoding="utf-8") as f:
            f.write(text)
        logging.info(f"Text successfully saved to {output_filepath}")
    except IOError as e:
        logging.error(f"Error saving text to file {output_filepath}: {e}")


def get_gemini_model(api_key, gemini_model_name):
    """Initializes and returns the Gemini model, checking for the API key."""
    if not api_key:
        logging.error("Google Gemini API key not set. Please set the 'GOOGLE_API_KEY' environment variable.")
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(gemini_model_name)


def chunk_text(text: str, max_chunk_size: int) -> list[str]:
    """
    Splits text into smaller parts (chunks).
    Uses approximate chunk length calculation.

    Args:
        text (str): Input text.
        max_chunk_size (int): Maximum chunk size in characters (approximate).

    Returns:
        list[str]: A list of text chunks.
    """
    chunks = []
    current_chunk = []
    current_length = 0

    # Split text into sentences
    sentences = text.split('.')
    for sentence in sentences:
        sentence_len = len(sentence) + 1  # +1 for period
        if current_length + sentence_len <= max_chunk_size:
            current_chunk.append(sentence)
            current_length += sentence_len
        else:
            if current_chunk:
                chunks.append(".".join(current_chunk) + ".")
            current_chunk = [sentence]
            current_length = sentence_len
    if current_chunk:
        chunks.append(".".join(current_chunk) + ".")
    return chunks


def summarize_text_with_gemini(
        model,
        text_to_summarize: str,
        max_output_tokens: int,
        temperature: float
) -> str:
    """
    Summarizes text using the Gemini model.
    Supports summarizing large texts by splitting them into chunks.

    Args:
        model: Initialized Gemini model.
        text_to_summarize (str): Text to summarize.
        max_output_tokens (int): Maximum number of tokens in the response.
        temperature (float): Generation temperature (0.0 - more deterministic, 1.0 - more creative).

    Returns:
        str: The generated summary or an error message.
    """
    if not model:
        return "Error: Gemini model not initialized. Check API key."

    if not text_to_summarize.strip():
        return "Error: Input text for summarization is empty."

    # Prompt for summarization
    base_prompt = "Provide a concise and objective summary of the following text in English, focusing on key ideas and facts. Present the summary as a list of bullet points for better readability. Avoid personal opinions and do not include additional content not present in the text. Ensure the summary is logically complete and no sentence is cut off:\n\n"

    if len(text_to_summarize) > MAX_TEXT_LENGTH_FOR_SINGLE_CALL:
        logging.info("Text is too long for a single request. Splitting into chunks and summarizing in parts.")
        chunks = chunk_text(text_to_summarize, max_chunk_size=MAX_TEXT_LENGTH_FOR_SINGLE_CALL)

        summaries = []
        for i, chunk in enumerate(chunks):
            logging.info(f"Summarizing chunk {i + 1}/{len(chunks)}...")
            prompt = base_prompt + "This is part of a larger document, so focus on the content of this specific section.\n\n" + chunk
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                    )
                )
                if response.candidates:
                    summaries.append(response.text)
                else:
                    logging.warning(f"Gemini did not generate text for chunk {i + 1}. Debug: {response}")
            except Exception as e:
                logging.error(f"An error occurred while calling Gemini API for chunk {i + 1}: {e}")
                return f"An error occurred while summarizing part of the document: {e}"

        if not summaries:
            return "Could not get any summaries from document parts."

        if len(summaries) > 1:
            logging.info("Combining and finally summarizing chunk summaries.")
            combined_summaries = "\n\n".join(summaries)
            final_prompt = base_prompt + "Summarize the following summaries to create one coherent and objective overall summary of the entire document. Focus on the most important points to create a brief and complete overview. Ensure the summary is logically complete and no sentence is cut off:\n\n" + combined_summaries
            try:
                final_response = model.generate_content(
                    final_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                    )
                )
                if final_response.candidates:
                    return textwrap.fill(final_response.text, width=80)
                else:
                    return f"Gemini did not generate final summary. Debug: {final_response}"
            except Exception as e:
                return f"An error occurred while calling Gemini API for final summarization: {e}"
        else:
            return textwrap.fill(summaries[0], width=80)
    else:
        prompt = base_prompt + text_to_summarize
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
            )
            if response.candidates:
                return textwrap.fill(response.text, width=80)
            else:
                return f"Gemini did not generate text. Perhaps there's an issue with the prompt or model. Debug: {response}"
        except Exception as e:
            return f"An error occurred while calling Gemini API: {e}"

if __name__ == "__main__":
    # Create the summaries folder if it doesn't exist
    os.makedirs(SUMMARIES_OUTPUT_FOLDER, exist_ok=True)

    # 1. Initialize Gemini model
    # The API_KEY variable is commented out in the original, assuming it should be set as an environment variable.
    # For demonstration purposes, I'll use a placeholder. In a real scenario, you'd uncomment and ensure it's loaded correctly.
    API_KEY = os.getenv('GOOGLE_API_KEY')
    gemini_model = get_gemini_model(API_KEY, GEMINI_MODEL_NAME)
    if not gemini_model:
        exit()  # Stop execution if API key is not set

    # Get a list of all PDF files in the specified folder
    pdf_files = [f for f in os.listdir(PDF_INPUT_FOLDER) if f.lower().endswith('.pdf')]

    if not pdf_files:
        logging.info(f"No PDF files found in '{PDF_INPUT_FOLDER}' for processing.")
    else:
        for pdf_file_name in pdf_files:
            pdf_path = os.path.join(PDF_INPUT_FOLDER, pdf_file_name)
            logging.info(f"\n--- Processing file: {pdf_file_name} ---")

            # 2. Extract text from PDF
            extracted_full_text = extract_text_from_pdf(pdf_path)

            if extracted_full_text:
                logging.info(f"Extracted text (first 500 characters): {extracted_full_text[:500]}...")

                # 3. Summarize text using Gemini
                logging.info("Summarizing text with Google Gemini...")
                summary = summarize_text_with_gemini(
                    gemini_model,
                    extracted_full_text,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    temperature=TEMPERATURE
                )

                print(f"\n--- Generated summary for {pdf_file_name} ---")
                print(summary)

                # 4. Save the summary to a separate file
                summary_file_name = os.path.splitext(pdf_file_name)[0] + '_summary.txt'
                summary_output_path = os.path.join(SUMMARIES_OUTPUT_FOLDER, summary_file_name)
                save_text_to_file(summary, summary_output_path)
            else:
                logging.warning(f"Could not extract text from {pdf_file_name}. Summarization not possible.")