import json
import os
import time
import logging
import asyncio
import aiohttp
from typing import List, Dict, Tuple, Optional
from urllib.parse import urlencode

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class NvidiaJobDetail:
    def __init__(self, job_id: str, title: str, external_path: str, locations_text: str, posted_on: str):
        self.id = job_id
        self.title = title
        self.external_path = external_path
        self.locations_text = locations_text
        self.posted_on = posted_on
        self.link = f"https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite{external_path}"

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'external_path': self.external_path,
            'locations_text': self.locations_text,
            'posted_on': self.posted_on,
            'link': self.link
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            job_id=data['id'],
            title=data['title'],
            external_path=data['external_path'],
            locations_text=data['locations_text'],
            posted_on=data['posted_on']
        )

    @classmethod
    def from_api_response(cls, job_data: dict):
        job_id = job_data.get('bulletFields', [None])[0] if job_data.get('bulletFields') else None
        if not job_id:
            job_id = job_data.get('externalPath', '').split('_')[-1]
        
        title = job_data.get('title', '')
        external_path = job_data.get('externalPath', '')
        locations_text = job_data.get('locationsText', '')
        posted_on = job_data.get('postedOn', '')
        
        # Skip jobs with empty attributes (deleted jobs)
        if not title or not external_path or not locations_text or not posted_on:
            return None
        
        return cls(
            job_id=job_id,
            title=title,
            external_path=external_path,
            locations_text=locations_text,
            posted_on=posted_on
        )


class NvidiaCareer:
    def __init__(
        self,
        base_url: str = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs",
        location_hierarchy: str = "2fcb99c455831013ea52ed162d4932c0",  # Taiwan
        job_family_group: str = "0c40f6bd1d8f10ae43ffaefd46dc7e78",    # Engineering
        jobs_json: str = "nvidia_jobs.json",
        delay: float = 2.0
    ):
        self.base_url = base_url
        self.location_hierarchy = location_hierarchy
        self.job_family_group = job_family_group
        self.jobs_json = jobs_json
        self.delay = delay
        
        # Load existing jobs
        self.old_jobs = self._load_old_jobs()
        self.old_ids = {job.id for job in self.old_jobs}

    def _load_old_jobs(self) -> List[NvidiaJobDetail]:
        if not os.path.exists(self.jobs_json):
            return []
        
        try:
            with open(self.jobs_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            jobs = []
            for item in data:
                try:
                    # Skip jobs with empty attributes (deleted jobs)
                    if not item.get('title') or not item.get('external_path') or not item.get('locations_text') or not item.get('posted_on'):
                        continue
                    jobs.append(NvidiaJobDetail.from_dict(item))
                except Exception as e:
                    logging.warning(f"Skipped invalid job entry: {e}")
            return jobs
        except Exception as e:
            logging.error(f"Failed to read jobs JSON: {e}")
            return []

    def _save_jobs(self, jobs: List[NvidiaJobDetail]):
        try:
            with open(self.jobs_json, 'w', encoding='utf-8') as f:
                json.dump([job.to_dict() for job in jobs], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to write jobs JSON: {e}")

    async def fetch_jobs_page(self, session: aiohttp.ClientSession, offset: int = 0, limit: int = 20) -> Optional[dict]:
        """Fetch a page of jobs from NVIDIA Workday API"""
        
        # Use POST request with JSON body as Workday APIs typically expect
        payload = {
            "appliedFacets": {
                "locationHierarchy1": [self.location_hierarchy],
                "jobFamilyGroup": [self.job_family_group]
            },
            "limit": limit,
            "offset": offset,
            "searchText": ""
        }
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        try:
            async with session.post(self.base_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logging.error(f"HTTP {response.status} when fetching jobs page")
                    text = await response.text()
                    logging.error(f"Response: {text[:200]}...")
                    return None
        except Exception as e:
            logging.error(f"Error fetching jobs page: {e}")
            return None

    async def crawl_all_jobs(self) -> List[NvidiaJobDetail]:
        """Crawl all available jobs from NVIDIA careers"""
        all_jobs = []
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            offset = 0
            limit = 20
            total_jobs = None  # Store total from first page
            
            while True:
                logging.info(f"Fetching jobs from offset {offset}")
                
                # Add delay between requests
                if offset > 0:
                    await asyncio.sleep(self.delay)
                
                data = await self.fetch_jobs_page(session, offset, limit)
                if not data:
                    break
                
                job_postings = data.get('jobPostings', [])
                if not job_postings:
                    break
                
                # Store total from first page (API sometimes returns 0 on subsequent pages)
                if total_jobs is None:
                    total_jobs = data.get('total', 0)
                    logging.info(f"Total jobs available: {total_jobs}")
                
                # Process job postings
                for job_data in job_postings:
                    try:
                        job = NvidiaJobDetail.from_api_response(job_data)
                        if job:  # Only add valid jobs (skip deleted ones)
                            all_jobs.append(job)
                    except Exception as e:
                        logging.warning(f"Failed to parse job: {e}")
                
                # Check if we've reached the end using the total from first page
                if total_jobs and offset + len(job_postings) >= total_jobs:
                    break
                
                offset += limit
        
        logging.info(f"Crawled {len(all_jobs)} total jobs")
        return all_jobs

    def compare_jobs(self, new_jobs: List[NvidiaJobDetail]) -> Tuple[List[NvidiaJobDetail], List[NvidiaJobDetail]]:
        """Compare new jobs with old jobs to find additions and removals"""
        new_ids = {job.id for job in new_jobs}
        
        added_jobs = [job for job in new_jobs if job.id not in self.old_ids]
        removed_jobs = [job for job in self.old_jobs if job.id not in new_ids]
        
        return added_jobs, removed_jobs

    async def run(self) -> List[NvidiaJobDetail]:
        """Main method to crawl jobs and return new additions"""
        new_jobs = await self.crawl_all_jobs()
        added_jobs, removed_jobs = self.compare_jobs(new_jobs)
        
        print(f"New: {len(added_jobs)}")
        for job in added_jobs:
            print(f" + {job.id}_{job.title}")
            print(job.link)
        
        print(f"Removed: {len(removed_jobs)}")
        for job in removed_jobs:
            print(f" - {job.id}_{job.title}")
        
        # Save updated job list
        self._save_jobs(new_jobs)
        
        # Update old jobs for next comparison
        self.old_jobs = new_jobs
        self.old_ids = {job.id for job in new_jobs}
        
        return added_jobs

    # Synchronous wrapper for backward compatibility
    def run_sync(self) -> List[NvidiaJobDetail]:
        """Synchronous wrapper for the async run method"""
        return asyncio.run(self.run())


# For standalone usage
if __name__ == '__main__':
    async def main():
        # Taiwan Engineering jobs
        crawler = NvidiaCareer(
            location_hierarchy="2fcb99c455831013ea52ed162d4932c0",  # Taiwan
            job_family_group="0c40f6bd1d8f10ae43ffaefd46dc7e78",    # Engineering
            jobs_json="nvidia_tw_jobs.json"
        )
        new_jobs = await crawler.run()
        print(f"Found {len(new_jobs)} new jobs")

    asyncio.run(main())