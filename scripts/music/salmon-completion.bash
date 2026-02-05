#!/bin/bash
# Bash completion for salmon-upload script

_salmon_complete() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # If completing first argument
    if [ $COMP_CWORD -eq 1 ]; then
        # Check if user is typing an absolute path
        if [[ "$cur" == /* ]]; then
            # Use default file/directory completion for absolute paths
            COMPREPLY=( $(compgen -d -- "$cur") )
        else
            # Complete with directories in Deemix folder
            local deemix_path="/volume2/downloads/music/Deemix"
            if [ -d "$deemix_path" ]; then
                local dirs=$(cd "$deemix_path" 2>/dev/null && compgen -d -- "$cur")
                COMPREPLY=( $(compgen -W "$dirs" -- "$cur") )
            fi
        fi
    fi

    return 0
}

# Register completion function
complete -o filenames -o nospace -F _salmon_complete salmon
