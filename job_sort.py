#!/usr/bin/env python3
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Configuration
JOBS_JSON_PATH = Path("jobs.json")
OUTPUT_JSON_PATH = Path("jobs_sorted.json")

console = Console()

def main():
    if not JOBS_JSON_PATH.exists():
        console.print(f"[red]Error:[/] {JOBS_JSON_PATH} not found.", style="bold")
        return

    # 1. Load jobs.json
    with open(JOBS_JSON_PATH, "r", encoding="utf-8") as f:
        jobs = json.load(f)

    # 2. Sort by recommend (descending)
    jobs_sorted = sorted(
        jobs,
        key=lambda job: job.get("recommend", 0),
        reverse=True
    )

    # 3. Write sorted list back to a new JSON
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs_sorted, f, ensure_ascii=False, indent=2)

    # 4. Display a quick table
    table = Table(title="Jobs Sorted by Recommend")
    table.add_column("Job ID", style="cyan", no_wrap=True)
    table.add_column("Recommend", justify="center")
    table.add_column("Title", overflow="fold")

    for job in jobs_sorted:
        table.add_row(
            job.get("id", ""),
            str(job.get("recommend", 0)),
            job.get("title", "")
        )

    console.print(table)
    console.print(f"\nSorted jobs written to [green]{OUTPUT_JSON_PATH}[/green]")

if __name__ == "__main__":
    main()
