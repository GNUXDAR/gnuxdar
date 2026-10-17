"""Actualiza las secciones de videos largos y shorts del README con lo último del canal."""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

CHANNEL_ID = "UCJYo8D21cZxPR9vC4IUXanA"
README = "README.md"
API_KEY = os.environ.get("YOUTUBE_API_KEY")

# YouTube expone una playlist automática por tipo: UULF = videos largos, UUSH = shorts
SECTIONS = [
    ("YOUTUBE-VIDEOS", "UULF" + CHANNEL_ID[2:], 8, "https://www.youtube.com/watch?v="),
    ("YOUTUBE-SHORTS", "UUSH" + CHANNEL_ID[2:], 4, "https://www.youtube.com/shorts/"),
]


def latest_videos(playlist_id, count):
    query = urllib.parse.urlencode({
        "part": "snippet",
        "playlistId": playlist_id,
        "maxResults": count,
        "key": API_KEY,
    })
    url = f"https://www.googleapis.com/youtube/v3/playlistItems?{query}"
    with urllib.request.urlopen(url, timeout=30) as response:
        items = json.load(response).get("items", [])
    return [
        (item["snippet"]["resourceId"]["videoId"], item["snippet"]["title"])
        for item in items
    ]


def render(videos, base_url):
    cards = "\n".join(
        f"  <a href='{base_url}{video_id}' target='_blank'>\n"
        f"    <img width='23%' src='https://img.youtube.com/vi/{video_id}/mqdefault.jpg' alt='{html.escape(title, quote=True)}' />\n"
        f"  </a>"
        for video_id, title in videos
    )
    return f'<p align="center">\n{cards}\n</p>'


def main():
    if not API_KEY:
        print("Falta el secret YOUTUBE_API_KEY, no se actualiza nada", file=sys.stderr)
        return

    with open(README, encoding="utf-8") as f:
        content = f.read()

    for marker, playlist_id, count, base_url in SECTIONS:
        videos = latest_videos(playlist_id, count)
        if not videos:
            # Si la API no devuelve nada, mejor dejar la sección como está que vaciarla
            print(f"{marker}: sin videos, se deja igual", file=sys.stderr)
            continue
        pattern = re.compile(f"(<!-- {marker}:START -->).*?(<!-- {marker}:END -->)", re.S)
        if not pattern.search(content):
            sys.exit(f"No se encontraron los marcadores {marker} en {README}")
        content = pattern.sub(
            lambda m: f"{m.group(1)}\n{render(videos, base_url)}\n{m.group(2)}", content
        )

    with open(README, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()
