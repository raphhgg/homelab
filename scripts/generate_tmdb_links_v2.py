#!/usr/bin/env python3
"""
Generate a formatted list of unmatched assets with direct TMDb links.
Uses Radarr/Sonarr APIs to get TMDb IDs for accurate links.
"""

import json
import subprocess

def get_radarr_lookup():
    """Get movie lookup from Radarr via docker exec"""
    cmd = '''docker exec daps-ui curl -s "http://radarr:7878/api/v3/movie?apikey=65aa12a2c361442299ccd95c5db036c0"'''
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error getting Radarr data: {result.stderr}")
        return {}

    movies = json.loads(result.stdout)
    lookup = {}
    for m in movies:
        # Store by exact title|year
        key = f"{m.get('title', '')}|{m.get('year')}"
        lookup[key] = m.get('tmdbId')
        # Also store by lowercase for fuzzy matching
        key_lower = f"{m.get('title', '').lower()}|{m.get('year')}"
        lookup[key_lower] = m.get('tmdbId')
    return lookup

def get_sonarr_lookup():
    """Get series lookup from Sonarr via docker exec"""
    cmd = '''docker exec daps-ui curl -s "http://sonarr:8989/api/v3/series?apikey=e3d546a29d164cfb9c77e95adf2a2c35"'''
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error getting Sonarr data: {result.stderr}")
        return {}

    series = json.loads(result.stdout)
    lookup = {}
    for s in series:
        key = f"{s.get('title', '')}|{s.get('year')}"
        lookup[key] = s.get('tmdbId')
        key_lower = f"{s.get('title', '').lower()}|{s.get('year')}"
        lookup[key_lower] = s.get('tmdbId')
    return lookup

def main():
    input_file = '/volume2/docker/appdata/daps/logs/unmatched_assets/debug/unmatched_dict.json'
    output_file = '/volume2/docker/compose/scripts/unmatched_assets_with_tmdb_links.txt'

    print("Loading Radarr library...")
    radarr_lookup = get_radarr_lookup()
    print(f"  Found {len(radarr_lookup)//2} movies")

    print("Loading Sonarr library...")
    sonarr_lookup = get_sonarr_lookup()
    print(f"  Found {len(sonarr_lookup)//2} series")

    # Read input JSON
    with open(input_file, 'r') as f:
        data = json.load(f)

    output_lines = []

    # Process movies
    if data.get('movies'):
        output_lines.append('=' * 80)
        output_lines.append('MOVIES')
        output_lines.append('=' * 80)
        output_lines.append('')

        for movie in data['movies']:
            title = movie['title']
            year = movie.get('year')

            display_name = f"{title} ({year})" if year else title

            # Look up TMDb ID
            key = f"{title}|{year}"
            key_lower = f"{title.lower()}|{year}"
            tmdb_id = radarr_lookup.get(key) or radarr_lookup.get(key_lower)

            if tmdb_id:
                tmdb_url = f"https://www.themoviedb.org/movie/{tmdb_id}"
            else:
                tmdb_url = "[Not found in Radarr]"

            output_lines.append(f"{display_name}")
            output_lines.append(f"  {tmdb_url}")
            output_lines.append('')

    # Process TV series
    if data.get('series'):
        output_lines.append('')
        output_lines.append('=' * 80)
        output_lines.append('TV SERIES')
        output_lines.append('=' * 80)
        output_lines.append('')

        for show in data['series']:
            title = show['title']
            year = show.get('year')

            display_name = f"{title} ({year})" if year else title

            # Look up TMDb ID
            key = f"{title}|{year}"
            key_lower = f"{title.lower()}|{year}"
            tmdb_id = sonarr_lookup.get(key) or sonarr_lookup.get(key_lower)

            if tmdb_id:
                tmdb_url = f"https://www.themoviedb.org/tv/{tmdb_id}"
            else:
                tmdb_url = "[Not found in Sonarr]"

            output_lines.append(f"{display_name}")
            output_lines.append(f"  {tmdb_url}")
            output_lines.append('')

    # Write output file
    with open(output_file, 'w') as f:
        f.write('\n'.join(output_lines))

    print(f"\n✓ Output written to: {output_file}")
    print(f"  Total movies: {len(data.get('movies', []))}")
    print(f"  Total series: {len(data.get('series', []))}")

if __name__ == '__main__':
    main()
