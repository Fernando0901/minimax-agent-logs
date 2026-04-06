#!/usr/bin/env python3
"""
Pipeline Orchestrator — Multi-Agent Self-Fix Pipeline
Runs agents 1→7 sequentially, manages session state, and coordinates
post-pipeline actions (GitHub push, Telegram, PostgreSQL).
"""

import asyncio
import os
import re
import sys
import json
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# Pipeline paths
PIPELINE_DIR = Path("/root/minimax-agent/pipeline")
SESSIONS_DIR = PIPELINE_DIR / "sessions"
AGENTS_DIR = PIPELINE_DIR / "agents"

# Ensure sessions directory exists
SESSIONS_DIR.mkdir(exist_ok=True, parents=True)
