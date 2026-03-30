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
            ("Invalid URL; must look like "
             "https://www.youtube.com/watch?v=dQw4w9WgXcQ or "
             "https://youtu.be/dQw4w9WgXcQ?si=A9Ex2iHaIc8Ep9NZ\nExample: "
             "python main.py https://youtu.be/dQw4w9WgXcQ?si=A9Ex2iHaIc8Ep9NZ")
        )
        sys.exit(1)

    if args.strategy == "fuzzy" and args.intensity is None:
        logging.error(
            ("Must provide heartbeat intensity when using fuzzy clipping "
             "strategy.\nExample: python main.py --strategy fuzzy --intensity "
             "0.5 <URL>")
        )
        sys.exit(1)

    if args.strategy != "fuzzy" and args.intensity:
        logging.warning("Intensity only used with fuzzy strategy; ignoring.")

    if args.intensity and (args.intensity <= 0 or args.intensity >= 1):
        logging.error(
            ("Intensity must be greater than 0 and less than 1.\nExample: "
             "python main.py --strategy fuzzy --intensity 0.5 <URL>"))
        sys.exit(1)

    if args.strategy == "time" and args.duration is None:
        logging.error(
            ("Must provide minimum total duration of clips when using time "
             "clipping strategy.\nExample: python main.py --strategy time "
             "--duration 60 <URL>"))
        sys.exit(1)

    if args.strategy != "time" and args.duration:
        logging.warning("Duration only used with time strategy; ignoring.")

    if args.strategy == "time" and args.duration <= 0:
        logging.error(
            ("Duration must be a positive integer.\nExample: python main.py "
             "--strategy time --duration 60 <URL>"))
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download the “most-replayed” clips from a YouTube video."
    )

    p.add_argument(
        "url",
        help="YouTube video URL")
    p.add_argument(
        "-o", "--output",
        type=Path,
        default=Path.cwd() / "Clips",
        help="directory where clips are written")
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="more logging")
    p.add_argument(
        "-s", "--strategy",
        default="strict",
        choices=["fuzzy", "strict", "time"],
        help="clipping strategy.\n[fuzzy,strict,auto]")
    p.add_argument(
        "-i", "--intensity",
        type=float,
        help=("heartbeat intensity between 0 and 1. used with --strategy "
              "fuzzy."))
    p.add_argument(
        "-d", "--duration",
        type=int,
        help=("minimum total duration of clips (in seconds). used with "
              "--strategy time."))

    parsed_args = p.parse_args()
    validate_args(parsed_args)
    return parsed_args
