"""Actualiza el README con los últimos videos y notifica en Discord los que aún no estén registrados."""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

CHANNEL_ID = "UCJYo8D21cZxPR9vC4IUXanA"
README = "README.md"
STATE_FILE = "youtube_state.json"
API_KEY = os.environ.get("YOUTUBE_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# YouTube expone playlists automáticas: UULF = videos largos, UUSH = shorts.
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
        with open(STATE_FILE, encoding="utf-8") as state_file:
            state = json.load(state_file)
        if not isinstance(state, dict):
            raise ValueError(f"{STATE_FILE} must contain a JSON object")
        return state
    except FileNotFoundError:
        return {}


def send_discord_message(kind, title, video_url):
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("Falta el secreto DISCORD_WEBHOOK_URL o está vacío")

    payload = json.dumps({
        "content": f"{kind} Nuevo video: {title}\n{video_url}",
        "username": "GNUXDAR • YouTube",
        "avatar_url": "https://raw.githubusercontent.com/GNUXDAR/gnuxdar/main/assets/discord-bot-avatar.png",
        "allowed_mentions": {"parse": []},
    }).encode("utf-8")
    request = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        # Cloudflare (Discord) rechaza el User-Agent por defecto "Python-urllib" con HTTP 403 (error 1010).
        headers={
            "Content-Type": "application/json",
            "User-Agent": "gnuxdar-youtube-bot (https://github.com/GNUXDAR/gnuxdar, 1.0)",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in (200, 204):
                raise RuntimeError(f"Discord respondió HTTP {response.status}")
    except urllib.error.HTTPError as error:
        # Nunca imprimir la URL: contiene el token privado del webhook.
        raise RuntimeError(f"Discord rechazó el webhook (HTTP {error.code})") from None
    except urllib.error.URLError as error:
        raise RuntimeError(f"No se pudo conectar con Discord: {error.reason}") from None


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
        sys.exit("Falta el secreto YOUTUBE_API_KEY; no se actualiza nada")
    if not DISCORD_WEBHOOK_URL:
        sys.exit("Falta el secreto DISCORD_WEBHOOK_URL; no se actualiza nada")

    state = read_state()
    with open(README, encoding="utf-8") as readme_file:
        content = readme_file.read()

    for marker, playlist_id, count, base_url, kind in SECTIONS:
        videos = latest_videos(playlist_id, count)
        if not videos:
            print(f"{marker}: YouTube no devolvió videos; se conserva el estado actual", file=sys.stderr)
            continue

        previous_ids = set(state.get(marker, []))
        new_videos = [(video_id, title) for video_id, title in videos if video_id not in previous_ids]

        # Avisar primero; solo se guarda el ID si Discord aceptó el mensaje.
        notified_ids = set()
        for video_id, title in reversed(new_videos):
            video_url = f"{base_url}{video_id}"
            send_discord_message(kind, title, video_url)
            print(f"Notificación enviada a Discord: {title} ({video_url})")
            notified_ids.add(video_id)

        state[marker] = [
            video_id for video_id, _ in videos
            if video_id in previous_ids or video_id in notified_ids
        ]

        pattern = re.compile(f"(<!-- {marker}:START -->).*?(<!-- {marker}:END -->)", re.S)
        if not pattern.search(content):
            sys.exit(f"No se encontraron los marcadores {marker} en {README}")
        content = pattern.sub(
            lambda match: f"{match.group(1)}\n{render(videos, base_url)}\n{match.group(2)}", content
        )

    with open(STATE_FILE, "w", encoding="utf-8") as state_file:
        json.dump(state, state_file, ensure_ascii=False, indent=2)
        state_file.write("\n")
    with open(README, "w", encoding="utf-8") as readme_file:
        readme_file.write(content)


if __name__ == "__main__":
    main()
