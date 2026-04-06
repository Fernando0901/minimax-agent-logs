#!/usr/bin/env python3
"""
task_watcher.py — Monitors /root/agent-tasks/pending/ for new task files.
Executes them via the Multi-Agent Self-Fix Pipeline (orchestrator.py).
For "corrígelo" / fix tasks: runs orchestrator.py
For other tasks: runs Claude Code CLI directly.
Runs as a systemd service, completely independent of minimax-agent Docker container.
"""

import asyncio
import os
import sys
import shutil
import httpx
import fcntl
import hashlib
from pathlib import Path
from datetime import datetime

PENDING_DIR = Path("/root/agent-tasks/pending")
COMPLETED_DIR = Path("/root/agent-tasks/completed")
FAILED_DIR = Path("/root/agent-tasks/failed")
QUEUE_DIR = Path("/root/agent-tasks/queued")
LOCK_FILE = Path("/root/agent-tasks/.watcher.lock")
POLL_INTERVAL = 5

# Add pipeline to path
sys.path.insert(0, "/root/minimax-agent/pipeline")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_USER_ID = os.environ.get("TELEGRAM_AUTHORIZED_USER_ID", "")

PENDING_DIR.mkdir(exist_ok=True, parents=True)
COMPLETED_DIR.mkdir(exist_ok=True, parents=True)
FAILED_DIR.mkdir(exist_ok=True, parents=True)
QUEUE_DIR.mkdir(exist_ok=True, parents=True)


def _escape_html(text: str) -> str:
    """Escape special HTML chars so Telegram HTML mode doesn't break."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def send_telegram(message: str, use_html: bool = True):
    """Send a message to Fernando via Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_USER_ID:
        print(f"[WARN] Telegram not configured: {message[:80]}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_USER_ID,
        "text": message,
    }
    if use_html:
        payload["parse_mode"] = "HTML"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=payload)
            data = r.json()
            if not data.get("ok"):
                print(f"[WARN] Telegram HTML send failed: {data.get('description')} — retrying plain")
                payload.pop("parse_mode", None)
                await client.post(url, json=payload)
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")


def _get_content_hash(file_path: Path) -> str:
    """Return MD5 hex digest of file bytes — used for deduplication."""
    return hashlib.md5(file_path.read_bytes()).hexdigest()


def _acquire_lock(lock_fd) -> bool:
    """
    Try to acquire exclusive lock on the given file descriptor.
    Returns True if lock acquired (caller MUST release), False if busy.
    """
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


def _release_lock(lock_fd) -> None:
    """Release the exclusive lock."""
    fcntl.flock(lock_fd, fcntl.LOCK_UN)


def _is_fix_task(task_content: str) -> bool:
    """
    Heuristic: does this task look like a self-fix task?
    Returns True for tasks containing: 'corrígelo', 'corrige', 'fix',
    'error', 'bug', 'problema', 'fallo'
    """
    content_lower = task_content.lower()
    fix_keywords = [
        "corrígelo", "corrige", "fix", "bug", "error", "problema",
        "fallo", "self-fix", "self_fix", "mejora", "corrámpelo",
    ]
    return any(kw in content_lower for kw in fix_keywords)


async def execute_via_orchestrator(task_file: Path) -> tuple[bool, str, str]:
    """
    Run the Multi-Agent Self-Fix Pipeline on the task file.
    Imports and calls orchestrator.run_pipeline() synchronously.
    Returns (success, stdout_output, stderr_output).
    """
    from orchestrator import run_pipeline

    task_path_str = str(task_file)
    try:
        session_dir = await run_pipeline(task_path_str)
        output = f"Pipeline session: {session_dir}"
        return True, output, ""
    except Exception as e:
        import traceback
        return False, "", f"Orchestrator error: {e}\n{traceback.format_exc()}"


async def execute_via_claude(task_file: Path) -> tuple[bool, str, str]:
    """Run Claude Code CLI directly on the task file (for non-fix tasks)."""
    task_content = task_file.read_text()
    proc = await asyncio.create_subprocess_shell(
        "claude --print",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd="/root"
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=task_content.encode()), timeout=600
        )
        success = proc.returncode == 0
        return success, stdout.decode() if stdout else "", stderr.decode() if stderr else ""
    except asyncio.TimeoutError:
        proc.kill()
        return False, "", "Timeout after 600s"


