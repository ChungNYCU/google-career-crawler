import discord
import asyncio
import subprocess
import os
import re
import random
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()
DISCORD_BOT_TOKEN       = os.getenv("DISCORD_BOT_TOKEN")
PYTHON_PATH             = os.getenv("PYTHON_PATH", "python")
# IDs for two channels
DISCORD_L3_CHANNEL_ID   = int(os.getenv("DISCORD_L3_CHANNEL_ID"))
DISCORD_L4_CHANNEL_ID   = int(os.getenv("DISCORD_L4_CHANNEL_ID"))
# Paths to the two different GoogleCareer scripts
GC_SCRIPT_L3            = os.getenv("GC_SCRIPT_L3")
GC_SCRIPT_L4            = os.getenv("GC_SCRIPT_L4")

# Execution interval settings (seconds)
MIN_INTERVAL_SEC = 420  # 7 minutes
MAX_INTERVAL_SEC = 900  # 15 minutes

# Discord message character limit
DISCORD_CHAR_LIMIT = 2000

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def chunk_message(text: str, limit: int = DISCORD_CHAR_LIMIT) -> list[str]:
    """Split a long text into chunks not exceeding the character limit."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + limit
        if end < len(text):
            # try break at newline
            nl = text.rfind("\n", start, end)
            if nl != -1 and nl > start:
                end = nl + 1
        chunks.append(text[start:end])
        start = end
    return chunks


async def crawl_loop(channel_id: int, script_path: str):
    """Continuously run the given GoogleCareer script and post updates to a Discord channel."""
    await client.wait_until_ready()
    channel = client.get_channel(channel_id)
    if channel is None:
        print(f"❌ Cannot find channel ID {channel_id}. Check permissions and ID.")
        return

    while True:
        start = datetime.now()
        print(f"⏳ [{start.strftime('%H:%M:%S')}] Running {script_path}...", flush=True)

        try:
            result = subprocess.run(
                [PYTHON_PATH, script_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30000
            )
        except subprocess.TimeoutExpired:
            print(f"⚠️ {script_path} timed out (>5m), skipping this round.")
            await asyncio.sleep(random.randint(MIN_INTERVAL_SEC, MAX_INTERVAL_SEC))
            continue

        end = datetime.now()
        duration = (end - start).total_seconds()
        print(f"✅ [{end.strftime('%H:%M:%S')}] {script_path} finished in {duration:.1f}s", flush=True)

        output = result.stdout.strip()
        error  = result.stderr.strip()
        if error:
            print(f"[ERR] {script_path} stderr:\n{error}", flush=True)

        # parse new/removed counts
        new_match     = re.search(r"New:\s*(\d+)", output)
        removed_match = re.search(r"Removed:\s*(\d+)", output)
        new_count     = int(new_match.group(1)) if new_match else 0
        removed_count = int(removed_match.group(1)) if removed_match else 0

        msg_lines = [f"📢 {os.path.basename(script_path)} Update:\nNew: {new_count}\nRemoved: {removed_count}"]

        # extract "New" entries
        new_section = re.search(r"New:\s*\d+\s*(.*?)Removed:", output, re.DOTALL)
        if new_section or new_count > 0:
            block = (new_section or re.search(r"New:\s*\d+\s*(.*)", output, re.DOTALL)).group(1)
            lines = block.strip().splitlines()
            entries = []
            for i in range(0, len(lines), 2):
                if i+1 >= len(lines): break
                job_line = lines[i].strip()
                link_line = lines[i+1].strip()
                if job_line.startswith('+') and "_" in job_line:
                    jid, title = job_line[1:].split("_", 1)
                    entries.append(f"- [{jid}] [{title}]({link_line})")
            if entries:
                msg_lines.append("🆕 New Positions:\n" + "\n".join(entries))

        # extract "Removed" entries
        removed_section = re.search(r"Removed:\s*\d+\s*(.*)", output, re.DOTALL)
        if removed_section:
            lines = removed_section.group(1).strip().splitlines()
            entries = []
            for line in lines:
                if line.strip().startswith('-') and "_" in line:
                    jid, title = line.strip()[1:].split("_", 1)
                    entries.append(f"- [{jid}] {title}")
            if entries:
                msg_lines.append("❌ Removed Positions:\n" + "\n".join(entries))

        # send only if there is any change
        if new_count > 0 or removed_count > 0:
            full_msg = "\n\n".join(msg_lines)
            chunks = chunk_message(full_msg)
            for part in chunks:
                await channel.send(part)

        # wait random interval
        wait = random.randint(MIN_INTERVAL_SEC, MAX_INTERVAL_SEC)
        print(f"🕒 Next run for {script_path} in {wait//60} min", flush=True)
        await asyncio.sleep(wait)


@client.event
async def on_ready():
    print(f"✅ Bot logged in as {client.user}")
    print("🔍 Visible channels:")
    for guild in client.guilds:
        print(f"Server: {guild.name}")
        for channel in guild.text_channels:
            print(f"  - {channel.name} (ID: {channel.id})")
    client.loop.create_task(crawl_loop(DISCORD_L3_CHANNEL_ID, GC_SCRIPT_L3))
    client.loop.create_task(crawl_loop(DISCORD_L4_CHANNEL_ID, GC_SCRIPT_L4))

client.run(DISCORD_BOT_TOKEN)
