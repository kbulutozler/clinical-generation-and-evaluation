# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
    . /etc/bashrc
fi

# User specific environment
if ! [[ "$PATH" =~ "$HOME/.local/bin:$HOME/bin:" ]]
then
    PATH="$HOME/.local/bin:$HOME/bin:$PATH"
fi
export PATH

# Uncomment the following line if you don't like systemctl's auto-paging feature:
# export SYSTEMD_PAGER=

# User specific aliases and functions

. "$HOME/.local/share/../bin/env"

# Load shared env
[ -f "$HOME/.bash_env" ] && . "$HOME/.bash_env"

# Convenience aliases
alias proj="cd \$PROJ_USER"
alias scr="cd \$SCRATCH_USER"
alias sq="squeue -u \$USER"
alias sa="sacct -u \$USER --format=JobID,JobName%15,Partition,AllocTRES%25,Elapsed,State -X"
