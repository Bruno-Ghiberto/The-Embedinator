## 1. Pre-Launch Steps

### 1.1 Set Environment Variable

```bash
# INITIATE SESSION IN ONE LINER COMMAND (Fixed: detached mode + proper config)
cd ~/Documents/Projects/The-Embedinator && \
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 && \
tmux has-session -t The_Embedinator 2>/dev/null || \
  tmux new-session -d -s The_Embedinator -x 240 -y 60 && \
tmux set-option -t The_Embedinator -g mouse on && \
tmux set-option -t The_Embedinator -g history-limit 50000 && \
tmux set-option -t The_Embedinator -g pane-border-status top && \
tmux set-option -t The_Embedinator -g pane-border-format " #{pane_index}: #{pane_title} " && \
tmux set-option -t The_Embedinator -g pane-border-style "fg=colour240" && \
tmux set-option -t The_Embedinator -g pane-active-border-style "fg=colour75,bold" && \
tmux set-option -t The_Embedinator -g status-right "#{pane_title} | %H:%M" && \
tmux set-option -t The_Embedinator -g status-interval 5 && \
tmux set-option -t The_Embedinator -g display-panes-time 3000 && \
tmux set-option -t The_Embedinator -g pane-base-index 1 && \
tmux set-option -t The_Embedinator -g base-index 1 && \
tmux set-option -t The_Embedinator -g remain-on-exit off && \
tmux attach-session -t The_Embedinator

# REQUIRED — enables Agent Teams multi-pane coordination
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```
