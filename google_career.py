import json
import os
import time
import logging
from dotenv import load_dotenv
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from typing import List, Tuple, Optional
from dataclasses import dataclass, field

load_dotenv()
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

@dataclass
class JobDetail:
    """
    Data class representing detailed information for a Google Career job listing.
    """
    id: str
    title: str
    link: str
    minimum_qualifications: List[str] = field(default_factory=list)
    preferred_qualifications: List[str] = field(default_factory=list)
    about_the_job: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    recommend: Optional[int] = None
    analysis: Optional[str] = None

    @classmethod
    def from_meta(cls, meta: dict) -> "JobDetail":
        """Create a JobDetail with only id/title/link from meta dict."""
        return cls(id=meta['id'], title=meta['title'], link=meta['link'])

    @classmethod
    def from_sections(cls, job_detail: "JobDetail", sections: dict, recommend: int = None, analysis: str = None) -> "JobDetail":
        """
        Populate sections into an existing JobDetail instance.
        """
        job_detail.minimum_qualifications = sections.get('Minimum qualifications', [])
        job_detail.preferred_qualifications = sections.get('Preferred qualifications', [])
        job_detail.about_the_job = sections.get('About the job', [])
        job_detail.responsibilities = sections.get('Responsibilities', [])
        job_detail.recommend = recommend
        job_detail.analysis = analysis
        return job_detail

    def to_dict(self) -> dict:
        """Serialize JobDetail to JSON-friendly dict."""
        return {
            "id": self.id,
            "title": self.title,
            "link": self.link,
            "minimum_qualifications": self.minimum_qualifications,
            "preferred_qualifications": self.preferred_qualifications,
            "about_the_job": self.about_the_job,
            "responsibilities": self.responsibilities,
            "recommend": self.recommend,
            "analysis": self.analysis,
        }

def default_options():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-logging")
    opts.add_argument("--log-level=3")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--no-sandbox")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    return opts


class GoogleCareer:
    def __init__(
        self,
        chromedriver_path: str = CHROMEDRIVER_PATH,
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
            try:
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
            except Exception as e:
                logging.warning(f"Skipped invalid job entry: {e}")
        self.old_ids = {job.id for job in self.old_jobs}

    def _load_old_jobs(self) -> List[dict]:
        if os.path.exists(self.jobs_json):
            try:
                with open(self.jobs_json, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Failed to read jobs JSON: {e}")
        return []

    def _save_jobs(self, jobs: List[dict]):
        try:
            with open(self.jobs_json, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to write jobs JSON: {e}")

    def _init_driver(self):
        opts = default_options()
        service = Service(self.chromedriver_path)
        try:
            return webdriver.Chrome(service=service, options=opts)
        except Exception as e:
            logging.error(f"Failed to initialize ChromeDriver: {e}")
            raise

    def crawl_all(self, delay: int = 3) -> List[dict]:
        driver = self._init_driver()
        results, seen, page = [], set(), 1
        try:
            while True:
                url = f"{self.base_url}?q=%22{self.query.replace(' ', '%20')}%22&location={self.location}&target_level={self.level}&page={page}"
                logging.info(f"[Paging] Crawling page {page}: {url}")
                driver.get(url)
                time.sleep(delay)
                links = {a.get_attribute('href') for a in driver.find_elements(by='tag name', value='a')
                         if a.get_attribute('href') and a.get_attribute('href').startswith(self.filter_prefix)}
                if not links:
                    break
                for href in links:
                    try:
                        seg = urlparse(href).path.rstrip('/').split('/')[-1]
                        if '-' in seg:
                            id_, title = seg.split('-', 1)
                            if id_ not in seen:
                                seen.add(id_)
                                results.append({'id': id_, 'title': title, 'link': href})
                    except Exception as e:
                        logging.warning(f"Failed to parse job link {href}: {e}")
                page += 1
        finally:
            driver.quit()
        return results

    def compare_jobs(self, metas: List[dict]) -> Tuple[List[dict], List[dict]]:
        new_ids = {m['id'] for m in metas}
        added = [m for m in metas if m['id'] not in self.old_ids]
        removed = [job.to_dict() for job in self.old_jobs if job.id not in new_ids]
        return added, removed

    def fetch_job_detail(self, url: str, delay: int = 3) -> str:
        driver = self._init_driver()
        try:
            driver.get(url)
            time.sleep(delay)
            return driver.page_source
        except Exception as e:
            logging.error(f"Failed to fetch job detail from {url}: {e}")
            return ""
        finally:
            driver.quit()

    def parse_job_detail(self, html: str) -> dict:
        soup = BeautifulSoup(html, 'html.parser')
        sections = {}
        for label in ['Minimum qualifications', 'Preferred qualifications', 'About the job', 'Responsibilities']:
            try:
                header = soup.find(lambda t: t.name in ['h2', 'h3', 'h4'] and label in t.text)
                if not header:
                    continue
                items = []
                for sib in header.find_next_siblings():
                    if sib.name in ['h2', 'h3', 'h4']:
                        break
                    if sib.name == 'ul':
                        items.extend(li.get_text(strip=True) for li in sib.find_all('li'))
                    elif sib.name == 'p':
                        items.append(sib.get_text(strip=True))
                sections[label] = items
            except Exception as e:
                logging.warning(f"Failed to parse section {label}: {e}")
        return sections

    def run(self) -> List[JobDetail]:
        metas = self.crawl_all()
        added_jobs, removed_jobs = self.compare_jobs(metas)
        removed_ids = {job['id'] for job in removed_jobs}

        print(f"New: {len(added_jobs)}")
        for meta in added_jobs:
            print(f" + {meta['id']}_{meta['title']}\n{meta['link']}")

        print(f"Removed: {len(removed_jobs)}")
        for meta in removed_jobs:
            print(f" - {meta['id']}_{meta['title']}")

        raw_existing = self._load_old_jobs()
        kept = [item for item in raw_existing if item.get('id') not in removed_ids]

        new_details, detailed_dicts = [], []
        for meta in added_jobs:
            html = self.fetch_job_detail(meta['link'])
            if not html:
                continue
            base = JobDetail.from_meta(meta)
            sec = self.parse_job_detail(html)
            jd = JobDetail.from_sections(base, sec)
            new_details.append(jd)
            detailed_dicts.append(jd.to_dict())

        combined = kept + detailed_dicts
        self._save_jobs(combined)
        return new_details

if __name__ == '__main__':
    crawler = GoogleCareer(
        query='software engineer',
        chromedriver_path=CHROMEDRIVER_PATH
    )
    out: List[JobDetail] = crawler.run()
