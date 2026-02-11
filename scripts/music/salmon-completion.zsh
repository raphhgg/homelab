#compdef salmon salmon-auto salmon-upload.sh salmon-upload-auto.py

# Zsh completion for salmon upload scripts
# Always completes album directories from /volume2/downloads/music/tmp

_salmon() {
    local tmp_path="/volume2/downloads/music/tmp"

    if [[ -d "$tmp_path" ]]; then
        _files -W "$tmp_path" -/ -F '(@*|.*)'
    fi
}

# Register for alias names and actual scripts
compdef _salmon salmon
compdef _salmon salmon-auto
compdef _salmon salmon-upload.sh
compdef _salmon salmon-upload-auto.py

# Also set completion for the alias explicitly
setopt complete_aliases
