#!/usr/bin/env python3
"""
CRASH LENS Social Media Post Generator
=======================================
Generates platform-optimized social media posts using Claude API.
Reads crash data statistics and content templates to produce
ready-to-schedule posts for all configured platforms.

Usage:
    python generate_posts.py                          # Generate weekly batch
    python generate_posts.py --pillar safety_stats    # Specific content pillar
    python generate_posts.py --platform linkedin      # Specific platform only
    python generate_posts.py --topic "New feature X"  # Custom topic
    python generate_posts.py --count 5                # Number of posts
    python generate_posts.py --dry-run                # Preview without API call

Environment Variables:
    ANTHROPIC_API_KEY    - Required. Your Claude API key.
    SOCIAL_MEDIA_CONFIG  - Optional. Path to config.json (default: social_media/config.json)
"""

import argparse
import csv
import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = SCRIPT_DIR / "config.json"
TEMPLATES_DIR = SCRIPT_DIR / "templates"
OUTPUT_DIR = SCRIPT_DIR / "output"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_config(config_path=None):
    """Load social media configuration."""
    path = Path(config_path) if config_path else CONFIG_PATH
    with open(path, "r") as f:
        return json.load(f)


def load_template(platform):
    """Load a platform-specific prompt template."""
    template_path = TEMPLATES_DIR / f"{platform}.txt"
    if template_path.exists():
        return template_path.read_text()
    # Fall back to default template
    default_path = TEMPLATES_DIR / "default.txt"
    if default_path.exists():
        return default_path.read_text()
    return None


