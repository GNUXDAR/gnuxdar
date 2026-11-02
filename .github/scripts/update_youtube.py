"""Actualiza las secciones de videos largos y shorts del README con lo último del canal y notifica en Discord si hay novedades."""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

CHANNEL_ID = "UCJYo8D21cZxPR9vC4IUXanA"
README = "README.md"
STATE_FILE = "youtube_state.json"
API_KEY = os.environ.get("YOUTUBE_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# YouTube expone una playlist automática por tipo: UULF = videos largos, UUSH = shorts
SECTIONS = [
    ("YOUTUBE-VIDEOS", "UULF" + CHANNEL_ID[2:], 8, "https://www.youtube.com/watch?v=", "🎬"),
    ("YOUTUBE-SHORTS", "UUSH" + CHANNEL_ID[2:], 4, "https://www.youtube.com/shorts/", "🎥"),
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

def read_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        pass
    return {}

def write_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")

def send_discord_message(kind, title, video_url):
    if not DISCORD_WEBHOOK_URL:
        return

    payload = json.dumps({
        "content": f"{kind} Nuevo video: {title}\n{video_url}",
        "username": "YouTube Bot",
    }).encode("utf-8")

    request = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in (200, 204):
                print(f"Discord respondió con estado {response.status}", file=sys.stderr)
    except Exception as exc:
        print(f"No se pudo enviar el mensaje a Discord: {exc}", file=sys.stderr)

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

    state = read_state()

    with open(README, encoding="utf-8") as f:
        content = f.read()

    for marker, playlist_id, count, base_url, kind in SECTIONS:
        videos = latest_videos(playlist_id, count)
        if not videos:
            print(f"{marker}: sin videos, se deja igual", file=sys.stderr)
            continue

        previous_ids = set(state.get(marker, []))
        new_videos = [(video_id, title) for video_id, title in videos if video_id not in previous_ids]

        if new_videos:
            for video_id, title in new_videos:
                send_discord_message(kind, title, f"{base_url}{video_id}")

        state[marker] = [video_id for video_id, _ in videos]

        pattern = re.compile(f"(<!-- {marker}:START -->).*?(<!-- {marker}:END -->)", re.S)
        if not pattern.search(content):
            sys.exit(f"No se encontraron los marcadores {marker} en {README}")
        content = pattern.sub(
            lambda m: f"{m.group(1)}\n{render(videos, base_url)}\n{m.group(2)}", content
        )

    write_state(state)

    with open(README, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    main()
