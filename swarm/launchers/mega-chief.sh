#!/usr/bin/env bash
# mega-chief.sh — Swarm host orchestrator for dialogue-memory
# Launches Wave agents in parallel tmux windows
#
# Usage: bash mega-chief.sh [--wave W0|W1|W2|all] [--model sonnet|haiku]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SWARM_DIR="$(dirname "$SCRIPT_DIR")"
PROMPTS_DIR="$SWARM_DIR/prompts"
LOGS_DIR="$SWARM_DIR/logs"
REPO_DIR="/home/pook/dialogue-memory"

# PATH setup
source ~/.bashrc 2>/dev/null || true
source ~/.cargo/env 2>/dev/null || true
export PATH="$HOME/.npm-global/bin:$HOME/.bun/bin:$HOME/.local/bin:$HOME/bin:$PATH"

# Defaults
WAVE="W0"
MODEL="sonnet"
MAX_TURNS=30
STAGGER=3

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --wave) WAVE="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --max-turns) MAX_TURNS="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

mkdir -p "$LOGS_DIR"

echo "=== dialogue-memory mega-chief ==="
echo "Wave: $WAVE | Model: $MODEL | Max turns: $MAX_TURNS"
echo "Prompts: $PROMPTS_DIR"
echo ""

# Discover prompts for this wave
if [[ "$WAVE" == "all" ]]; then
    PROMPT_FILES=("$PROMPTS_DIR"/*-prompt.md)
else
    PROMPT_FILES=("$PROMPTS_DIR"/${WAVE}-*-prompt.md)
fi

if [[ ${#PROMPT_FILES[@]} -eq 0 ]]; then
    echo "No prompts found for wave $WAVE"
    exit 1
fi

SESSION="dm-swarm-${WAVE}"
tmux kill-session -t "$SESSION" 2>/dev/null || true

FIRST=true
for PROMPT_FILE in "${PROMPT_FILES[@]}"; do
    TASK_ID=$(basename "$PROMPT_FILE" -prompt.md)
    LOG_FILE="$LOGS_DIR/${TASK_ID}.log"

    # Generate standalone launcher for this agent
    LAUNCHER="$LOGS_DIR/${TASK_ID}-launch.sh"
    cat > "$LAUNCHER" << LAUNCHER_EOF
#!/usr/bin/env bash
set -euo pipefail
source ~/.bashrc 2>/dev/null || true
source ~/.cargo/env 2>/dev/null || true
export PATH="\$HOME/.npm-global/bin:\$HOME/.bun/bin:\$HOME/.local/bin:\$HOME/bin:\$PATH"
cd "$REPO_DIR"
echo "[\$(date)] Agent ${TASK_ID} starting (model: ${MODEL})" | tee "$LOG_FILE"
cat "$PROMPT_FILE" | claude --print \\
    --allowedTools 'Edit,Write,Read,Bash(*),Grep,Glob' \\
    --model "$MODEL" \\
    --max-turns $MAX_TURNS \\
    2>&1 | tee -a "$LOG_FILE"
EC=\$?
echo "[\$(date)] Agent ${TASK_ID} finished (exit: \$EC)" | tee -a "$LOG_FILE"
LAUNCHER_EOF
    chmod +x "$LAUNCHER"

    if [[ "$FIRST" == true ]]; then
        tmux new-session -d -s "$SESSION" -n "$TASK_ID" "bash $LAUNCHER"
        FIRST=false
    else
        sleep $STAGGER
        tmux new-window -t "$SESSION" -n "$TASK_ID" "bash $LAUNCHER"
    fi
    echo "[+] Launched $TASK_ID in tmux:$SESSION"
done

echo ""
echo "=== Swarm launched: ${#PROMPT_FILES[@]} agents in tmux session '$SESSION' ==="
echo "Monitor: tmux attach -t $SESSION"
echo "Logs:    ls $LOGS_DIR/${WAVE}-*.log"
