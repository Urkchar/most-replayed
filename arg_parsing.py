import re
import argparse
from pathlib import Path
import logging
import sys


def validate_url(url: str) -> bool:
    watch_pattern = r"https?://(www\.)?youtube\.com/watch\?v=[\w-]{11}"
    youtu_be_pattern = r"https?://youtu\.be/[\w-]{11}"
    return bool(
        re.match(watch_pattern, url)
        or re.match(youtu_be_pattern, url))


def validate_args(args):
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not validate_url(args.url):
        logging.error(
            "Invalid URL; must look like https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        sys.exit(1)

    if args.strategy not in {"strict", "fuzzy"}:
        logging.error("Clipping strategy must be fuzzy or strict.\nExample usage: python main.py -s strict <URL>")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download the “most-replayed” clips from a YouTube video."
    )
    p.add_argument("url", help="YouTube video URL")
    p.add_argument(
        "-o", "--output", type=Path, default=Path.cwd() / "Clips",
        help="directory where clips are written"
    )
    p.add_argument("-v", "--verbose", action="store_true", help="more logging")
    p.add_argument("-s", "--strategy", 
                   help="clipping strategy. fuzzy or strict.",
                   default="strict")
    parsed_args = p.parse_args()
    validate_args(parsed_args)
    return parsed_args
