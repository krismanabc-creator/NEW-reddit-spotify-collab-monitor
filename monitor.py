import os
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SEEN_FILE = "seen_posts.json"

SEARCH_QUERY = (
    'spotify (collab OR collaborative OR collaborator '
    'OR "add a song" OR "add songs" OR "add your song" '
    'OR "everyone add" OR "anyone add" '
    'OR "join the playlist" OR "join as collaborator")'
)


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)


def search_reddit():
    params = urllib.parse.urlencode({
        "q": SEARCH_QUERY,
        "sort": "new",
        "t": "week",
        "limit": 25,
    })

    url = f"https://www.reddit.com/search.rss?{params}"

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SpotifyCollabMonitor/1.0"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()

    root = ET.fromstring(data)

    namespace = {
        "atom": "http://www.w3.org/2005/Atom"
    }

    posts = []

    for entry in root.findall("atom:entry", namespace):
        title = entry.findtext(
            "atom:title", "", namespace
        )

        link_element = entry.find(
            "atom:link", namespace
        )

        link = (
            link_element.attrib.get("href", "")
            if link_element is not None
            else ""
        )

        content = entry.findtext(
            "atom:content", "", namespace
        )

        post_id = entry.findtext(
            "atom:id", "", namespace
        )

        posts.append({
            "id": post_id,
            "title": title,
            "url": link,
            "content": content,
        })

    return posts


def is_qualifying(post):
    title = post.get("title", "")
    content = post.get("content", "")

    text = f"{title} {content}".lower()

    # Must be about Spotify
    spotify = (
        "spotify" in text
        or "open.spotify.com" in text
    )

    if not spotify:
        return False

    # Must contain collaboration language
    collaboration_terms = [
        "collab",
        "collaborative",
        "collaborator",
        "add a song",
        "add songs",
        "add your song",
        "everyone add",
        "anyone add",
        "join the playlist",
        "join as collaborator",
        "feel free to add",
    ]

    collaboration = any(
        term in text
        for term in collaboration_terms
    )

    if not collaboration:
        return False

    # Must contain an actual Spotify playlist
    spotify_playlist = re.search(
        r"https?://open\.spotify\.com/playlist/[^\s<\"']+",
        content
    )

    if not spotify_playlist:
        return False

    return True


def send_email(post):
    """
    Email notification will be added in the next step.
    For now, print the qualifying post.
    """

    print("")
    print("=" * 60)
    print("QUALIFYING SPOTIFY COLLAB POST")
    print("=" * 60)
    print(f"TITLE: {post.get('title')}")
    print(f"REDDIT: {post.get('url')}")

    content = post.get("content", "")

    spotify_match = re.search(
        r"https?://open\.spotify\.com/playlist/[^\s<\"']+",
        content
    )

    if spotify_match:
        print(f"SPOTIFY: {spotify_match.group(0)}")

    print("=" * 60)
    print("")


def main():

    seen = load_seen()

    print(f"SEARCH: {SEARCH_QUERY}")

    try:
        posts = search_reddit()
    except Exception as e:
        print(f"Reddit search failed: {e}")
        return

    print(f"FOUND: {len(posts)} posts")

    new_posts = []

    for post in posts:

        post_id = post.get("id")

        if not post_id:
            continue

        if post_id in seen:
            continue

        if is_qualifying(post):
            new_posts.append(post)

    print(
        f"QUALIFYING NEW POSTS: {len(new_posts)}"
    )

    for post in new_posts:

        try:
            send_email(post)

            # Only mark the post as seen after
            # successfully processing it.
            seen.add(post["id"])

        except Exception as e:
            print(
                f"Notification failed: {e}"
            )

    save_seen(seen)


if __name__ == "__main__":
    main()
