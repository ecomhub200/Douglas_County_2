#!/usr/bin/env python3
"""
CRASH LENS Social Media Posting Script
========================================
Posts approved content to social media platforms via their APIs.
Supports direct API posting and integration with Postiz (self-hosted).

Usage:
    python post_to_platforms.py posts_file.json                     # Post all approved
    python post_to_platforms.py posts_file.json --platform linkedin  # Specific platform
    python post_to_platforms.py posts_file.json --schedule           # Schedule (don't post now)
    python post_to_platforms.py posts_file.json --via postiz         # Post via Postiz API

Environment Variables:
    # Direct API posting
    LINKEDIN_ACCESS_TOKEN    - LinkedIn OAuth2 access token
    TWITTER_API_KEY          - Twitter/X API key
    TWITTER_API_SECRET       - Twitter/X API secret
    TWITTER_ACCESS_TOKEN     - Twitter/X access token
    TWITTER_ACCESS_SECRET    - Twitter/X access token secret
    FACEBOOK_PAGE_TOKEN      - Facebook Page access token
    BLUESKY_HANDLE           - Bluesky handle
    BLUESKY_APP_PASSWORD     - Bluesky app password

    # Postiz (self-hosted)
    POSTIZ_API_URL           - Postiz instance URL (e.g., http://localhost:4200)
    POSTIZ_API_KEY           - Postiz API key

    # Buffer
    BUFFER_ACCESS_TOKEN      - Buffer OAuth2 access token
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Optional imports for direct API posting
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ---------------------------------------------------------------------------
# Platform posting functions
# ---------------------------------------------------------------------------

class PlatformPoster:
    """Base class for platform-specific posting."""

    def __init__(self, platform_name):
        self.platform = platform_name
        self.posted = []
        self.errors = []

    def post(self, post_data):
        raise NotImplementedError

    def log(self, message):
        print(f"  [{self.platform.upper()}] {message}")


class LinkedInPoster(PlatformPoster):
    """Post to LinkedIn via API."""

    def __init__(self):
        super().__init__("linkedin")
        self.access_token = os.environ.get("LINKEDIN_ACCESS_TOKEN")

    def post(self, post_data):
        if not self.access_token:
            self.log("ERROR: LINKEDIN_ACCESS_TOKEN not set")
            return False

        if not HAS_REQUESTS:
            self.log("ERROR: 'requests' package not installed")
            return False

        text = post_data["post_text"]
        hashtags = post_data.get("hashtags", [])
        if hashtags:
            text += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)

        # LinkedIn API v2 - UGC Post
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        # First get the user's URN
        profile_resp = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers=headers
        )
        if profile_resp.status_code != 200:
            self.log(f"ERROR: Could not get profile: {profile_resp.text}")
            return False

        user_sub = profile_resp.json().get("sub")
        author_urn = f"urn:li:person:{user_sub}"

        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        resp = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json=payload
        )

        if resp.status_code in (200, 201):
            self.log(f"Posted successfully! ID: {resp.json().get('id', 'unknown')}")
            return True
        else:
            self.log(f"ERROR: {resp.status_code} - {resp.text}")
            return False


class TwitterPoster(PlatformPoster):
    """Post to Twitter/X via API v2."""

    def __init__(self):
        super().__init__("twitter")
        self.api_key = os.environ.get("TWITTER_API_KEY")
        self.api_secret = os.environ.get("TWITTER_API_SECRET")
        self.access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
        self.access_secret = os.environ.get("TWITTER_ACCESS_SECRET")

    def post(self, post_data):
        if not all([self.api_key, self.api_secret, self.access_token, self.access_secret]):
            self.log("ERROR: Twitter API credentials not fully set")
            return False

        if not HAS_REQUESTS:
            self.log("ERROR: 'requests' package not installed")
            return False

        try:
            from requests_oauthlib import OAuth1
        except ImportError:
            self.log("ERROR: 'requests_oauthlib' package not installed. Run: pip install requests-oauthlib")
            return False

        text = post_data["post_text"]
        hashtags = post_data.get("hashtags", [])
        if hashtags:
            text += " " + " ".join(f"#{h.lstrip('#')}" for h in hashtags[:3])

        # Truncate to 280 chars
        if len(text) > 280:
            text = text[:277] + "..."

        auth = OAuth1(self.api_key, self.api_secret, self.access_token, self.access_secret)
        resp = requests.post(
            "https://api.twitter.com/2/tweets",
            json={"text": text},
            auth=auth
        )

        if resp.status_code in (200, 201):
            tweet_id = resp.json().get("data", {}).get("id", "unknown")
            self.log(f"Tweeted successfully! ID: {tweet_id}")
            return True
        else:
            self.log(f"ERROR: {resp.status_code} - {resp.text}")
            return False


class FacebookPoster(PlatformPoster):
    """Post to Facebook Page via Graph API."""

    def __init__(self):
        super().__init__("facebook")
        self.page_token = os.environ.get("FACEBOOK_PAGE_TOKEN")

    def post(self, post_data):
        if not self.page_token:
            self.log("ERROR: FACEBOOK_PAGE_TOKEN not set")
            return False

        if not HAS_REQUESTS:
            self.log("ERROR: 'requests' package not installed")
            return False

        text = post_data["post_text"]
        hashtags = post_data.get("hashtags", [])
        if hashtags:
            text += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags[:3])

        resp = requests.post(
            f"https://graph.facebook.com/v18.0/me/feed",
            params={"access_token": self.page_token},
            json={"message": text}
        )

        if resp.status_code == 200:
            post_id = resp.json().get("id", "unknown")
            self.log(f"Posted successfully! ID: {post_id}")
            return True
        else:
            self.log(f"ERROR: {resp.status_code} - {resp.text}")
            return False


class BlueskyPoster(PlatformPoster):
    """Post to Bluesky via AT Protocol."""

    def __init__(self):
        super().__init__("bluesky")
        self.handle = os.environ.get("BLUESKY_HANDLE")
        self.app_password = os.environ.get("BLUESKY_APP_PASSWORD")

    def post(self, post_data):
        if not self.handle or not self.app_password:
            self.log("ERROR: BLUESKY_HANDLE or BLUESKY_APP_PASSWORD not set")
            return False

        if not HAS_REQUESTS:
            self.log("ERROR: 'requests' package not installed")
            return False

        # Authenticate
        auth_resp = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": self.handle, "password": self.app_password}
        )

        if auth_resp.status_code != 200:
            self.log(f"ERROR: Auth failed: {auth_resp.text}")
            return False

        session = auth_resp.json()
        did = session["did"]
        access_jwt = session["accessJwt"]

        text = post_data["post_text"]
        # Bluesky max 300 chars
        if len(text) > 300:
            text = text[:297] + "..."

        # Create post
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        resp = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {access_jwt}"},
            json={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": text,
                    "createdAt": now
                }
            }
        )

        if resp.status_code == 200:
            self.log(f"Posted successfully! URI: {resp.json().get('uri', 'unknown')}")
            return True
        else:
            self.log(f"ERROR: {resp.status_code} - {resp.text}")
            return False


class PostizPoster(PlatformPoster):
    """Post via self-hosted Postiz instance."""

    def __init__(self, platform="all"):
        super().__init__(f"postiz-{platform}")
        self.api_url = os.environ.get("POSTIZ_API_URL", "http://localhost:4200")
        self.api_key = os.environ.get("POSTIZ_API_KEY")

    def post(self, post_data):
        if not self.api_key:
            self.log("ERROR: POSTIZ_API_KEY not set")
            return False

        if not HAS_REQUESTS:
            self.log("ERROR: 'requests' package not installed")
            return False

        text = post_data["post_text"]
        hashtags = post_data.get("hashtags", [])
        if hashtags:
            text += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "content": text,
            "platforms": [post_data.get("platform", "all")],
            "schedule": post_data.get("schedule_time"),
            "media": []
        }

        resp = requests.post(
            f"{self.api_url}/api/posts",
            headers=headers,
            json=payload
        )

        if resp.status_code in (200, 201):
            self.log(f"Queued in Postiz! ID: {resp.json().get('id', 'unknown')}")
            return True
        else:
            self.log(f"ERROR: {resp.status_code} - {resp.text}")
            return False


class BufferPoster(PlatformPoster):
    """Post via Buffer API."""

    def __init__(self):
        super().__init__("buffer")
        self.access_token = os.environ.get("BUFFER_ACCESS_TOKEN")

    def post(self, post_data):
        if not self.access_token:
            self.log("ERROR: BUFFER_ACCESS_TOKEN not set")
            return False

        if not HAS_REQUESTS:
            self.log("ERROR: 'requests' package not installed")
            return False

        text = post_data["post_text"]
        hashtags = post_data.get("hashtags", [])
        if hashtags:
            text += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)

        # Get profiles
        profiles_resp = requests.get(
            "https://api.bufferapp.com/1/profiles.json",
            params={"access_token": self.access_token}
        )

        if profiles_resp.status_code != 200:
            self.log(f"ERROR: Could not get profiles: {profiles_resp.text}")
            return False

        profiles = profiles_resp.json()
        target_platform = post_data.get("platform", "")

        for profile in profiles:
            if target_platform and target_platform not in profile.get("service", "").lower():
                continue

            resp = requests.post(
                "https://api.bufferapp.com/1/updates/create.json",
                data={
                    "access_token": self.access_token,
                    "profile_ids[]": profile["id"],
                    "text": text,
                    "now": not post_data.get("schedule_time")
                }
            )

            if resp.status_code == 200:
                self.log(f"Queued in Buffer for {profile['service']}!")
            else:
                self.log(f"ERROR ({profile['service']}): {resp.text}")

        return True


# ---------------------------------------------------------------------------
# Main posting logic
# ---------------------------------------------------------------------------

def get_poster(platform, via=None):
    """Get the appropriate poster for a platform."""
    if via == "postiz":
        return PostizPoster(platform)
    elif via == "buffer":
        return BufferPoster()

    posters = {
        "linkedin": LinkedInPoster,
        "twitter": TwitterPoster,
        "facebook": FacebookPoster,
        "bluesky": BlueskyPoster,
    }

    poster_class = posters.get(platform)
    if poster_class:
        return poster_class()

    # For platforms without direct API support, suggest Postiz/Buffer
    print(f"  [{platform.upper()}] No direct API poster available.")
    print(f"  Tip: Use --via postiz or --via buffer for {platform}")
    return None


def post_approved(posts_file, platform_filter=None, via=None, schedule=False, delay=5):
    """Post all approved posts from a generated batch file."""
    with open(posts_file, "r") as f:
        batch = json.load(f)

    posts = batch.get("posts", [])
    approved = [p for p in posts if p.get("status") == "approved"]

    if not approved:
        print("\nNo approved posts found.")
        print("To approve posts, edit the JSON file and set status to 'approved'.")
        print("Or approve all pending posts with: --approve-all flag")
        return

    print(f"\n{'='*60}")
    print(f"  CRASH LENS Social Media Publisher")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Via: {via or 'Direct API'}")
    print(f"  Posts to publish: {len(approved)}")
    print(f"  Mode: {'Schedule' if schedule else 'Post now'}")
    print(f"{'='*60}\n")

    results = {"posted": 0, "failed": 0, "skipped": 0}

    for i, post in enumerate(approved):
        platform = post.get("platform", "unknown")

        if platform_filter and platform != platform_filter:
            results["skipped"] += 1
            continue

        print(f"\n[{i+1}/{len(approved)}] {platform.upper()} - {post.get('topic', 'No topic')}")

        poster = get_poster(platform, via)
        if not poster:
            results["skipped"] += 1
            continue

        success = poster.post(post)
        if success:
            post["status"] = "posted"
            post["posted_at"] = datetime.now().isoformat()
            results["posted"] += 1
        else:
            post["status"] = "failed"
            results["failed"] += 1

        # Rate limiting delay between posts
        if i < len(approved) - 1:
            print(f"  Waiting {delay}s before next post...")
            time.sleep(delay)

    # Save updated status back to file
    with open(posts_file, "w") as f:
        json.dump(batch, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  Results: {results['posted']} posted, {results['failed']} failed, {results['skipped']} skipped")
    print(f"  Updated statuses saved to: {posts_file}")
    print(f"{'='*60}")


def approve_all(posts_file):
    """Mark all pending posts as approved."""
    with open(posts_file, "r") as f:
        batch = json.load(f)

    count = 0
    for post in batch.get("posts", []):
        if post.get("status") == "pending_review":
            post["status"] = "approved"
            count += 1

    batch["review_status"] = "approved"
    batch["approved_at"] = datetime.now().isoformat()

    with open(posts_file, "w") as f:
        json.dump(batch, f, indent=2)

    print(f"Approved {count} posts in {posts_file}")


def list_posts(posts_file):
    """List all posts and their statuses."""
    with open(posts_file, "r") as f:
        batch = json.load(f)

    posts = batch.get("posts", [])
    print(f"\n{'='*60}")
    print(f"  Posts in: {posts_file}")
    print(f"  Total: {len(posts)}")
    print(f"{'='*60}\n")

    for i, post in enumerate(posts):
        status = post.get("status", "unknown")
        platform = post.get("platform", "unknown")
        topic = post.get("topic", "No topic")
        chars = len(post.get("post_text", ""))
        status_icon = {
            "pending_review": "[ ]",
            "approved": "[+]",
            "posted": "[v]",
            "failed": "[!]"
        }.get(status, "[?]")
        print(f"  {status_icon} {i+1:2d}. [{platform:10s}] {topic:40s} ({chars} chars) - {status}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CRASH LENS Social Media Publisher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python post_to_platforms.py output/posts_20260217.json --list
  python post_to_platforms.py output/posts_20260217.json --approve-all
  python post_to_platforms.py output/posts_20260217.json
  python post_to_platforms.py output/posts_20260217.json --via postiz
  python post_to_platforms.py output/posts_20260217.json --via buffer
  python post_to_platforms.py output/posts_20260217.json --platform linkedin
        """
    )
    parser.add_argument("posts_file", help="Path to generated posts JSON file")
    parser.add_argument("--platform", help="Post to specific platform only")
    parser.add_argument("--via", choices=["postiz", "buffer"], help="Post via aggregator service")
    parser.add_argument("--schedule", action="store_true", help="Schedule posts instead of posting now")
    parser.add_argument("--approve-all", action="store_true", help="Approve all pending posts")
    parser.add_argument("--list", action="store_true", help="List posts and their statuses")
    parser.add_argument("--delay", type=int, default=5, help="Seconds between posts (default: 5)")

    args = parser.parse_args()

    if not os.path.exists(args.posts_file):
        print(f"ERROR: File not found: {args.posts_file}")
        sys.exit(1)

    if args.list:
        list_posts(args.posts_file)
        return

    if args.approve_all:
        approve_all(args.posts_file)
        return

    post_approved(
        args.posts_file,
        platform_filter=args.platform,
        via=args.via,
        schedule=args.schedule,
        delay=args.delay
    )


if __name__ == "__main__":
    main()
