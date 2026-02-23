"""Local LLM task extraction + markdown vault management.

Uses Ollama to extract actionable tasks from estimate transcriptions and
maintains a per-job markdown vault for richer LLM context over time.
"""

import json
import logging
import re
import urllib.request
import urllib.error
from pathlib import Path

import config
import database

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Markdown vault helpers
# ---------------------------------------------------------------------------

def _safe_name(text):
    """Convert text to a filesystem-safe name."""
    return re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")[:60]


def _vault_dir(token_str, job_name):
    """Return (and create) the vault directory for a job."""
    d = config.ESTIMATES_VAULT / token_str / _safe_name(job_name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_estimate_markdown(estimate, job_name, transcription, photo_captions=None):
    """Write an individual estimate markdown file and update the job summary."""
    token_str = estimate["token"]
    vault = _vault_dir(token_str, job_name)

    date_str = estimate["created_at"][:10]
    eid = estimate["id"]
    filename = f"estimate_{date_str}_{eid}.md"

    lines = [
        f"# Estimate #{eid} — {job_name}",
        f"**Date:** {date_str}",
        "",
        "## Transcription",
        transcription or "(no audio)",
        "",
    ]

    if photo_captions:
        lines.append("## Photo Captions")
        for cap in photo_captions:
            lines.append(f"- {cap}")
        lines.append("")

    (vault / filename).write_text("\n".join(lines), encoding="utf-8")

    # Update job summary
    _update_summary(vault, job_name)


def _update_summary(vault, job_name):
    """Rebuild _summary.md from all estimate files in the vault."""
    estimate_files = sorted(vault.glob("estimate_*.md"))
    lines = [f"# {job_name} — Estimate Summary", ""]
    for f in estimate_files:
        lines.append(f.read_text(encoding="utf-8"))
        lines.append("\n---\n")
    (vault / "_summary.md").write_text("\n".join(lines), encoding="utf-8")


def get_job_context(token_str, job_name):
    """Read the job summary markdown for LLM context. Returns '' if none."""
    vault = _vault_dir(token_str, job_name)
    summary = vault / "_summary.md"
    if summary.exists():
        return summary.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# Ollama task extraction
# ---------------------------------------------------------------------------

def _call_ollama(prompt, system_prompt=""):
    """Send a prompt to Ollama and return the response text."""
    payload = {
        "model": config.OLLAMA_MODEL,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        config.OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        logger.warning(f"Ollama call failed: {e}")
        return ""


def extract_tasks(estimate, job_name, transcription, photo_captions=None):
    """Extract tasks from an estimate transcription using Ollama.

    Returns a list of task name strings. Failures return an empty list
    (non-blocking — the estimate still completes).
    """
    token_str = estimate["token"]
    job_id = estimate["job_id"]

    # Build context from vault
    context = get_job_context(token_str, job_name)

    # Build few-shot from past company tasks
    existing_tasks = database.get_job_tasks(job_id)
    examples = ""
    if existing_tasks:
        task_names = [t["name"] for t in existing_tasks[:20]]
        examples = "Previously identified tasks for this job:\n" + "\n".join(f"- {n}" for n in task_names) + "\n\n"

    # Build caption text
    caption_text = ""
    if photo_captions:
        caption_text = "\nPhoto captions from the job site:\n" + "\n".join(f"- {c}" for c in photo_captions) + "\n"

    system_prompt = (
        "You are a construction project task extractor. Given a voice memo transcription "
        "from a job site estimate walkthrough, extract a list of discrete actionable tasks "
        "that need to be performed. Return ONLY a JSON array of task name strings. "
        "Each task should be concise (5-15 words). Do not include commentary."
    )

    prompt = ""
    if context:
        prompt += f"Project context:\n{context}\n\n"
    if examples:
        prompt += examples
    prompt += f"New estimate transcription:\n{transcription}\n"
    if caption_text:
        prompt += caption_text
    prompt += "\nExtract the tasks as a JSON array:"

    response = _call_ollama(prompt, system_prompt)
    if not response:
        return []

    # Parse JSON array from response
    try:
        # Try direct parse first
        tasks = json.loads(response)
        if isinstance(tasks, list):
            return [str(t).strip() for t in tasks if str(t).strip()]
    except json.JSONDecodeError:
        pass

    # Try extracting JSON array from markdown code block or mixed text
    match = re.search(r"\[.*?\]", response, re.DOTALL)
    if match:
        try:
            tasks = json.loads(match.group())
            if isinstance(tasks, list):
                return [str(t).strip() for t in tasks if str(t).strip()]
        except json.JSONDecodeError:
            pass

    logger.warning(f"Could not parse tasks from Ollama response: {response[:200]}")
    return []


def process_estimate_tasks(estimate):
    """Full pipeline: extract tasks, store in DB, update vault.

    Called by task_queue after successful transcription.
    """
    job_id = estimate["job_id"]
    token_str = estimate["token"]
    job_name = estimate.get("job_name", "")
    transcription = estimate.get("transcription", "")

    if not transcription:
        return

    # Get photo captions for context
    photos = database.get_all_job_photos_for_job(job_id)
    photo_captions = [p["caption"] for p in photos if p.get("caption")]

    # Write vault markdown
    write_estimate_markdown(estimate, job_name, transcription, photo_captions)

    # Extract tasks via Ollama
    task_names = extract_tasks(estimate, job_name, transcription, photo_captions)
    for name in task_names:
        database.create_job_task(job_id, token_str, name, source="ai")

    if task_names:
        logger.info(f"Extracted {len(task_names)} tasks for estimate {estimate['id']}")


def test_extraction(text, model=None):
    """Quick test function for comparing models. Call from Python REPL."""
    old_model = config.OLLAMA_MODEL
    if model:
        config.OLLAMA_MODEL = model
    try:
        result = _call_ollama(
            f"Extract tasks from this construction estimate:\n{text}\n\nReturn JSON array:",
            "You are a construction project task extractor. Return ONLY a JSON array of task name strings.",
        )
        print(f"Model: {config.OLLAMA_MODEL}")
        print(f"Response: {result}")
        try:
            tasks = json.loads(result)
            print(f"Parsed tasks: {tasks}")
        except json.JSONDecodeError:
            print("Could not parse as JSON")
        return result
    finally:
        config.OLLAMA_MODEL = old_model
