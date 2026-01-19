#!/usr/bin/env python3
"""
Generate a formatted list of unmatched assets with TMDb links.
Reads from daps unmatched_dict.json and outputs a file with movie/show names and TMDb URLs.
"""

import json
import sys
import time
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

def search_tmdb(title, year, media_type='movie'):
    """Search TMDb for a title and return the URL."""
    api_key = '1ad7f0397c528cf8c23f068d79e3bc20'  # Public TMDb API key

    # Clean up title for search
    search_title = title.replace(':', '').strip()

    # Build search URL
    url = f'https://api.themoviedb.org/3/search/{media_type}?api_key={api_key}&query={quote(search_title)}'
    if year:
        url += f'&year={year}'

    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

            if data.get('results'):
                result = data['results'][0]
                tmdb_id = result['id']
                return f'https://www.themoviedb.org/{media_type}/{tmdb_id}'
            else:
                # Try without year if no results
                if year:
                    url_no_year = f'https://api.themoviedb.org/3/search/{media_type}?api_key={api_key}&query={quote(search_title)}'
                    req = Request(url_no_year, headers={'User-Agent': 'Mozilla/5.0'})
                    with urlopen(req, timeout=10) as response2:
                        data = json.loads(response2.read().decode())
                        if data.get('results'):
                            result = data['results'][0]
                            tmdb_id = result['id']
                            return f'https://www.themoviedb.org/{media_type}/{tmdb_id}'

                return None
    except (URLError, HTTPError) as e:
        print(f"Error searching for {title}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Unexpected error for {title}: {e}", file=sys.stderr)
        return None

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

        for idx, movie in enumerate(data['movies'], 1):
            title = movie['title']
            year = movie.get('year')

            display_name = f"{title} ({year})" if year else title
            print(f"[{idx}/{len(data['movies'])}] Searching movie: {display_name}")

            tmdb_url = search_tmdb(title, year, 'movie')

            if tmdb_url:
                output_lines.append(f"{display_name}")
                output_lines.append(f"  {tmdb_url}")
            else:
                output_lines.append(f"{display_name}")
                output_lines.append(f"  [No TMDb match found]")

            output_lines.append('')

            # Rate limiting
            time.sleep(0.3)

    # Process TV series
    if data.get('series'):
        output_lines.append('')
        output_lines.append('=' * 80)
        output_lines.append('TV SERIES')
        output_lines.append('=' * 80)
        output_lines.append('')

        for idx, show in enumerate(data['series'], 1):
            title = show['title']
            year = show.get('year')

            display_name = f"{title} ({year})" if year else title
            print(f"[{idx}/{len(data['series'])}] Searching series: {display_name}")

            tmdb_url = search_tmdb(title, year, 'tv')

            if tmdb_url:
                output_lines.append(f"{display_name}")
                output_lines.append(f"  {tmdb_url}")
            else:
                output_lines.append(f"{display_name}")
                output_lines.append(f"  [No TMDb match found]")

            output_lines.append('')

            # Rate limiting
            time.sleep(0.3)

    # Write output file
    with open(output_file, 'w') as f:
        f.write('\n'.join(output_lines))

    print(f"\n✓ Output written to: {output_file}")
    print(f"  Total movies: {len(data.get('movies', []))}")
    print(f"  Total series: {len(data.get('series', []))}")

if __name__ == '__main__':
    main()
