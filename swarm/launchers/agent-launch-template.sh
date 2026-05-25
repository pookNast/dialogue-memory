#!/usr/bin/env bash
# Template for dialogue-memory swarm agent launchers
# Usage: Copy and customize TASK_ID, PROMPT_FILE, MODEL
set -euo pipefail

TASK_ID="${TASK_ID:-W0-S0}"
PROMPT_FILE="${PROMPT_FILE:-$(dirname "$0")/../prompts/${TASK_ID}-prompt.md}"
MODEL="${MODEL:-sonnet}"
MAX_TURNS="${MAX_TURNS:-30}"
LOG_DIR="$(dirname "$0")/../logs"
REPO_DIR="/home/pook/dialogue-memory"

# PATH setup
source ~/.bashrc 2>/dev/null || true
source ~/.cargo/env 2>/dev/null || true
export PATH="$HOME/.npm-global/bin:$HOME/.bun/bin:$HOME/.local/bin:$HOME/bin:$PATH"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/${TASK_ID}.log"

echo "[$(date)] Starting agent ${TASK_ID} (model: ${MODEL})" | tee "$LOG_FILE"

if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "FATAL: prompt file not found: $PROMPT_FILE" | tee -a "$LOG_FILE"
    exit 1
fi

cd "$REPO_DIR"

cat "$PROMPT_FILE" | claude --print \
    --allowedTools 'Edit,Write,Read,Bash(*),Grep,Glob' \
    --model "$MODEL" \
    --max-turns "$MAX_TURNS" \
    2>&1 | tee -a "$LOG_FILE"

EC=$?
echo "[$(date)] Agent ${TASK_ID} exited with code ${EC}" | tee -a "$LOG_FILE"
exit $EC
