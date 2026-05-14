#!/bin/bash

SESSION_NAME="The_Embedinator"
PROJECT_DIR="$HOME/Documents/Projects/The-Embedinator"

# 1. Vamos al directorio
cd "$PROJECT_DIR" || { echo "Error: Directorio no encontrado"; exit 1; }

# 2. Exportamos la variable (se heredará a la sesión de tmux si se crea ahora)
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# 3. Comprobamos si la sesión NO existe
if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    
    # Creamos la sesión en segundo plano
    tmux new-session -d -s "$SESSION_NAME" -x 240 -y 60
    
    # Opciones de Sesión (SIN -g, para que solo afecten a esta sesión)
    tmux set-option -t "$SESSION_NAME" mouse on
    tmux set-option -t "$SESSION_NAME" history-limit 50000
    tmux set-option -t "$SESSION_NAME" status-right "#{pane_title} | %H:%M"
    tmux set-option -t "$SESSION_NAME" status-interval 5
    tmux set-option -t "$SESSION_NAME" display-panes-time 3000
    tmux set-option -t "$SESSION_NAME" base-index 1
    tmux set-option -t "$SESSION_NAME" remain-on-exit off
    
    # Opciones de Ventana/Panel (Usando -w)
    tmux set-option -w -t "$SESSION_NAME" pane-border-status top
    tmux set-option -w -t "$SESSION_NAME" pane-border-format " #{pane_index}: #{pane_title} "
    tmux set-option -w -t "$SESSION_NAME" pane-border-style "fg=colour240"
    tmux set-option -w -t "$SESSION_NAME" pane-active-border-style "fg=colour75,bold"
    tmux set-option -w -t "$SESSION_NAME" pane-base-index 1
fi

# 4. Nos conectamos a la sesión (haya sido recién creada o ya existiera)
tmux attach-session -t "$SESSION_NAME"