async def process_task(task_file: Path):
    """Process a single task file: route to pipeline or Claude, move, notify."""
    content = task_file.read_text()
    first_line = content.split("\n")[0].replace("# ", "").strip()

    is_fix = _is_fix_task(content)
    task_type = "🔧 <b>Pipeline</b>" if is_fix else "🤖 <b>Claude</b>"

    await send_telegram(
        f"{task_type} <b>Ejecutando:</b> {_escape_html(first_line)}\n"
        f"<i>Esperando 2-10 minutos...</i>"
    )

    if is_fix:
        success, stdout, stderr = await execute_via_orchestrator(task_file)
    else:
        success, stdout, stderr = await execute_via_claude(task_file)

    output = stdout if success else stderr
    result_section = (
        f"\n---\n## Execution Result\n"
        f"**Status:** {'✅ SUCCESS' if success else '❌ FAILED'}\n"
        f"**Timestamp:** {datetime.now().isoformat()}\n"
        f"**Output:**\n{output[:2000]}\n"
    )
    task_file.write_text(content + result_section)

    dest_dir = COMPLETED_DIR if success else FAILED_DIR
    shutil.move(str(task_file), str(dest_dir / task_file.name))

    if success:
        preview = _escape_html(stdout[:600].strip()) if stdout.strip() else "(sin output)"
        await send_telegram(
            f"✅ <b>Tarea completada:</b> {_escape_html(first_line)}\n\n"
            f"<pre>{preview}</pre>"
        )
    else:
        preview = _escape_html(stderr[:400].strip()) if stderr.strip() else "(sin stderr)"
        await send_telegram(
            f"❌ <b>Tarea fallida:</b> {_escape_html(first_line)}\n\n"
            f"<pre>{preview}</pre>"
        )


async def watch_pending():
    """Main loop: poll pending/ every 5 seconds for new .md files."""
    # Seed by content hash (not filename) for true deduplication
    processed_hashes: set[str] = set()
    for f in PENDING_DIR.glob("*.md"):
        processed_hashes.add(_get_content_hash(f))
    for f in QUEUE_DIR.glob("*.md"):
        processed_hashes.add(_get_content_hash(f))

    # Ensure lock file exists
    LOCK_FILE.parent.mkdir(exist_ok=True)
    LOCK_FILE.touch(exist_ok=True)

    print(f"[task_watcher] Started. Watching {PENDING_DIR}. Seeded: {len(processed_hashes)} hashes")
    print(f"[task_watcher] Fix tasks → orchestrator | Other tasks → claude --print")
    print(f"[task_watcher] Busy pipeline → queued/ | Deduplication by content hash")

    while True:
        try:
            # STEP 1: Drain queued/ first if pipeline is free
            lock_fd = os.open(str(LOCK_FILE), os.O_RDWR)
            pipeline_free = _acquire_lock(lock_fd)
            if pipeline_free:
                _release_lock(lock_fd)
                for queued_file in sorted(QUEUE_DIR.glob("*.md")):
                    h = _get_content_hash(queued_file)
                    if h not in processed_hashes:
                        processed_hashes.add(h)
                        print(f"[task_watcher] Drain queued: {queued_file.name}")
                        asyncio.create_task(process_task(queued_file))
                        await asyncio.sleep(1)  # brief gap between queued items

            # STEP 2: Process new files in pending/
            for task_file in sorted(PENDING_DIR.glob("*.md")):
                h = _get_content_hash(task_file)
                if h in processed_hashes:
                    continue

                # Try to acquire pipeline lock
                if not pipeline_free:
                    lock_fd = os.open(str(LOCK_FILE), os.O_RDWR)
                    pipeline_free = _acquire_lock(lock_fd)

                if not pipeline_free:
                    # Pipeline busy — move to queued/
                    dest = QUEUE_DIR / task_file.name
                    shutil.move(str(task_file), str(dest))
                    print(f"[task_watcher] Pipeline busy, queued: {task_file.name}")
                    continue

                processed_hashes.add(h)
                print(f"[task_watcher] New task: {task_file.name} (hash={h[:8]})")
                asyncio.create_task(process_task(task_file))
                await asyncio.sleep(1)

            if pipeline_free:
                _release_lock(lock_fd)

        except Exception as e:
            print(f"[ERROR] Watcher loop: {e}")
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(watch_pending())
