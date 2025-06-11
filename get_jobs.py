import json
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from urllib.parse import urlparse

# Settings
CHROMEDRIVER_PATH = r'C:\Repos\google-career-crawler\chromedriver-win64\chromedriver.exe'
TARGET_BASE = 'https://www.google.com/about/careers/applications/jobs/results/'
FILTER_PREFIX = TARGET_BASE
LOCATION = 'Taiwan'
TARGET_LEVEL = 'EARLY' # INTERN_AND_APPRENTICE, EARLY, MID, ADVANCED, DIRECTOR_PLUS
QUERY_PARAMS = f'?q=%22Software%20Engineer%22&location={LOCATION}&target_level={TARGET_LEVEL}'
JOBS_JSON = 'jobs.json'

# Read previous jobs data
old_jobs = []
if os.path.exists(JOBS_JSON):
    with open(JOBS_JSON, 'r', encoding='utf-8') as f:
        old_jobs = json.load(f)
old_ids = {job['id'] for job in old_jobs}

# Initialize Selenium
options = Options()

options.add_argument("--disable-logging")
options.add_argument("--log-level=3")                   # 0 = INFO, 1 = WARNING, 2 = LOG_ERROR, 3 = LOG_FATAL
options.add_experimental_option("excludeSwitches", ["enable-logging"])

options.add_argument("--start-maximized")
driver = webdriver.Chrome(service=Service(CHROMEDRIVER_PATH), options=options)

results = []
seen_ids = set()
page = 1

# Crawl through pages
while True:
    url = TARGET_BASE + QUERY_PARAMS + f'&page={page}'
    print(f"[Paging] Crawling page {page}: {url}")
    driver.get(url)
    time.sleep(3)

    links = set(
        a.get_attribute('href') for a in driver.find_elements(By.TAG_NAME, 'a')
        if a.get_attribute('href') and a.get_attribute('href').startswith(FILTER_PREFIX)
    )
    if not links:
        print("⚠️ No more job listings found, stopping pagination.")
        break

    for href in links:
        path = urlparse(href).path.rstrip('/')
        last_segment = path.split('/')[-1]
        if '-' in last_segment:
            id_, title = last_segment.split('-', 1)
            if id_ not in seen_ids:
                seen_ids.add(id_)
                results.append({'id': id_, 'title': title, 'link': href})
    page += 1

driver.quit()

# Compare and identify new and removed jobs
new_ids = {job['id'] for job in results}
added = [job for job in results if job['id'] not in old_ids]
removed = [job for job in old_jobs if job['id'] not in new_ids]

print(f"\n✅ New jobs: {len(added)}")
for job in added:
    print(f" + {job['id']} — {job['title']}")

print(f"\n✅ Removed jobs: {len(removed)}")
for job in removed:
    print(f" - {job['id']} — {job['title']}")

# Update jobs.json
with open(JOBS_JSON, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("\n🎯 jobs.json has been updated.")
