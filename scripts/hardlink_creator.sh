#!/bin/bash

# Simple Hardlink Creator for Duplicates Between Two Folders
# Usage: ./hardlink_creator.sh /path/to/original /path/to/copy
# 
# This script will:
# 1. Find duplicate files between two folders
# 2. Keep files in the ORIGINAL folder
# 3. Replace files in the COPY folder with hardlinks to the original

if [ $# -ne 2 ]; then
    echo "Usage: $0 <original_folder> <copy_folder>"
    echo "Example: $0 /volume1/data/medias/tvshows /volume1/data/medias/downloads/torrents/complete/tvshows"
    echo
    echo "Files in <original_folder> will be KEPT"
    echo "Files in <copy_folder> will be REPLACED with hardlinks"
    exit 1
fi

ORIGINAL_FOLDER="$1"
COPY_FOLDER="$2"
WORK_DIR="/tmp/jdupes_work_$$"
HASH_DB="$WORK_DIR/duplicates.txt"

# Validate input folders
if [ ! -d "$ORIGINAL_FOLDER" ]; then
    echo "ERROR: Original folder '$ORIGINAL_FOLDER' does not exist!"
    exit 1
fi

if [ ! -d "$COPY_FOLDER" ]; then
    echo "ERROR: Copy folder '$COPY_FOLDER' does not exist!"
    exit 1
fi

# Create working directory
mkdir -p "$WORK_DIR"
cd "$WORK_DIR" || exit 1

echo "=== DUPLICATE FINDER ==="
echo "Original folder (files will be KEPT): $ORIGINAL_FOLDER"
echo "Copy folder (files will be REPLACED): $COPY_FOLDER"
echo "Working directory: $WORK_DIR"
echo

# Function to extract episode/season info from filename
extract_episode_info() {
    local filename="$1"
    # Extract SxxExx pattern or similar episode identifiers (case insensitive)
    echo "$filename" | grep -oiE 's[0-9]+e[0-9]+' | head -1 | tr '[:upper:]' '[:lower:]'
}

# Function to check if files should be matched based on episode info
should_match_episodes() {
    local file1="$1"
    local file2="$2"
    
    # Extract episode info
    local ep1=$(extract_episode_info "$file1")
    local ep2=$(extract_episode_info "$file2")
    
    # If both have episode info, they must match
    if [ -n "$ep1" ] && [ -n "$ep2" ]; then
        if [ "$ep1" = "$ep2" ]; then
            echo "MATCH"
        else
            echo "DIFFERENT_EPISODES"
        fi
    else
        # If we can't extract episode info from one or both, be cautious
        echo "UNKNOWN"
    fi
}

# Step 1: Check initial sizes
echo "=== INITIAL FOLDER SIZES ==="
echo "Original folder:"
du -sh "$ORIGINAL_FOLDER"
echo "Copy folder:"
du -sh "$COPY_FOLDER"
echo

# Step 2: Scan for duplicates and create hash database
echo "=== SCANNING FOR DUPLICATES ==="
echo "Scanning for duplicates (files >100MB)..."
echo "This uses cryptographic hashes to find files with identical content."
echo
echo "Command: jdupes -rS -X size+:100m \"$ORIGINAL_FOLDER\" \"$COPY_FOLDER\" > duplicates_raw.txt"
echo

# Note: Removed -A and -y flags, using simpler approach
jdupes -rS -X size+:100m "$ORIGINAL_FOLDER" "$COPY_FOLDER" > duplicates_raw.txt

echo "=== SCAN COMPLETE ==="
echo

# Check if duplicates were found
if [ ! -f "duplicates_raw.txt" ] || [ ! -s "duplicates_raw.txt" ]; then
    echo "No duplicates found between the two folders."
    rm -rf "$WORK_DIR"
    exit 0
fi

# Parse the jdupes output to identify which files are from which folder
echo "=== PARSING DUPLICATE RESULTS ==="
echo "Analyzing which files belong to which folder..."
echo

# Process jdupes output (it groups duplicates together, separated by blank lines)
match_count=0
safe_count=0
suspicious_count=0
different_folder_count=0

> "$HASH_DB"  # Clear the hash database

# Read the jdupes output and process groups of duplicates
{
    group_files=()
    while IFS= read -r line; do
        if [ -z "$line" ]; then
            # Empty line indicates end of a group
            if [ ${#group_files[@]} -ge 2 ]; then
                # Process this group
                original_files=()
                copy_files=()
                
                # Separate files by folder
                for file in "${group_files[@]}"; do
                    if [[ "$file" == "$ORIGINAL_FOLDER"* ]]; then
                        original_files+=("$file")
                    elif [[ "$file" == "$COPY_FOLDER"* ]]; then
                        copy_files+=("$file")
                    fi
                done
                
                # Only process if we have files from both folders
                if [ ${#original_files[@]} -gt 0 ] && [ ${#copy_files[@]} -gt 0 ]; then
                    # Match each copy file with the first original file
                    original_file="${original_files[0]}"
                    
                    for copy_file in "${copy_files[@]}"; do
                        match_count=$((match_count + 1))
                        different_folder_count=$((different_folder_count + 1))
                        
                        # Check episode matching
                        episode_check=$(should_match_episodes "$original_file" "$copy_file")
                        
                        if [ "$episode_check" = "DIFFERENT_EPISODES" ]; then
                            suspicious_count=$((suspicious_count + 1))
                            echo "SUSPICIOUS,$match_count,$original_file,$copy_file" >> "$HASH_DB"
                        else
                            safe_count=$((safe_count + 1))
                            echo "SAFE,$match_count,$original_file,$copy_file" >> "$HASH_DB"
                        fi
                    done
                fi
            fi
            group_files=()
        else
            # Add file to current group
            group_files+=("$line")
        fi
    done
    
    # Process the last group if it exists
    if [ ${#group_files[@]} -ge 2 ]; then
        original_files=()
        copy_files=()
        
        for file in "${group_files[@]}"; do
            if [[ "$file" == "$ORIGINAL_FOLDER"* ]]; then
                original_files+=("$file")
            elif [[ "$file" == "$COPY_FOLDER"* ]]; then
                copy_files+=("$file")
            fi
        done
        
        if [ ${#original_files[@]} -gt 0 ] && [ ${#copy_files[@]} -gt 0 ]; then
            original_file="${original_files[0]}"
            
            for copy_file in "${copy_files[@]}"; do
                match_count=$((match_count + 1))
                different_folder_count=$((different_folder_count + 1))
                
                episode_check=$(should_match_episodes "$original_file" "$copy_file")
                
                if [ "$episode_check" = "DIFFERENT_EPISODES" ]; then
                    suspicious_count=$((suspicious_count + 1))
                    echo "SUSPICIOUS,$match_count,$original_file,$copy_file" >> "$HASH_DB"
                else
                    safe_count=$((safe_count + 1))
                    echo "SAFE,$match_count,$original_file,$copy_file" >> "$HASH_DB"
                fi
            done
        fi
    fi
} < duplicates_raw.txt

# Display found duplicates
echo "=== DUPLICATES FOUND ==="
echo "The following duplicate files were found between the two folders:"
echo "================================================================"

if [ ! -s "$HASH_DB" ]; then
    echo "No cross-folder duplicates found."
    echo "(Note: Files may be duplicated within the same folder, but this script"
    echo "only processes duplicates between different folders)"
    rm -rf "$WORK_DIR"
    exit 0
fi

while IFS=',' read -r status match_num original_file copy_file; do
    orig_basename=$(basename "$original_file")
    copy_basename=$(basename "$copy_file")
    
    # Get file size
    file_size=$(stat -c %s "$original_file" 2>/dev/null | numfmt --to=iec 2>/dev/null || echo "unknown")
    
    echo
    if [ "$status" = "SUSPICIOUS" ]; then
        echo "⚠️  SUSPICIOUS Match #$match_num (Size: $file_size):"
        ep1=$(extract_episode_info "$orig_basename")
        ep2=$(extract_episode_info "$copy_basename")
        echo "  📺 Episodes: '$ep1' vs '$ep2' (DIFFERENT!)"
    else
        echo "✓ Safe Match #$match_num (Size: $file_size):"
    fi
    
    echo "  KEEP:    $orig_basename"
    echo "  REPLACE: $copy_basename"
    echo "  Paths:"
    echo "    KEEP:    ${original_file#$ORIGINAL_FOLDER}"
    echo "    REPLACE: ${copy_file#$COPY_FOLDER}"
    
done < "$HASH_DB"

echo
echo "=== SUMMARY ==="
echo "Cross-folder duplicate pairs found: $different_folder_count"
echo "Safe matches (same/similar episodes): $safe_count"
echo "Suspicious matches (different episodes): $suspicious_count"

if [ $different_folder_count -eq 0 ]; then
    echo "No cross-folder duplicates to process."
    rm -rf "$WORK_DIR"
    exit 0
fi

if [ $suspicious_count -gt 0 ]; then
    echo
    echo "⚠️  WARNING: $suspicious_count suspicious matches found!"
    echo "These appear to be different episodes with identical file content."
    echo "This could indicate:"
    echo "  - Corrupted or mislabeled files"
    echo "  - Duplicate content wrongly named"
    echo "  - Files that need manual review"
    echo
    echo "RECOMMENDATION: Review these files manually before proceeding."
fi

# Step 3: Ask for confirmation and create hardlinks
echo
echo "=== HARDLINK CREATION ==="
echo "This will:"
echo "  - KEEP files in: $ORIGINAL_FOLDER"
echo "  - REPLACE files in: $COPY_FOLDER with hardlinks"

if [ $suspicious_count -gt 0 ]; then
    echo
    echo "⚠️  There are $suspicious_count suspicious matches!"
    echo "Options:"
    echo "  1) Process only safe matches ($safe_count files)"
    echo "  2) Process ALL matches (including suspicious ones)"
    echo "  3) Cancel and exit"
    echo
    echo "Enter your choice (1/2/3):"
    read -r choice
    
    case $choice in
        1)
            echo "Will process only safe matches."
            PROCESS_SUSPICIOUS=false
            ;;
        2)
            echo "Will process ALL matches including suspicious ones."
            PROCESS_SUSPICIOUS=true
            ;;
        3|*)
            echo "Operation cancelled."
            rm -rf "$WORK_DIR"
            exit 0
            ;;
    esac
else
    echo
    echo "Do you want to create hardlinks for these $different_folder_count pairs? (y/n)"
    read -r response
    
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Operation cancelled."
        rm -rf "$WORK_DIR"
        exit 0
    fi
    PROCESS_SUSPICIOUS=true
fi

echo
echo "Creating hardlinks..."

# Process each match
processed_count=0
skipped_count=0

while IFS=',' read -r status match_num original_file copy_file; do
    # Skip suspicious matches if requested
    if [ "$PROCESS_SUSPICIOUS" = "false" ] && [ "$status" = "SUSPICIOUS" ]; then
        echo "Skipping suspicious match: $(basename "$original_file") <-> $(basename "$copy_file")"
        skipped_count=$((skipped_count + 1))
        continue
    fi
    
    echo "Processing: $(basename "$copy_file") -> $(basename "$original_file")"
    
    # Create hardlink (remove copy file and link to original)
    if [ -f "$copy_file" ] && [ -f "$original_file" ]; then
        if rm "$copy_file" && ln "$original_file" "$copy_file"; then
            echo "  ✓ Hardlink created successfully"
            processed_count=$((processed_count + 1))
        else
            echo "  ✗ Failed to create hardlink"
        fi
    else
        echo "  ✗ One or both files not found"
    fi
    
done < "$HASH_DB"

echo
echo "=== HARDLINKS CREATED ==="
echo "Successfully processed: $processed_count files"
if [ $skipped_count -gt 0 ]; then
    echo "Skipped suspicious matches: $skipped_count files"
fi

# Step 4: Verify hardlinks were created successfully
echo
echo "=== VERIFYING HARDLINKS ==="
echo "Checking that hardlinks were created successfully..."

verified_count=0

while IFS=',' read -r status match_num original_file copy_file; do
    # Skip if this was skipped during processing
    if [ "$PROCESS_SUSPICIOUS" = "false" ] && [ "$status" = "SUSPICIOUS" ]; then
        continue
    fi
    
    echo "Checking: $(basename "$copy_file")"
    
    # Get inodes
    if [ -f "$original_file" ] && [ -f "$copy_file" ]; then
        orig_inode=$(stat -c %i "$original_file" 2>/dev/null)
        copy_inode=$(stat -c %i "$copy_file" 2>/dev/null)
        link_count=$(stat -c %h "$original_file" 2>/dev/null)
        
        if [ "$orig_inode" = "$copy_inode" ]; then
            echo "  ✓ HARDLINKED (inode: $orig_inode, links: $link_count)"
            verified_count=$((verified_count + 1))
        else
            echo "  ✗ NOT HARDLINKED (orig: $orig_inode, copy: $copy_inode)"
        fi
    else
        echo "  ✗ FILE MISSING"
    fi
    
done < "$HASH_DB"

echo
echo "=== VERIFICATION COMPLETE ==="
echo "Successfully verified: $verified_count hardlinks"

# Step 5: Show final sizes
echo
echo "=== FINAL FOLDER SIZES ==="
echo "Original folder:"
du -sh "$ORIGINAL_FOLDER"
echo "Copy folder:"
du -sh "$COPY_FOLDER"
echo
echo "NOTE: Copy folder size may appear unchanged because 'du' counts"
echo "hardlinks separately. The real space savings are visible in the"
echo "filesystem usage and overall directory totals."

# Cleanup
echo
echo "Cleaning up working directory..."
rm -rf "$WORK_DIR"
echo "Done!"
