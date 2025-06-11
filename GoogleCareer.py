import json
import os
import time
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from typing import List, Tuple

from job_detail import JobDetail

def default_options():
    opts = Options()
    opts.add_argument("--disable-logging")
    opts.add_argument("--log-level=3")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    opts.add_argument("--start-maximized")
    return opts


class GoogleCareer:
    """
    Crawler for Google Career job listings that compares new and removed positions,
    fetches detailed job page content, and parses key sections.
    """
    def __init__(
        self,
        chromedriver_path: str,
        location: str = "Taiwan",
        level: str = "EARLY",
        query: str = "Software Engineer",
        jobs_json: str = "jobs.json",
        base_url: str = "https://www.google.com/about/careers/applications/jobs/results/"
    ):
        self.chromedriver_path = chromedriver_path
        self.location = location
        self.level = level
        self.query = query
        self.jobs_json = jobs_json
        self.base_url = base_url
        self.filter_prefix = base_url

        raw = self._load_old_jobs()
        self.old_jobs: List[JobDetail] = []
        for item in raw:
            if isinstance(item, dict):
                jd = JobDetail.from_meta(item)
                if 'minimum_qualifications' in item:
                    sections = {
                        'Minimum qualifications': item.get('minimum_qualifications', []),
                        'Preferred qualifications': item.get('preferred_qualifications', []),
                        'About the job': item.get('about_the_job', []),
                        'Responsibilities': item.get('responsibilities', [])
                    }
                    jd = JobDetail.from_sections(jd, sections,
                                                  recommend=item.get('recommend'),
                                                  analysis=item.get('analysis'))
                self.old_jobs.append(jd)
        self.old_ids = {job.id for job in self.old_jobs}

    def _load_old_jobs(self) -> List[dict]:
        """Load previous jobs from JSON file and return raw list of dicts."""
        if os.path.exists(self.jobs_json):
            with open(self.jobs_json, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def _save_jobs(self, jobs: List[dict]):
        """Save job list to JSON file."""
        with open(self.jobs_json, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, indent=2, ensure_ascii=False)

    def _init_driver(self):
        """Initialize Chrome WebDriver with default options."""
        opts = default_options()
        service = Service(self.chromedriver_path)
        return webdriver.Chrome(service=service, options=opts)

    def crawl_all(self, delay: int = 3) -> List[dict]:
        """
        Crawl through paginated job listings and return list of meta dicts.
        """
        driver = self._init_driver()
        results, seen, page = [], set(), 1
        try:
            while True:
                url = f"{self.base_url}?q=%22{self.query.replace(' ', '%20')}%22&location={self.location}&target_level={self.level}&page={page}"
                print(f"[Paging] Crawling page {page}: {url}")
                driver.get(url)
                time.sleep(delay)
                links = {a.get_attribute('href') for a in driver.find_elements(by='tag name', value='a')
                         if a.get_attribute('href') and a.get_attribute('href').startswith(self.filter_prefix)}
                if not links:
                    break
                for href in links:
                    seg = urlparse(href).path.rstrip('/').split('/')[-1]
                    if '-' in seg:
                        id_, title = seg.split('-', 1)
                        if id_ not in seen:
                            seen.add(id_)
                            results.append({'id': id_, 'title': title, 'link': href})
                page += 1
        finally:
            driver.quit()
        return results

    def compare_jobs(self, metas: List[dict]) -> Tuple[List[dict], List[dict]]:
        """
        Compare new metadata with old JobDetail list.
        Returns list of added meta dicts and removed job dicts.
        """
        new_ids = {m['id'] for m in metas}
        # Metas to add
        added = [m for m in metas if m['id'] not in self.old_ids]
        # Old jobs to remove, serialized to dict
        removed = [job.to_dict() for job in self.old_jobs if job.id not in new_ids]
        return added, removed

    def fetch_job_detail(self, url: str, delay: int = 3) -> str:
        """Fetch HTML content of job detail page."""
        driver = self._init_driver()
        try:
            driver.get(url)
            time.sleep(delay)
            return driver.page_source
        finally:
            driver.quit()

    def parse_job_detail(self, html: str) -> dict:
        """Parse job page sections into dict."""
        soup = BeautifulSoup(html, 'html.parser')
        sections = {}
        for label in ['Minimum qualifications', 'Preferred qualifications', 'About the job', 'Responsibilities']:
            header = soup.find(lambda t: t.name in ['h2','h3','h4'] and label in t.text)
            if not header: continue
            items = []
            for sib in header.find_next_siblings():
                if sib.name in ['h2','h3','h4']: break
                if sib.name == 'ul': items.extend(li.get_text(strip=True) for li in sib.find_all('li'))
                elif sib.name == 'p': items.append(sib.get_text(strip=True))
            sections[label] = items
        return sections

    def run(self) -> List[JobDetail]:
        """
        Full workflow: crawl, detect new/removed, fetch/parse new job details,
        update jobs.json (remove only removed, add new, keep existing), and return list of JobDetail.
        """
        # Crawl current metadata
        metas = self.crawl_all()
        added_jobs, removed_jobs = self.compare_jobs(metas)
        removed_ids = {job['id'] for job in removed_jobs}

        print(f"New: {len(added_jobs)}")
        for meta in added_jobs:
            print(f" + {meta['id']}_{meta['title']}")

        print(f"Removed: {len(removed_ids)}")
        for meta in removed_jobs:
            print(f" + {meta['id']}_{meta['title']}")

        # Load existing raw data
        raw_existing = self._load_old_jobs()
        # Filter out removed by id
        kept = [item for item in raw_existing if item.get('id') not in removed_ids]

        # Process new additions
        new_details: List[JobDetail] = []
        detailed_dicts: List[dict] = []
        for meta in added_jobs:
            html = self.fetch_job_detail(meta['link'])
            base = JobDetail.from_meta(meta)
            sec = self.parse_job_detail(html)
            jd = JobDetail.from_sections(base, sec)
            new_details.append(jd)
            detailed_dicts.append(jd.to_dict())

        # Combine kept raw entries with new detailed dicts
        combined = kept + detailed_dicts

        # Save combined list
        self._save_jobs(combined)
        return new_details
    
if __name__ == '__main__':
    crawler = GoogleCareer(
        query='software engineer',
        chromedriver_path=r'C:\Repos\google-career-crawler\chromedriver-win64\chromedriver.exe'
    )
    out: List[JobDetail] = crawler.run()

