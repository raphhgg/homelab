#!/bin/bash

# Trailers Organizer
# 
# Recursively searches through movie and TV show directories (including subcategories)
# to find and organize trailer files. 
#   - Creates Trailers folder if missing, or reorganizes existing ones. 
#   - Moves loose trailer files from root directories into Trailers folders.
#   - Renames all trailer files to consistent format: "Trailer 1.mkv", "Trailer 2.mkv", etc.
#   - Supports various naming patterns including "Movie - Trailer.mkv", "Trailer.mkv", typos, etc.
# 
# Usage: ./organize_trailers.sh /path/to/media

# Check if path was provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 /path/to/media"
    echo "Example: $0 /Users/username/Movies"
    echo "Example: $0 /Users/username/TV Shows"
    exit 1
fi

media_path="$1"

# Check if the path exists
if [ ! -d "$media_path" ]; then
    echo "Error: Directory '$media_path' does not exist"
    exit 1
fi

echo "Processing all media directories in: $media_path"
echo "=================================================="
echo

# Change to the media directory
cd "$media_path" || exit 1

# Counter for statistics
total_items=0
items_with_trailers=0
total_trailers_processed=0

# Function to check if a directory is a media directory (contains video files or has Trailers folder)
is_media_directory() {
    local dir="$1"
    
    # Check if it has a Trailers folder
    if [ -d "$dir/Trailers" ]; then
        return 0
    fi
    
    # Check if it has video files (common movie/show extensions)
    if find "$dir" -maxdepth 1 \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" -o -name "*.mov" -o -name "*.m4v" \) -type f | head -1 | grep -q .; then
        return 0
    fi
    
    return 1
}

# Function to process a single media directory
process_media_directory() {
    local item_dir="$1"
    
    total_items=$((total_items + 1))
    
    echo "Processing: $item_dir"
    
    # Step 1: Find trailer files in root directory
    root_trailer_files=$(find "$item_dir" -maxdepth 1 \( -name "*[Tt]railer*.mkv" -o -name "*[Tt]raier*.mkv" -o -name "*-[Tt]railer.mkv" -o -name "*-[Tt]raier.mkv" \) -type f)
    
    # Step 2: Check if Trailers folder exists and find files there
    existing_trailer_files=""
    if [ -d "$item_dir/Trailers" ]; then
        existing_trailer_files=$(find "$item_dir/Trailers" -maxdepth 1 -name "*.mkv" -type f)
    fi
    
    # Step 3: Decide what to do based on what we found
    if [ -z "$root_trailer_files" ] && [ -z "$existing_trailer_files" ]; then
        echo "  No trailer files found - skipping"
        echo
        return
    fi
    
    items_with_trailers=$((items_with_trailers + 1))
    
    # Step 4: Create Trailers folder if it doesn't exist
    mkdir -p "$item_dir/Trailers"
    echo "  Created/verified Trailers directory"
    
    # Step 5: Create temporary directory for safe renaming
    temp_dir="$item_dir/temp_trailers_$"
    mkdir -p "$temp_dir"
    
    # Step 6: Move/collect all trailer files to temp directory with proper naming
    counter=1
    
    # First, handle files from root directory (move them)
    if [ -n "$root_trailer_files" ]; then
        echo "  Moving trailer files from root directory:"
        while IFS= read -r -d '' file; do
            if [ -f "$file" ]; then
                new_name="Trailer ${counter}.mkv"
                mv "$file" "$temp_dir/$new_name"
                echo "    Moved: $(basename "$file") -> $new_name"
                counter=$((counter + 1))
                total_trailers_processed=$((total_trailers_processed + 1))
            fi
        done < <(find "$item_dir" -maxdepth 1 \( -name "*[Tt]railer*.mkv" -o -name "*[Tt]raier*.mkv" -o -name "*-[Tt]railer.mkv" -o -name "*-[Tt]raier.mkv" \) -type f -print0)
    fi
    
    # Then, handle files from existing Trailers folder (rename them)
    if [ -n "$existing_trailer_files" ]; then
        echo "  Renaming trailer files from Trailers directory:"
        while IFS= read -r -d '' file; do
            if [ -f "$file" ]; then
                new_name="Trailer ${counter}.mkv"
                mv "$file" "$temp_dir/$new_name"
                echo "    Renamed: $(basename "$file") -> $new_name"
                counter=$((counter + 1))
                total_trailers_processed=$((total_trailers_processed + 1))
            fi
        done < <(find "$item_dir/Trailers" -maxdepth 1 -name "*.mkv" -type f -print0)
    fi
    
    # Step 7: Move all properly named files back to Trailers folder
    if [ "$(ls -A "$temp_dir" 2>/dev/null)" ]; then
        mv "$temp_dir"/* "$item_dir/Trailers/"
        echo "  All trailers organized with consistent naming"
    fi
    
    # Step 8: Clean up temp directory
    rmdir "$temp_dir"
    
    echo "  Completed: $item_dir"
    echo
}

# Recursive function to find and process media directories
find_and_process_media() {
    local current_path="$1"
    local depth="$2"
    local max_depth=5  # Prevent infinite recursion
    
    if [ "$depth" -gt "$max_depth" ]; then
        return
    fi
    
    # Loop through all subdirectories in current path
    for item_dir in "$current_path"/*/; do
        if [ -d "$item_dir" ]; then
            # Remove trailing slash for cleaner output
            item_dir="${item_dir%/}"
            
            # Check if this is a media directory (has video files or Trailers folder)
            if is_media_directory "$item_dir"; then
                # This is a media directory, process it
                process_media_directory "$item_dir"
            else
                # This might be a category folder, recurse into it
                echo "Exploring category: $(basename "$item_dir")"
                find_and_process_media "$item_dir" $((depth + 1))
            fi
        fi
    done
}

