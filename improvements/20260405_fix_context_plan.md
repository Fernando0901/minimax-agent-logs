# Fix Implementation Plan — 20260405_192045

## Problem Statement
When `execute_self_fix()` sends a fix task to Claude Code CLI via task_watcher, it only passes the last 10 items from `conversation_history` which is derived from `conversation_store.json`. This lacks:
- The actual Telegram messages exchanged
- Bot response content
- User message content with full context

Fernando wants: **the last 7 Telegram chat messages** (user + bot), plus logs, so Claude Code has full context of what failed.

---

## Files to Modify

| File | Change |
|------|--------|
| `agent/self_improve.py` | Modify `execute_self_fix()` to include last 7 raw Telegram messages |
| `agent/brain.py` | Ensure `simple_chat()` passes the current exchange's raw messages, not just stored history |

---

## Current Behavior (execute_self_fix line 426-516)

```python
# Currently uses:
recent_msgs = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
context = "\n".join([
    f"{m['role']}: {str(m.get('content',''))[:200]}"
    for m in recent_msgs
])
```

Issues:
1. Only passes last 10 items (Fernando wants 7)
2. `conversation_history` is loaded from `conversation_store.json` — it has only `role` and `content` fields
3. No distinction between user messages and bot responses in the context block

---

## Proposed Behavior

### Step 1: Track Raw Telegram Messages

The `conversation_store.json` already saves history as:
```json
{"8288612046": [
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]}
```

But this loses the Telegram-specific context (message IDs, timestamps). For the fix task context, we need to show the last 7 exchanges clearly labeled as `[USER]` or `[BOT]` with the actual text.

### Step 2: Modify execute_self_fix()

Change the context building from:
```python
recent_msgs = conversation_history[-10:]
context = "\n".join([
    f"{m['role']}: {str(m.get('content',''))[:200]}"
    for m in recent_msgs
])
```

To:
```python
# Always use last 7 exchanges (14 messages = user+bot pairs)
recent_msgs = conversation_history[-14:] if len(conversation_history) >= 14 else conversation_history
context = "\n".join([
    f"[{'👤 USER' if m['role']=='user' else '🤖 BOT'}] {str(m.get('content',''))[:300]}"
    for m in recent_msgs
])
```

### Step 3: Include Tool Call Results in Context

Currently the audit section shows errors separately. For better context, also include a summary of the last few tool calls with their results:

```python
# Add last 5 tool calls to context
tool_events = today_events("tool_call", limit=5)
tool_section = "\n## Recent Tool Calls\n"
for ev in tool_events:
    tool_section += f"- **{ev.get('tool_name')}**: {str(ev.get('result',''))[:150]}\n"
```

---

## Implementation

### Change 1: self_improve.py — execute_self_fix()

```python
# Line ~441: Change from 10 to 14 (7 pairs of user+bot)
recent_msgs = conversation_history[-14:] if len(conversation_history) >= 14 else conversation_history

# Line ~443-446: Change context formatting to show role clearly
context = "\n".join([
    f"[{'👤 USER' if m['role']=='user' else '🤖 BOT'}] {str(m.get('content',''))[:300]}"
    for m in recent_msgs
])
```

### Change 2: self_improve.py — Add Tool Summary Section

After the audit section, add a compact tool call summary for the last 5 tool calls.

---

## Testing

After implementing:
1. Ask the bot something that triggers a tool call
2. Say "corrígelo" to trigger `execute_self_fix()`
3. Check the task file at `/root/agent-tasks/pending/fix_*.md`
4. Verify it contains `[👤 USER]` and `[🤖 BOT]` labels for last 7 exchanges
5. Verify tool call summary is present

---

## Risk Assessment

- **Risk:** Low — only changes string formatting in task file generation
- **No breaking changes:** Does not modify `brain.py` interface or `main.py`
- **No new dependencies:** Uses existing `audit_logger` functions
- **Rollback:** Easy — revert the two string formatting lines in `execute_self_fix()`

---

## Status

⏳ Waiting for Fernando's approval before implementing