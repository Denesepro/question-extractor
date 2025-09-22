# PDF to Web Form: Automated Question Extractor and Uploader

This project provides a complete, two-stage solution for automating the process of transferring multiple-choice quizzes from a PDF file into a web-based platform.

1.  **AI-Powered Extraction (`extractor.py`):** A Python script that leverages the **Gemini 1.5 Flash** multimodal AI to analyze images of PDF pages. It intelligently extracts all questions, options, and correct answers, saving them into a structured `JSON` file.
2.  **Web Automation (`automator.py`):** A second Python script using **Selenium** that reads the generated `JSON` file. It then automatically logs into a target website (e.g., biazmoon.com), navigates to the question creation form, and systematically enters and submits each question.

---

## ✨ Key Features

* **Accurate PDF to JSON Extraction**: Directly converts quiz questions from PDF files into a clean, structured `JSON` format.
* **Powered by Gemini AI**: Utilizes the powerful `gemini-1.5-flash` model for high-accuracy visual content analysis.
* **Flexible Answer Key Processing**: Can extract correct answers from either a dedicated answer key page or by detecting **bolded** text within the options.
* **Advanced Text Post-Processing**: Automatically cleans the extracted text, correcting common punctuation and spacing errors (e.g., for Persian ZWNJ).
* **End-to-End Web Automation**: Handles the entire web workflow, from logging in to filling out and submitting forms.
* **Multi-Tag Support**: Allows for a predefined list of tags to be automatically added to each question on the website.
* **Robust Error Handling**: Implements smart waits and error management to ensure the scripts run stably.

---

## ⚙️ How It Works

The project follows a simple, two-script workflow:

1.  **Initial Input**: A quiz file, `Test.pdf`.
    `⬇️`
2.  **Script 1: `extractor.py`**:
    * Converts the PDF into a series of high-resolution images.
    * Sends each image to the **Gemini API** for analysis.
    * Receives and processes the structured data.
    * Saves the output to `questions.json`.
    `⬇️`
3.  **Intermediate File**: `questions.json`.
    `⬇️`
4.  **Script 2: `automator.py`**:
    * Reads and parses `questions.json`.
    * Launches a browser with **Selenium** and logs into the target website.
    * Navigates to the "Create Question" page.
    * Loops through each question, populating the web form and submitting it.
`⬇️`
5.  **Final Result**: All questions are successfully uploaded to the website.

---

## 📦 Prerequisites & Installation

To run this project, you will need the following:

1.  **Python 3.7+**
2.  **Poppler**: The `pdf2image` library requires this utility. Download it and add its `bin` directory to your system's `PATH`.
    * [Download Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases/)
3.  **Python Libraries**: Install the necessary packages using pip:
    ```bash
    pip install google-generativeai selenium pdf2image Pillow
    ```
4.  **Google Chrome** and a compatible **ChromeDriver**. (Note: Modern versions of Selenium can manage ChromeDriver automatically).

---

## 🔧 Configuration

Before running the scripts, you must configure the following settings:

#### In `extractor.py`:

* `API_KEY`: Set your Google AI Studio API key.
    ```python
    API_KEY = "YOUR_GOOGLE_AI_API_KEY"
    ```

#### In `automator.py`:

* **Login Credentials**: Enter your username and password for the target website.
    ```python
    YOUR_USERNAME = "your_email@example.com"
    YOUR_PASSWORD = "your_password"
    ```
    > **⚠️ Security Warning**: Never commit this file with your real credentials to a public GitHub repository.

* **URLs and Settings**: Adjust the `LOGIN_URL`, `CREATE_QUESTION_URL`, `TAGS_TO_ADD`, and `QQQ_SESSION_NUMBER` variables to match your specific needs.

---

## 🚀 Usage Guide

1.  **Clone the Repository**:
    ```bash
    git clone [https://github.com/your-username/your-repo-name.git](https://github.com/your-username/your-repo-name.git)
    cd your-repo-name
    ```
2.  **Install Prerequisites**: Follow the installation guide above to set up your environment.
3.  **Configure Scripts**: Edit the Python files to set your API key and user credentials.
4.  **Place PDF**: Put your quiz PDF file in the main project directory.
5.  **Run the Extractor Script**:
    ```bash
    python extractor.py
    ```
    The script will prompt you for the PDF filename, the total number of questions, and the answer key method. Once finished, it will generate a `_extracted_questions.json` file.

6.  **Run the Automator Script**:
    ```bash
    python automator.py
    ```
    This will launch the browser, log in, and begin uploading the questions automatically.

---

## 📁 Project Structure
