#!/usr/bin/env python3
"""
Generate a formatted list of unmatched assets with TMDb search links.
Reads from daps unmatched_dict.json and outputs a file with movie/show names and TMDb search URLs.
"""

import json
from urllib.parse import quote

def main():
    input_file = '/volume2/docker/appdata/daps/logs/unmatched_assets/debug/unmatched_dict.json'
    output_file = '/volume2/docker/compose/scripts/unmatched_assets_with_tmdb_links.txt'

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

            # Generate TMDb search URL
            search_query = f"{title} {year}" if year else title
            tmdb_url = f"https://www.themoviedb.org/search?query={quote(search_query)}"

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

            # Generate TMDb search URL
            search_query = f"{title} {year}" if year else title
            tmdb_url = f"https://www.themoviedb.org/search?query={quote(search_query)}"

            output_lines.append(f"{display_name}")
            output_lines.append(f"  {tmdb_url}")
            output_lines.append('')

    # Write output file
    with open(output_file, 'w') as f:
        f.write('\n'.join(output_lines))

    print(f"✓ Output written to: {output_file}")
    print(f"  Total movies: {len(data.get('movies', []))}")
    print(f"  Total series: {len(data.get('series', []))}")
    print(f"\nNote: Collections are skipped as they are Plex-specific and don't have direct TMDb equivalents.")

if __name__ == '__main__':
    main()
