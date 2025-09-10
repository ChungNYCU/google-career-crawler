import discord
import asyncio
import os
import re
import random
import sys
import csv
import json
from dotenv import load_dotenv
from datetime import datetime

# =========================
#  Environment variables
# =========================
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PYTHON_PATH = os.getenv("PYTHON_PATH", sys.executable or "python")
DATA_FOLDER_PATH = os.getenv("DATA_FOLDER_PATH")

# Optional timeout (in seconds). If empty => no timeout
CRAWLER_TIMEOUT_ENV = os.getenv("CRAWLER_TIMEOUT_SEC", "").strip()
CRAWLER_TIMEOUT_SEC: float | None = float(
    CRAWLER_TIMEOUT_ENV) if CRAWLER_TIMEOUT_ENV else None

# Channel IDs and script paths
DISCORD_L3_CHANNEL_ID = int(os.getenv("DISCORD_L3_CHANNEL_ID"))
DISCORD_L4_CHANNEL_ID = int(os.getenv("DISCORD_L4_CHANNEL_ID"))
DISCORD_US_CHANNEL_ID = int(os.getenv("DISCORD_US_CHANNEL_ID"))
DISCORD_NV_CHANNEL_ID = int(os.getenv("DISCORD_NV_CHANNEL_ID", "0"))
GC_SCRIPT_L3 = os.getenv("GC_SCRIPT_L3")
GC_SCRIPT_L4 = os.getenv("GC_SCRIPT_L4")
GC_SCRIPT_US = os.getenv("GC_SCRIPT_US")
NV_SCRIPT_TW = os.getenv("NV_SCRIPT_TW")
TAGS = {
    GC_SCRIPT_L3: 'L3',
    GC_SCRIPT_L4: 'L4',
    GC_SCRIPT_US: 'US',
    NV_SCRIPT_TW: 'NV_TW'
}

# Execution interval settings (seconds)
MIN_INTERVAL_SEC = 60 * 60
MAX_INTERVAL_SEC = 90 * 60

# Discord single message character limit
DISCORD_CHAR_LIMIT = 2000

# Job history tracking
JOB_HISTORY_FILE = os.getenv("JOB_HISTORY_FILE", f"{DATA_FOLDER_PATH}job_history.csv")

# =========================
#  Discord client setup
# =========================
intents = discord.Intents.default()
client = discord.Client(intents=intents)
_started = False  # Prevent multiple task spawns when on_ready fires more than once


# =========================
#  Utility functions
# =========================
def chunk_message(text: str, limit: int = DISCORD_CHAR_LIMIT) -> list[str]:
    """
    Split a long text into chunks that do not exceed the Discord character limit.
    Prefers splitting at newline characters if possible.

    Args:
        text (str): The full text to split.
        limit (int): Maximum characters per chunk.

    Returns:
        list[str]: List of message chunks.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + limit
        if end < len(text):
            nl = text.rfind("\n", start, end)
            if nl != -1 and nl > start:
                end = nl + 1
        chunks.append(text[start:end])
        start = end
    return chunks


async def run_cmd(cmd: list[str], timeout: float | None = None) -> tuple[int, str, str]:
    """
    Run an external command asynchronously using asyncio subprocess.
    This prevents blocking the Discord event loop.

    Args:
        cmd (list[str]): The command and arguments to run.
        timeout (float | None): Timeout in seconds, or None for no timeout.

    Returns:
        tuple[int, str, str]: (return_code, stdout_text, stderr_text)

    Raises:
        asyncio.TimeoutError: If the command times out (only when timeout is set).
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        if timeout is None:
            stdout, stderr = await proc.communicate()
        else:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(proc.communicate(), timeout=5)
        except asyncio.TimeoutError:
            pass
        raise
    return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")


