#compdef set-work set-close set-merge set-new set-list set-project set-jira
# Zsh completions for wt-* commands

# Get list of active worktree change-ids
_wt_get_worktrees() {
    local worktrees
    worktrees=(${(f)"$(set-list 2>/dev/null | grep -E '^\s+\w' | awk '{print $1}')"})
    echo "${worktrees[@]}"
}

# Get list of remote change branches
_wt_get_remote_branches() {
    git fetch -q 2>/dev/null
    local branches
    branches=(${(f)"$(git branch -r 2>/dev/null | grep 'origin/change/' | sed 's|.*origin/change/||')"})
    echo "${branches[@]}"
}

_set-work() {
    local -a worktrees remotes
    worktrees=(${(f)"$(_wt_get_worktrees)"})
    remotes=(${(f)"$(_wt_get_remote_branches)"})

    _arguments \
        '1:change-id:(${worktrees} ${remotes})' \
        '--terminal[Open in terminal instead of Zed]' \
        '--help[Show help]'
}

_set-close() {
    local -a worktrees
    worktrees=(${(f)"$(_wt_get_worktrees)"})

    _arguments \
        '1:change-id:(${worktrees})' \
        '--force[Force delete without confirmation]' \
        '--keep-branch[Keep the branch after closing]' \
        '--delete-remote[Delete remote branch too]' \
        '--help[Show help]'
}

_set-merge() {
    local -a worktrees
    worktrees=(${(f)"$(_wt_get_worktrees)"})

    _arguments \
        '1:change-id:(${worktrees})' \
        '--target[Target branch to merge into]:branch:' \
        '--no-delete[Keep branch after merge]' \
        '--help[Show help]'
}

_set-new() {
    _arguments \
        '1:change-id:' \
        '--new[Force create new branch even if remote exists]' \
        '--project[Project name]:project:' \
        '--help[Show help]'
}

_set-list() {
    _arguments \
        '--all[List all projects]' \
        '--remote[List remote change branches]' \
        '--project[Filter by project]:project:' \
        '--help[Show help]'
}

_set-project() {
    local -a subcmds
    subcmds=(
        'init:Register current directory as a project'
        'list:List registered projects'
        'remove:Remove a project from registry'
        'default:Set default project'
    )

    _arguments \
        '1:command:->command' \
        '*::arg:->args'

    case $state in
        command)
            _describe 'command' subcmds
            ;;
        args)
            case ${words[1]} in
                remove|default)
                    local projects
                    projects=(${(f)"$(set-project list 2>/dev/null | grep -E '^\s+\w' | awk '{print $1}' | sed 's/(default)//')"})
                    _arguments '1:project:(${projects})'
                    ;;
            esac
            ;;
    esac
}

_set-jira() {
    local -a subcmds
    subcmds=(
        'init:Configure JIRA credentials'
        'test:Test JIRA connection'
        'show:Show current configuration'
        'log:Log work time'
        'sync:Sync proposals to JIRA'
        'create-story:Create JIRA story from proposal'
        'rename-story:Rename a JIRA story'
        'move-subtask:Move subtask to another parent'
    )

    _arguments \
        '1:command:->command' \
        '*::arg:->args'

    case $state in
        command)
            _describe 'command' subcmds
            ;;
        args)
            case ${words[1]} in
                log)
                    _arguments \
                        '1:duration:(30m 1h 2h 3h 4h 1d)' \
                        '2:comment:'
                    ;;
                sync)
                    _arguments \
                        '--dry-run[Only show what would be done]' \
                        '--project[Project to sync]:project:' \
                        '--yes[Non-interactive mode]'
                    ;;
            esac
            ;;
    esac
}

# Register completions based on which command is being completed
case $service in
    set-work) _set-work ;;
    set-close) _set-close ;;
    set-merge) _set-merge ;;
    set-new) _set-new ;;
    set-list) _set-list ;;
    set-project) _set-project ;;
    set-jira) _set-jira ;;
esac