# Start the recursive search and processing
find_and_process_media "$media_path" 0

# Function to check if a directory is a media directory (contains video files or has Trailers folder)
is_media_directory() {
    local dir="$1"
    
    # Check if it has a Trailers folder
    if [ -d "$dir/Trailers" ]; then
        return 0
    fi
    
    # Check if it has video files (common movie/show extensions)
    if find "$dir" -maxdepth 1 \( -name "*.mkv" -o -name "*.mp4" -o -name "*.avi" -o -name "*.mov" -o -name "*.m4v" \) -type f | head -1 | grep -q .; then
        return 0
    fi
    
    return 1
}

# Function to process a single media directory
process_media_directory() {
    local item_dir="$1"
    
    total_items=$((total_items + 1))
    
    echo "Processing: $item_dir"
    
    # Step 1: Find trailer files in root directory
    root_trailer_files=$(find "$item_dir" -maxdepth 1 \( -name "*[Tt]railer*.mkv" -o -name "*[Tt]raier*.mkv" -o -name "*-[Tt]railer.mkv" -o -name "*-[Tt]raier.mkv" \) -type f)
    
    # Step 2: Check if Trailers folder exists and find files there
    existing_trailer_files=""
    if [ -d "$item_dir/Trailers" ]; then
        existing_trailer_files=$(find "$item_dir/Trailers" -maxdepth 1 -name "*.mkv" -type f)
    fi
    
    # Step 3: Decide what to do based on what we found
    if [ -z "$root_trailer_files" ] && [ -z "$existing_trailer_files" ]; then
        echo "  No trailer files found - skipping"
        echo
        return
    fi
    
    items_with_trailers=$((items_with_trailers + 1))
    
    # Step 4: Create Trailers folder if it doesn't exist
    mkdir -p "$item_dir/Trailers"
    echo "  Created/verified Trailers directory"
    
    # Step 5: Create temporary directory for safe renaming
    temp_dir="$item_dir/temp_trailers_$"
    mkdir -p "$temp_dir"
    
    # Step 6: Move/collect all trailer files to temp directory with proper naming
    counter=1
    
    # First, handle files from root directory (move them)
    if [ -n "$root_trailer_files" ]; then
        echo "  Moving trailer files from root directory:"
        while IFS= read -r -d '' file; do
            if [ -f "$file" ]; then
                new_name="Trailer ${counter}.mkv"
                mv "$file" "$temp_dir/$new_name"
                echo "    Moved: $(basename "$file") -> $new_name"
                counter=$((counter + 1))
                total_trailers_processed=$((total_trailers_processed + 1))
            fi
        done < <(find "$item_dir" -maxdepth 1 \( -name "*[Tt]railer*.mkv" -o -name "*[Tt]raier*.mkv" -o -name "*-[Tt]railer.mkv" -o -name "*-[Tt]raier.mkv" \) -type f -print0)
    fi
    
    # Then, handle files from existing Trailers folder (rename them)
    if [ -n "$existing_trailer_files" ]; then
        echo "  Renaming trailer files from Trailers directory:"
        while IFS= read -r -d '' file; do
            if [ -f "$file" ]; then
                new_name="Trailer ${counter}.mkv"
                mv "$file" "$temp_dir/$new_name"
                echo "    Renamed: $(basename "$file") -> $new_name"
                counter=$((counter + 1))
                total_trailers_processed=$((total_trailers_processed + 1))
            fi
        done < <(find "$item_dir/Trailers" -maxdepth 1 -name "*.mkv" -type f -print0)
    fi
    
    # Step 7: Move all properly named files back to Trailers folder
    if [ "$(ls -A "$temp_dir" 2>/dev/null)" ]; then
        mv "$temp_dir"/* "$item_dir/Trailers/"
        echo "  All trailers organized with consistent naming"
    fi
    
    # Step 8: Clean up temp directory
    rmdir "$temp_dir"
    
    echo "  Completed: $item_dir"
    echo
}

# Recursive function to find and process media directories
find_and_process_media() {
    local current_path="$1"
    local depth="$2"
    local max_depth=5  # Prevent infinite recursion
    
    if [ "$depth" -gt "$max_depth" ]; then
        return
    fi
    
    # Loop through all subdirectories in current path
    for item_dir in "$current_path"/*/; do
        if [ -d "$item_dir" ]; then
            # Remove trailing slash for cleaner output
            item_dir="${item_dir%/}"
            
            # Check if this is a media directory (has video files or Trailers folder)
            if is_media_directory "$item_dir"; then
                # This is a media directory, process it
                process_media_directory "$item_dir"
            else
                # This might be a category folder, recurse into it
                echo "Exploring category: $(basename "$item_dir")"
                find_and_process_media "$item_dir" $((depth + 1))
            fi
        fi
    done
}

echo "=================================================="
echo "SUMMARY:"
echo "Total items processed: $total_items"
echo "Items with trailers: $items_with_trailers"
echo "Total trailers processed: $total_trailers_processed"
echo "Done organizing all trailers!"