def parse_crawler_output(output: str) -> tuple[int, int, str | None, str | None]:
    """
    Parse crawler script output and extract job changes.

    Args:
        output (str): The raw output string from crawler script.

    Returns:
        tuple:
            - new_count (int): Number of new jobs.
            - removed_count (int): Number of removed jobs.
            - new_block (str | None): Formatted string of new jobs, or None if none.
            - removed_block (str | None): Formatted string of removed jobs, or None if none.
    """
    text = (output or "").strip()
    new_match = re.search(r"New:\s*(\d+)", text)
    removed_match = re.search(r"Removed:\s*(\d+)", text)
    new_count = int(new_match.group(1)) if new_match else 0
    removed_count = int(removed_match.group(1)) if removed_match else 0

    new_block = None
    new_section = re.search(r"New:\s*\d+\s*(.*?)Removed:", text, re.DOTALL)
    if new_section or new_count > 0:
        block_match = new_section or re.search(
            r"New:\s*\d+\s*(.*)", text, re.DOTALL)
        if block_match:
            lines = block_match.group(1).strip().splitlines()
            entries = []
            for i in range(0, len(lines), 2):
                if i + 1 >= len(lines):
                    break
                job_line = lines[i].strip()
                link_line = lines[i + 1].strip()
                if job_line.startswith('+') and "_" in job_line:
                    jid, title = job_line[1:].split("_", 1)
                    entries.append(f"- [{jid}] [{title}]({link_line})")
            if entries:
                new_block = "🆕 New Positions:\n" + "\n".join(entries)

    removed_block = None
    removed_section = re.search(r"Removed:\s*\d+\s*(.*)", text, re.DOTALL)
    if removed_section:
        lines = removed_section.group(1).strip().splitlines()
        entries = []
        for line in lines:
            s = line.strip()
            if s.startswith('-') and "_" in s:
                jid, title = s[1:].split("_", 1)
                entries.append(f"- [{jid}] {title}")
        if entries:
            removed_block = "❌ Removed Positions:\n" + "\n".join(entries)

    return new_count, removed_count, new_block, removed_block


def get_total_jobs_by_script(script_path: str) -> int:
    """
    Get the current total number of jobs for a given script by reading the JSON file.

    Args:
        script_path (str): Path to the script file.

    Returns:
        int: Total number of jobs, or -1 if error.
    """
    # Extract script name without extension
    script_name = os.path.splitext(os.path.basename(script_path))[0]
    json_file = f"{DATA_FOLDER_PATH}{script_name}_jobs.json"
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.loads(f.read())

        if isinstance(data, list):
            return len(data)
        elif isinstance(data, dict):
            return 1
        else:
            return 0
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return -1



