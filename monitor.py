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
    github_token = os.environ.get("GITHUB_TOKEN")
    github_repository = os.environ.get("GITHUB_REPOSITORY")

    if not github_token:
        raise Exception("GITHUB_TOKEN is missing.")

    if not github_repository:
        raise Exception("GITHUB_REPOSITORY is missing.")

    title = post.get("title", "New Spotify Collaborative Playlist")
    reddit_url = post.get("url", "")
    content = post.get("content", "")

    spotify_match = re.search(
        r"https?://open\.spotify\.com/playlist/[^\s<\"']+",
        content
    )

    spotify_url = (
        spotify_match.group(0)
        if spotify_match
        else "Spotify link not found"
    )

    issue_title = f"🎵 Spotify Collab: {title}"

    issue_body = f"""## New Spotify Collaborative Playlist Found

**Reddit Post:**  
{reddit_url}

**Spotify Playlist:**  
{spotify_url}

### Reddit Post Title

{title}

---

This issue was automatically created by the Reddit Spotify Collab Monitor.
"""

    api_url = (
        f"https://api.github.com/repos/"
        f"{github_repository}/issues"
    )

    payload = json.dumps({
        "title": issue_title,
        "body": issue_body
    }).encode("utf-8")

    request = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    print(
        f"GitHub Issue created: "
        f"{result.get('html_url')}"
    )

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
