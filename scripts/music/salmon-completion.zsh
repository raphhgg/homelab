#compdef salmon salmon-upload.sh

# Zsh completion for salmon upload script
# Always completes album directories from /volume2/downloads/music/tmp

_salmon() {
    local tmp_path="/volume2/downloads/music/tmp"

    if [[ -d "$tmp_path" ]]; then
        _files -W "$tmp_path" -/ -F '(@*|.*)'
    fi
}

# Register for both the alias name and the actual script
compdef _salmon salmon
compdef _salmon salmon-upload.sh

# Also set completion for the alias explicitly
setopt complete_aliases