def load_crash_statistics():
    """
    Load crash data statistics from the repo's data files.
    Returns a summary dict that can be used in post generation.
    """
    stats = {
        "data_available": False,
        "summary": "No crash data loaded. Posts will use general safety content.",
        "details": {}
    }

    # Try to load from data directory
    data_dir = REPO_ROOT / "data"
    if not data_dir.exists():
        return stats

    # Look for CSV crash data files
    csv_files = list(data_dir.glob("*.csv"))
    if not csv_files:
        return stats

    # Parse the first/latest crash data file for statistics
    for csv_file in sorted(csv_files, reverse=True):
        try:
            with open(csv_file, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if not rows:
                continue

            # Extract basic statistics
            total_crashes = len(rows)
            severity_counts = {}
            collision_types = {}
            years = set()

            for row in rows:
                # Try common column names for severity
                severity = (
                    row.get("CRASH_SEVERITY", "") or
                    row.get("Severity", "") or
                    row.get("SEVERITY", "") or
                    row.get("severity", "")
                ).strip()
                if severity:
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1

                # Try common column names for collision type
                collision = (
                    row.get("COLLISION_TYPE", "") or
                    row.get("CollisionType", "") or
                    row.get("COLLISIONTYPE", "") or
                    row.get("collision_type", "")
                ).strip()
                if collision:
                    collision_types[collision] = collision_types.get(collision, 0) + 1

                # Try to extract year
                date_val = (
                    row.get("CRASH_DATE", "") or
                    row.get("CrashDate", "") or
                    row.get("DATE", "") or
                    row.get("date", "")
                ).strip()
                if date_val and len(date_val) >= 4:
                    try:
                        year = date_val[:4] if date_val[4] in "-/" else date_val[-4:]
                        if year.isdigit() and 2000 <= int(year) <= 2030:
                            years.add(int(year))
                    except (IndexError, ValueError):
                        pass

            stats["data_available"] = True
            stats["details"] = {
                "total_crashes": total_crashes,
                "severity_counts": severity_counts,
                "collision_types": dict(sorted(collision_types.items(), key=lambda x: -x[1])[:10]),
                "years": sorted(years),
                "source_file": csv_file.name
            }

            # Build human-readable summary
            severity_str = ", ".join(f"{k}: {v}" for k, v in sorted(severity_counts.items()))
            year_range = f"{min(years)}-{max(years)}" if years else "unknown period"
            stats["summary"] = (
                f"Dataset: {total_crashes:,} total crashes ({year_range}). "
                f"Severity breakdown: {severity_str}."
            )
            break  # Use the first valid file

        except Exception as e:
            print(f"  Warning: Could not parse {csv_file.name}: {e}")
            continue

    return stats


def select_content_pillar(config, requested_pillar=None):
    """Select a content pillar based on weights or explicit request."""
    pillars = config.get("content_pillars", {})

    if requested_pillar:
        # Match partial names
        for key, val in pillars.items():
            if requested_pillar.lower() in key.lower():
                return key, val
        print(f"Warning: Pillar '{requested_pillar}' not found. Using random.")

    # Weighted random selection
    keys = list(pillars.keys())
    weights = [pillars[k].get("weight", 0.1) for k in keys]
    chosen = random.choices(keys, weights=weights, k=1)[0]
    return chosen, pillars[chosen]


def pick_topic(pillar_info):
    """Pick a random topic from the pillar's example topics."""
    topics = pillar_info.get("example_topics", [])
    return random.choice(topics) if topics else pillar_info.get("description", "General safety content")


# ---------------------------------------------------------------------------
# Post generation
# ---------------------------------------------------------------------------

def build_prompt(platform, platform_config, pillar_name, pillar_info, topic, brand, crash_stats, custom_instructions=""):
    """Build the full prompt for Claude to generate a social media post."""
    template = load_template(platform)

    # Base context
    prompt = f"""You are the social media manager for {brand['name']} -- {brand['tagline']}.

{brand['description']}

Website: {brand['website']}
Handle: {brand['handle']}

---

TASK: Generate a {platform.upper()} post.

CONTENT PILLAR: {pillar_name.replace('_', ' ').title()}
Description: {pillar_info['description']}

TOPIC: {topic}

"""

    # Add crash data context if available
    if crash_stats.get("data_available"):
        prompt += f"""CRASH DATA CONTEXT (use relevant stats naturally in the post):
{crash_stats['summary']}

Detailed breakdown: {json.dumps(crash_stats['details'], indent=2)}

"""

    # Platform-specific rules
    prompt += f"""PLATFORM RULES FOR {platform.upper()}:
- Maximum characters: {platform_config.get('max_chars', 'no limit')}
- Maximum hashtags: {platform_config.get('max_hashtags', 5)}
- Tone: {platform_config.get('tone', 'professional')}
- Content types supported: {', '.join(platform_config.get('content_types', ['text_posts']))}

BRAND HASHTAGS (use 1-2 of these plus platform-relevant ones):
{', '.join(brand.get('hashtags', ['#CrashLens']))}

"""

    # Add template-specific instructions
    if template:
        prompt += f"""PLATFORM-SPECIFIC TEMPLATE INSTRUCTIONS:
{template}

"""

    # Custom instructions
    if custom_instructions:
        prompt += f"""ADDITIONAL INSTRUCTIONS:
{custom_instructions}

"""

    # Output format
    prompt += """OUTPUT FORMAT:
Return a JSON object with these fields:
{
  "post_text": "The full post text ready to publish",
  "hashtags": ["list", "of", "hashtags"],
  "suggested_image": "Brief description of an ideal accompanying image/graphic",
  "image_alt_text": "WCAG-compliant alt text for the suggested image",
  "call_to_action": "The CTA included in the post",
  "estimated_engagement": "low/medium/high",
  "best_posting_time": "Suggested time to post (e.g., Tuesday 9 AM EST)",
  "notes": "Any additional notes for the reviewer"
}

IMPORTANT RULES:
1. Stay within the character limit
2. Write naturally -- do NOT sound like an AI or use filler phrases
3. Include alt text for any suggested images (WCAG 2.1 AA compliance)
4. Make the content genuinely valuable to traffic engineers and safety professionals
5. Include a clear call-to-action
6. Use data/statistics when available to add credibility
7. Do NOT include the hashtags in the post_text -- list them separately
8. Return ONLY the JSON object, no other text
"""

    return prompt


def generate_post_with_claude(prompt, config):
    """Call Claude API to generate a social media post."""
    if not HAS_ANTHROPIC:
        print("ERROR: 'anthropic' package not installed. Run: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("  Export it: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    model = config.get("automation", {}).get("claude_model", "claude-sonnet-4-5-20250929")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()

    # Parse JSON from response (handle markdown code blocks)
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response_text[start:end])
        return {"post_text": response_text, "error": "Could not parse as JSON"}


def generate_dry_run_post(platform, pillar_name, topic, brand):
    """Generate a placeholder post without calling the API."""
    return {
        "post_text": f"[DRY RUN] {brand['name']}: {topic} -- This is a placeholder post for {platform}.",
        "hashtags": brand.get("hashtags", [])[:3],
        "suggested_image": f"Infographic about {topic}",
        "image_alt_text": f"Data visualization showing {topic} for {brand['name']}",
        "call_to_action": f"Learn more at {brand['website']}",
        "estimated_engagement": "medium",
        "best_posting_time": "Tuesday 9 AM EST",
        "notes": "Dry run -- no API call made"
    }


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------

def generate_batch(config, platforms=None, pillar=None, topic=None, count=None, dry_run=False):
    """Generate a batch of posts across platforms."""
    brand = config["brand"]
    all_platforms = config["platforms"]
    crash_stats = load_crash_statistics()

    # Filter platforms
    if platforms:
        target_platforms = {k: v for k, v in all_platforms.items()
                           if k in platforms and v.get("enabled", True)}
    else:
        target_platforms = {k: v for k, v in all_platforms.items()
                           if v.get("enabled", True)}

    if not target_platforms:
        print("No enabled platforms found.")
        return []

    # Determine post count per platform
    posts_per_platform = count or config.get("automation", {}).get("posts_per_batch", 20) // len(target_platforms)
    posts_per_platform = max(1, posts_per_platform)

    all_posts = []
    total = len(target_platforms) * posts_per_platform
    current = 0

    print(f"\n{'='*60}")
    print(f"  CRASH LENS Social Media Post Generator")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE (Claude API)'}")
    print(f"  Platforms: {', '.join(target_platforms.keys())}")
    print(f"  Posts per platform: {posts_per_platform}")
    print(f"  Total posts: {total}")
    if crash_stats["data_available"]:
        print(f"  Crash data: {crash_stats['summary'][:80]}...")
    else:
        print(f"  Crash data: Not available (using general content)")
    print(f"{'='*60}\n")

    for platform_name, platform_config in target_platforms.items():
        print(f"\n--- {platform_name.upper()} ---")

        for i in range(posts_per_platform):
            current += 1
            # Select content pillar and topic
            pillar_name, pillar_info = select_content_pillar(config, pillar)
            post_topic = topic or pick_topic(pillar_info)

            print(f"  [{current}/{total}] Pillar: {pillar_name} | Topic: {post_topic}")

            if dry_run:
                post_data = generate_dry_run_post(platform_name, pillar_name, post_topic, brand)
            else:
                prompt = build_prompt(
                    platform_name, platform_config,
                    pillar_name, pillar_info,
                    post_topic, brand, crash_stats
                )
                post_data = generate_post_with_claude(prompt, config)

            # Add metadata
            post_data["platform"] = platform_name
            post_data["pillar"] = pillar_name
            post_data["topic"] = post_topic
            post_data["generated_at"] = datetime.now().isoformat()
            post_data["status"] = "pending_review"

            all_posts.append(post_data)
            print(f"    -> Generated ({len(post_data.get('post_text', ''))} chars)")

    return all_posts


def save_posts(posts, output_dir=None):
    """Save generated posts to a JSON file."""
    out_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"posts_{timestamp}.json"
    filepath = out_dir / filename

    output = {
        "generated_at": datetime.now().isoformat(),
        "total_posts": len(posts),
        "posts": posts,
        "review_status": "pending",
        "approved_by": None,
        "approved_at": None
    }

    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  Saved {len(posts)} posts to: {filepath}")
    print(f"  Review status: PENDING")
    print(f"{'='*60}")

    return filepath


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CRASH LENS Social Media Post Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_posts.py                            # Generate weekly batch (all platforms)
  python generate_posts.py --platform linkedin        # LinkedIn only
  python generate_posts.py --pillar safety_statistics # Safety stats posts only
  python generate_posts.py --topic "New AI feature"   # Custom topic
  python generate_posts.py --count 3 --dry-run        # Preview 3 posts per platform
  python generate_posts.py --platform twitter --count 7  # Full week of tweets
        """
    )
    parser.add_argument("--config", type=str, help="Path to config.json")
    parser.add_argument("--platform", type=str, help="Target platform (linkedin, twitter, facebook, etc.)")
    parser.add_argument("--pillar", type=str, help="Content pillar (safety_statistics, product_features, etc.)")
    parser.add_argument("--topic", type=str, help="Custom topic for the posts")
    parser.add_argument("--count", type=int, help="Number of posts per platform")
    parser.add_argument("--dry-run", action="store_true", help="Preview without calling Claude API")
    parser.add_argument("--output-dir", type=str, help="Output directory for generated posts")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Parse platforms
    platforms = None
    if args.platform:
        platforms = [p.strip().lower() for p in args.platform.split(",")]

    # Generate posts
    posts = generate_batch(
        config,
        platforms=platforms,
        pillar=args.pillar,
        topic=args.topic,
        count=args.count,
        dry_run=args.dry_run
    )

    if not posts:
        print("No posts generated.")
        sys.exit(1)

    # Save output
    save_posts(posts, args.output_dir)

    # Summary
    print(f"\nNext steps:")
    if args.dry_run:
        print(f"  1. Review the output and run again without --dry-run")
    else:
        print(f"  1. Review the generated posts in the output file")
        print(f"  2. Edit any posts that need adjustments")
        print(f"  3. Use post_to_platforms.py to schedule approved posts")
        print(f"  4. Or import the JSON into Postiz/Buffer for scheduling")


if __name__ == "__main__":
    main()
