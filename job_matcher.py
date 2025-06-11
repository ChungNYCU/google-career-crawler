#!/usr/bin/env python3
import os
import json
import ast
from pathlib import Path

import PyPDF2
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from openai import OpenAI

from job_detail import JobDetail

# Load .env file if present
load_dotenv()

console = Console()

# Configuration variables
RESUME_PATH = Path("Jun_2025_jesse_chung_resume.pdf")
JOBS_JSON_PATH = Path("jobs.json")
MODEL_NAME = "gpt-4.1-mini"

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    console.print("[red]Error:[/] OPENAI_API_KEY not set in .env", style="bold")
    raise SystemExit(1)
client = OpenAI(api_key=api_key)

class ResumeMatcher:
    def __init__(self, resume_path: Path, model: str):
        self.model = model
        self.resume_text = self._extract_text(resume_path)

    def _extract_text(self, pdf_path: Path) -> str:
        reader = PyPDF2.PdfReader(str(pdf_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)

    def analyze(self, job: JobDetail) -> dict:
        system_msg = {
            "role": "system",
            "content": (
                "You are an expert recruiter. "
                "Compare the resume and the job description, and return ONLY valid JSON using double quotes: "
                "{\"recommend\": score (0–10), \"analysis\": explanation}."
            )
        }
        user_msg = {
            "role": "user",
            "content": (
                f"=== RESUME ===\n{self.resume_text}\n\n"
                f"=== JOB DESCRIPTION ===\n{json.dumps(job.to_dict(), ensure_ascii=False)}"
            )
        }

        with console.status(f"[yellow]Analyzing match for job {job.id}…[/yellow]", spinner="dots"):
            resp = client.chat.completions.create(
                model=self.model,
                messages=[system_msg, user_msg],
                temperature=0.0
            )
        text = resp.choices[0].message.content.strip()

        # 嘗試 JSON 解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 再嘗試 Python literal 解析（支援單引號、Python dict）
            try:
                result = ast.literal_eval(text)
                if isinstance(result, dict):
                    return result
            except Exception:
                pass

        # 若前面都失敗，嘗試抽取大括號內字串後再解析
        import re
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            snippet = m.group(0)
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                try:
                    return ast.literal_eval(snippet)
                except Exception:
                    pass

        raise ValueError(f"Unable to parse response into dict:\n{text}")

def main():
    # Validate files
    if not RESUME_PATH.exists():
        console.print(f"[red]Error:[/] Resume not found: {RESUME_PATH}", style="bold")
        raise SystemExit(1)
    if not JOBS_JSON_PATH.exists():
        console.print(f"[red]Error:[/] jobs.json not found: {JOBS_JSON_PATH}", style="bold")
        raise SystemExit(1)

    # 1. Load jobs.json
    with open(JOBS_JSON_PATH, "r", encoding="utf-8") as f:
        jobs_meta = json.load(f)

    jobs = [JobDetail(**m) for m in jobs_meta]
    matcher = ResumeMatcher(RESUME_PATH, model=MODEL_NAME)

    table = Table(title="Resume ↔ Job Matches")
    table.add_column("Job ID", style="cyan", no_wrap=True)
    table.add_column("Job Title", style="cyan", no_wrap=True)
    table.add_column("Recommend", justify="center")
    table.add_column("Analysis", overflow="fold")

    # 2. Analyze & update
    for idx, job in enumerate(jobs):
        if job.recommend and job.analysis:
            continue
        res = matcher.analyze(job)
        # 寫回 JSON 結構
        jobs_meta[idx]["recommend"] = int(res.get("recommend", 0))
        jobs_meta[idx]["analysis"] = str(res.get("analysis", "")).replace("\n", " ")
        # 加入表格
        table.add_row(job.id, job.title, str(jobs_meta[idx]["recommend"]), jobs_meta[idx]["analysis"])
        table.add_row("---", "---", "-", "---")

    # 3. Save updated file
    with open(JOBS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs_meta, f, ensure_ascii=False, indent=2)

    console.print(table)

if __name__ == "__main__":
    main()
