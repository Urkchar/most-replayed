from bs4 import BeautifulSoup
import sys
import logging
from yt_dlp import YoutubeDL

from clipping import get_time_ranges
from arg_parsing import parse_args
from web_parsing import fetch_html, extract_yt_initial_data


logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def main():
    args = parse_args()

    logging.debug("Fetching HTML...")
    html = fetch_html(args.url)
    logging.debug("HTML fetched.")
    logging.debug("Initializing soup...")
    soup = BeautifulSoup(html, "html.parser")
    logging.debug("Soup initialized.")
    logging.debug("Extracting initial data...")
    data = extract_yt_initial_data(soup)
    logging.debug("Initial data extracted.")
    logging.info("Getting time ranges...")
    time_ranges = get_time_ranges(data, strategy=args.strategy)
    if not time_ranges:
        logging.error("Video has no 'Most replayed' section(s).")
        sys.exit(1)
    logging.info(
        f"Extracted {len(time_ranges)} 'Most replayed' time range(s).")
    logging.debug(time_ranges)


    output_directory = args.output / soup.title.text.rstrip(" - YouTube")
    output_directory.mkdir(exist_ok=True, parents=True)

    def ranges(info_dict, ydl):
        return time_ranges

    paths = {
        "home": str(output_directory)
    }
    ytdl_opts = {
        "download_ranges": ranges,
        "outtmpl": "%(autonumber)s.%(ext)s",
        "fixup": "warn",
        "force_keyframes_at_cuts": True,
        "quiet": not args.verbose,
        "paths": paths,
        "retries": 3
    }

    with YoutubeDL(ytdl_opts) as ytdl:
        try:
            logging.debug("Starting download...")
            ytdl.download(args.url)
            logging.debug("Download finished.")
        except Exception as e:
            logging.error("yt-dlp failed: %s", e)
            sys.exit(1)


if __name__ == "__main__":
    main()