def log_job_stats(level: str, total_jobs: int, new_jobs: int, removed_jobs: int):
    """
    Log job statistics to CSV file for historical tracking.

    Args:
        level (str): Job level (e.g., 'L3', 'L4').
        total_jobs (int): Current total job count.
        new_jobs (int): Number of new jobs.
        removed_jobs (int): Number of removed jobs.
    """
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')

    # Create CSV with headers if it doesn't exist
    file_exists = os.path.exists(JOB_HISTORY_FILE)

    try:
        with open(JOB_HISTORY_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(
                    ['date', 'time', 'level', 'total_jobs', 'new_jobs', 'removed_jobs'])
            writer.writerow([date_str, time_str, level,
                            total_jobs, new_jobs, removed_jobs])
    except Exception as e:
        print(f"⚠️ Failed to log job stats: {e!r}", flush=True)


async def send_changes_if_any(channel: discord.abc.Messageable, script_path: str, output: str):
    """
    Send job changes to a Discord channel if there are any.

    Args:
        channel (discord.abc.Messageable): The Discord channel to send messages to.
        script_path (str): The crawler script path (used for message header).
        output (str): Raw crawler output.
    """
    new_count, removed_count, new_block, removed_block = parse_crawler_output(
        output)


    # Get actual total jobs from JSON file using script path
    total_jobs = get_total_jobs_by_script(script_path)

    # Determine job tag from script path
    tag = TAGS.get(script_path, os.path.splitext(os.path.basename(script_path))[0])

    # Log stats regardless of whether there are changes (for tracking purposes)
    log_job_stats(tag, total_jobs, new_count, removed_count)

    if new_count == 0 and removed_count == 0:
        return

    msg_lines = [
        f"📢 {os.path.basename(script_path)} Update:\nNew: {new_count}\nRemoved: {removed_count}"]
    if new_block:
        msg_lines.append(new_block)
    if removed_block:
        msg_lines.append(removed_block)

    full_msg = "\n\n".join(msg_lines)
    for part in chunk_message(full_msg):
        await channel.send(part)


# =========================
#  Main crawler loop
# =========================
async def crawl_loop(channel_id: int, script_path: str):
    """
    Background loop that runs a crawler script repeatedly and reports results to a Discord channel.

    Args:
        channel_id (int): The target Discord channel ID.
        script_path (str): Path to the crawler script.
    """
    await client.wait_until_ready()

    channel = client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await client.fetch_channel(channel_id)
        except Exception as e:
            print(
                f"❌ Cannot access channel ID {channel_id}: {e!r}", flush=True)
            return

    if not script_path or not os.path.exists(script_path):
        print(f"❌ Script not found: {script_path!r}", flush=True)
        return

    while True:
        start = datetime.now()
        print(
            f"⏳ [{start.strftime('%H:%M:%S')}] Running {script_path}...", flush=True)

        try:
            rc, output, error = await run_cmd([PYTHON_PATH, script_path], timeout=CRAWLER_TIMEOUT_SEC)
        except asyncio.TimeoutError:
            print(
                f"⚠️ {script_path} timed out (> {CRAWLER_TIMEOUT_SEC}s).", flush=True)
        except Exception as e:
            print(f"💥 Failed to run {script_path}: {e!r}", flush=True)
        else:
            end = datetime.now()
            duration = (end - start).total_seconds()
            print(
                f"✅ [{end.strftime('%H:%M:%S')}] {script_path} finished in {duration:.1f}s (rc={rc})", flush=True)
            if error:
                print(f"[ERR] {script_path} stderr:\n{error}", flush=True)
            if rc != 0:
                print(
                    f"⚠️ {script_path} exited with non-zero code: {rc}", flush=True)

            try:
                await send_changes_if_any(channel, script_path, output)
            except Exception as e:
                print(
                    f"⚠️ Failed to send changes to Discord: {e!r}", flush=True)

        # Wait a random interval before the next run
        wait = random.randint(MIN_INTERVAL_SEC, MAX_INTERVAL_SEC)
        print(f"🕒 Next run for {script_path} in {wait//60} min", flush=True)
        await asyncio.sleep(wait)


# =========================
#  Events
# =========================
@client.event
async def on_ready():
    """
    Event handler triggered when the bot successfully connects to Discord.
    Starts the crawler loops only once.
    """
    global _started
    if _started:
        return
    _started = True

    print(f"✅ Bot logged in as {client.user}")
    print("🔍 Visible channels:")
    for guild in client.guilds:
        print(f"Server: {guild.name}")
        for channel in guild.text_channels:
            print(f"  - {channel.name} (ID: {channel.id})")

    asyncio.create_task(crawl_loop(DISCORD_L3_CHANNEL_ID, GC_SCRIPT_L3))
    asyncio.create_task(crawl_loop(DISCORD_L4_CHANNEL_ID, GC_SCRIPT_L4))
    asyncio.create_task(crawl_loop(DISCORD_US_CHANNEL_ID, GC_SCRIPT_US))
    
    asyncio.create_task(crawl_loop(DISCORD_NV_CHANNEL_ID, NV_SCRIPT_TW))


# =========================
#  Run bot
# =========================
client.run(DISCORD_BOT_TOKEN)
