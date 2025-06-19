import discord
import asyncio
import subprocess
import os
import re
import random
from dotenv import load_dotenv
from datetime import datetime

# === Load environment variables ===
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
PYTHON_PATH = os.getenv("PYTHON_PATH")


# === Execution interval settings (in seconds) ===
MIN_INTERVAL_SEC = 420   # Minimum interval: 7 minutes
MAX_INTERVAL_SEC = 900   # Maximum interval: 15 minutes

# === Initialize Discord client ===
intents = discord.Intents.default()
client = discord.Client(intents=intents)

async def check_and_notify():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)

    if channel is None:
        print(f"❌ Cannot find channel ID {CHANNEL_ID}. Please verify bot permissions and channel ID.")
        return

    while True:
        start_time = datetime.now()
        print(f"⏳ [{start_time.strftime('%H:%M:%S')}] Running GoogleCareer.py...", flush=True)

        try:
            result = subprocess.run(
                [PYTHON_PATH, "GoogleCareer.py"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=300  # Max wait time: 5 minutes
            )
        except subprocess.TimeoutExpired:
            print("⚠️ Script timeout (over 3 minutes). Skipping this round.")
            interval = random.randint(MIN_INTERVAL_SEC, MAX_INTERVAL_SEC)
            print(f"🕒 Next run scheduled in {interval // 60} minutes...")
            await asyncio.sleep(interval)
            continue

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"✅ [{end_time.strftime('%H:%M:%S')}] Script finished in {duration:.1f} seconds", flush=True)

        output = result.stdout.strip()
        error = result.stderr.strip()

        print(f"[LOG] stdout:\n{output}", flush=True)
        print(f"[LOG] stderr:\n{error}", flush=True)

        # Extract New / Removed job counts
        match_new = re.search(r"New:\s*(\d+)", output)
        match_removed = re.search(r"Removed:\s*(\d+)", output)
        new_count = int(match_new.group(1)) if match_new else 0
        removed_count = int(match_removed.group(1)) if match_removed else 0

        msg_parts = [f"📢 Google Careers Update:\nNew: {new_count}\nRemoved: {removed_count}"]

        # === Extract New section ===
        new_section_match = re.search(r"New:\s*\d+\s*(.*?)Removed:", output, re.DOTALL)
        if not new_section_match and new_count > 0:
            new_section_match = re.search(r"New:\s*\d+\s*(.*)", output, re.DOTALL)

        if new_section_match:
            new_section = new_section_match.group(1).strip().splitlines()
            new_entries = []
            for i in range(0, len(new_section), 2):
                if i + 1 >= len(new_section):
                    break
                job_line = new_section[i].strip()
                link_line = new_section[i + 1].strip()
                if job_line.startswith('+'):
                    job_id_title = job_line[1:].strip()
                    if "_" in job_id_title:
                        job_id, title = job_id_title.split("_", 1)
                        new_entries.append(f"- [{job_id}] [{title}]({link_line})")
            if new_entries:
                msg_parts.append("🆕 New Positions:\n" + "\n".join(new_entries))

        # === Extract Removed section ===
        removed_section_match = re.search(r"Removed:\s*\d+\s*(.*)", output, re.DOTALL)
        if removed_section_match:
            removed_section = removed_section_match.group(1).strip().splitlines()
            removed_entries = []
            for line in removed_section:
                line = line.strip()
                if line.startswith('-'):
                    job_id_title = line[1:].strip()
                    if "_" in job_id_title:
                        job_id, title = job_id_title.split("_", 1)
                        removed_entries.append(f"- [{job_id}] {title}")
            if removed_entries:
                msg_parts.append("❌ Removed Positions:\n" + "\n".join(removed_entries))

        # Send message to Discord
        if new_count > 0 or removed_count > 0:
            await channel.send("\n\n".join(msg_parts))

        # === Wait for a random interval before next run ===
        interval = random.randint(MIN_INTERVAL_SEC, MAX_INTERVAL_SEC)
        print(f"🕒 Next run scheduled in {interval // 60} minutes...")
        await asyncio.sleep(interval)

@client.event
async def on_ready():
    print(f"✅ Bot successfully logged in as: {client.user}")
    print("🔍 Visible channels:")
    for guild in client.guilds:
        print(f"Server: {guild.name}")
        for channel in guild.text_channels:
            print(f"  - {channel.name} (ID: {channel.id})")
    client.loop.create_task(check_and_notify())

client.run(TOKEN)
