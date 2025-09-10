#!/usr/bin/env python3
"""
NVIDIA Taiwan Career Crawler Script
Compatible with discord_bot.py crawl_loop pattern
"""

import asyncio
import os
from dotenv import load_dotenv
from nvidia_career import NvidiaCareer

load_dotenv()
DATA_FOLDER_PATH = os.getenv("DATA_FOLDER_PATH")
async def main():
    # Create NVIDIA career crawler for Taiwan Engineering positions
    crawler = NvidiaCareer(
        location_hierarchy="2fcb99c455831013ea52ed162d4932c0",  # Taiwan
        job_family_group="0c40f6bd1d8f10ae43ffaefd46dc7e78",    # Engineering
        jobs_json=f"{DATA_FOLDER_PATH}nvidia_script_tw_jobs.json"
    )
    
    # Run the crawler
    new_jobs = await crawler.run()
    
    return new_jobs

if __name__ == '__main__':
    asyncio.run(main())