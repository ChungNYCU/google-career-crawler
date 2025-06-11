# Google Career Resume Matcher

A Python-based CLI toolchain that automatically crawls Google Career job listings, analyzes how well each job matches your resume using OpenAI's API, and sorts the results by recommendation score.

## Prerequisites

* Python 3.8 or higher
* Google Chrome browser
* ChromeDriver installed and accessible
* An OpenAI API key
* Windows users: \[Optional] `setup.bat` for one-step setup

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/ChungNYCU/google-career-crawler.git
   cd google-career-crawler
   ```
2. (Optional on Windows) Run the setup script to install dependencies:

   ```bat
   setup.bat
   ```

   Or install manually:

   ```bash
   python -m venv venv
   source venv/bin/activate    # On Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   ```
3. Create a `.env` file at the project root:

   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```
4. Go https://googlechromelabs.github.io/chrome-for-testing/#stable to download chromedriver
5. Place your PDF resume in the project folder and update `RESUME_PATH` in `job_matcher.py` if needed.

## Usage

Follow these three steps in order:

### 1. Crawl and update job listings

Run `GoogleCareer.py` to fetch the latest Google Career job postings, parse job details, and save them to `jobs.json`.

```bash
python GoogleCareer.py --chromedriver-path /path/to/chromedriver \
   --query "Software Engineer" --location "Taiwan" --level EARLY
```

This script will:

* Crawl all pages of Google Career for the given query, location, and level
* Compare with existing `jobs.json` to detect added or removed positions
* Fetch and parse job details for new listings
* Save the combined list back to `jobs.json`

### 2. Analyze resume-to-job matches

Run `job_matcher.py` to evaluate each job against your resume using the OpenAI model. It will enrich `jobs.json` with two new fields: `recommend` (0–10) and `analysis` (text explanation).

```bash
python job_matcher.py
```

This script will:

* Read your PDF resume and existing `jobs.json`
* Call the OpenAI API for each job to compute a match score and rationale
* Update `jobs.json` with `recommend` and `analysis` fields
* Display a summary table in the console

### 3. Sort jobs by recommendation

Run `job_sort.py` to generate a sorted JSON and table view of jobs by descending recommendation score.

```bash
python job_sort.py
```

This script will:

* Read the updated `jobs.json`
* Sort the job entries by the `recommend` field (highest to lowest)
* Write the sorted list to `jobs_sorted.json`
* Print a table of Job ID, Recommend, and Title

## Project Structure

```
├── GoogleCareer.py    # Crawls and updates jobs.json
├── job_detail.py      # Data class for job metadata and details
├── job_matcher.py     # Analyzes resume vs. jobs with OpenAI
├── job_sort.py        # Sorts and outputs jobs_sorted.json
├── requirements.txt   # Python dependencies
├── setup.bat          # Windows helper to install dependencies
├── .env               # Environment variables (OpenAI API key)
├── jobs.json          # Fetched and analyzed job data
└── jobs_sorted.json   # Sorted output by recommendation
```

## Customization

* **Query parameters**: Change `--query`, `--location`, and `--level` when running `GoogleCareer.py`.
* **Model**: Edit `MODEL_NAME` in `job_matcher.py` to use a different OpenAI model.
* **Resume path**: Update `RESUME_PATH` constant in `job_matcher.py` if your resume filename or location changes.

## Contributing

Contributions and issues are welcome! Please open a pull request or issue for improvements, bug fixes, or feature requests.

## License

MIT License. See `LICENSE` for details.
