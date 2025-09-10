import os
import logging
from dotenv import load_dotenv
from typing import List

from google_career import GoogleCareer
from job_detail import JobDetail

load_dotenv()
DATA_FOLDER_PATH = os.getenv("DATA_FOLDER_PATH")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if __name__ == '__main__':
    crawler = GoogleCareer(
        query='software engineer',
        jobs_json=f'{DATA_FOLDER_PATH}us_jobs.json',
        location='United States',
        level=''
    )
    out: List[JobDetail] = crawler.run()
