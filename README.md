# google-career-crawler

# Google Career Tracker 🤖

Automatically track new or removed Software Engineer positions at Google Careers during team-match.

## 🔍 Overview

**What it does:**  
This tool scrapes Google Careers pages for "Software Engineer" roles in Taiwan (or any configured query), automatically paging through results, and tracks which jobs are newly posted or removed since the last check.

**Why it exists:**  
During Google’s internal team-match process, it’s easy to miss new openings or changes. This tracker alerts candidates to position updates so they never miss an opportunity.

---

## ⚙️ Features

- **Automatic pagination**: Crawls all available pages until no more listings.
- **Link parsing**: Extracts every job link and parses into:
  - `id` – the job’s numeric identifier  
  - `title` – the slugified job name  
  - `link` – full job URL
- **Change detection**: Compares current results to the previous `jobs.json`:
  - **New roles** – jobs not present in the previous run  
  - **Removed roles** – jobs present before but no longer available
- **Persistent storage**: Updates and overwrites `jobs.json` after each run.

---

## 🛠️ Installation

1. **Clone the repo**  
   ```bash
   git clone https://github.com/your-username/google-career-tracker.git
   cd google-career-tracker
   ```

2. **Install dependencies**

   ```bash
   pip install selenium
   ```

3. **Download ChromeDriver**

   * Ensure it matches your Chrome version
   * Place it in the project folder, e.g.:
     `./chromedriver-win64/chromedriver.exe`
   * Or update `CHROMEDRIVER_PATH` in `script.py`
   * Go https://googlechromelabs.github.io/chrome-for-testing/#stable to download chromedriver

---

## 🚀 Usage

Run the script:

```bash
python get_jobs.py
```

* **First run**: creates `jobs.json` with current job listings.
* **Subsequent runs**:

  * Prints new and removed job IDs
  * Updates `jobs.json`

### Sample Output

```
[Page 1] Crawling: …&page=1
[Page 2] Crawling: …&page=2
⚠️ No more jobs – stopping.

✅ New jobs: 2
 + 907456711… — software-engineer-ii-bluetooth
 + 906123450… — software-engineer-gpu-google-cloud-platforms

✅ Removed jobs: 1
 - 905987654… — software-engineer-android-pixel

🎯 jobs.json updated.
```

---

## 📁 Project Structure

```
.
├─ script.py         # Main scraper + diff logic
├─ jobs.json         # Persisted job listings
└─ chromedriver…     # ChromeDriver executable
```

---

## 🔧 Customization

* **Change filter/query**: Adjust `QUERY_PARAMS` in `script.py` for other roles or regions.
* **Save format**: Add CSV or database output options.
* **Enhance tracking**: Add email/Slack notifications on changes.
* **Detail scraping**: Extend to fetch job descriptions or qualifications.

---

## 🧭 Roadmap

* [ ] Schedule daily runs (cron or GitHub Actions)
* [ ] Add notification support (e.g., Slack/email)
* [ ] Scrape job detail pages for full metadata
* [ ] Export to CSV, DB (SQLite/Postgres)

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repo
2. Create a feature branch (`git checkout -b feature-name`)
3. Commit and push changes
4. Open a pull request

---

## 📄 License

MIT License — see `LICENSE` file for details.

