import requests
from bs4 import BeautifulSoup
import re
import json
import sys
import os
import logging
from yt_dlp import YoutubeDL


logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


HEADERS = {
    # YouTube serves different variants depending on headers; a desktop UA helps.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}


def extract_js_object_from_var(script_text: str, var_name: str) -> str | None:
    """
    Given the full text of a <script> tag and a variable name,
    returns the substring containing the JS object assigned to that var.
    Uses brace matching to handle nested objects safely.
    """
    # 1) Find "var|let|const varName =" or just "varName ="
    m = re.search(rf"(?:var|let|const)\s+{re.escape(var_name)}\s*=\s*", script_text)
    if not m:
        m = re.search(rf"{re.escape(var_name)}\s*=\s*", script_text)
    if not m:
        return None

    i = m.end()
    # 2) Seek the first opening brace '{'
    while i < len(script_text) and script_text[i] != "{":
        i += 1
    if i >= len(script_text):
        return None

    # 3) Brace-matching scan that ignores braces inside strings
    brace = 0
    j = i
    in_str = False
    quote = None
    esc = False

    while j < len(script_text):
        ch = script_text[j]

        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
        else:
            if ch in ("'", '"'):
                in_str = True
                quote = ch
            elif ch == "{":
                brace += 1
            elif ch == "}":
                brace -= 1
                if brace == 0:
                    j += 1  # include the closing '}'
                    break

        j += 1

    if brace != 0:
        return None  # unbalanced braces

    return script_text[i:j]  # the { ... } text


def normalize_js_like_json(text: str) -> str:
    r"""
    Make common JS-like constructs JSON-compatible.
    - Replace \xHH with \u00HH
    - Replace undefined/NaN/Infinity with null
    """
    # \xHH -> \u00HH
    text = re.sub(r'\\x([0-9A-Fa-f]{2})', lambda m: '\\u00' + m.group(1), text)
    # undefined, NaN, Infinity -> null
    text = re.sub(r'\bundefined\b', 'null', text)
    text = re.sub(r'\bNaN\b', 'null', text)
    text = re.sub(r'\bInfinity\b', 'null', text)
    return text


def extract_yt_initial_data(soup: BeautifulSoup) -> dict | None:
    """
    Finds the inline <script> that defines ytInitialData and returns it as a Python dict.
    """
    # YouTube embeds ytInitialData in an inline script; scan for it.
    for s in soup.find_all("script"):
        script_text = s.string or s.get_text() or ""
        if "ytInitialData" not in script_text:
            continue

        obj_text = extract_js_object_from_var(script_text, "ytInitialData")
        if not obj_text:
            continue

        # Try JSON parse directly first (YouTube usually uses valid JSON here)
        try:
            return json.loads(obj_text)
        except Exception:
            pass

        # Fallback: normalize some JS-isms then try again
        try:
            fixed = normalize_js_like_json(obj_text)
            return json.loads(fixed)
        except Exception:
            # As a last resort, give back the raw text so you can inspect it
            return None

    return None


def get_time_ranges(url: str) -> list[tuple[float]]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Falied to fetch URL: {e}")

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    data = extract_yt_initial_data(soup)
    time_ranges = []
    if not data:
        logging.warning("ytInitialData not found.")
        return time_ranges

    try:
        framework_updates = data["frameworkUpdates"]
        entity_batch_updates = framework_updates["entityBatchUpdate"]
        mutations = entity_batch_updates["mutations"]

        for mutation in mutations:
            if mutation["type"] != "ENTITY_MUTATION_TYPE_REPLACE":
                continue

            payload = mutation["payload"]
            macro_markers_list_entity = payload["macroMarkersListEntity"]
            markers_list = macro_markers_list_entity["markersList"]
            markers_decoration = markers_list["markersDecoration"]
            timed_marker_decorations = markers_decoration["timedMarkerDecorations"]

            for decoration in timed_marker_decorations:
                label = decoration["label"]
                runs = label["runs"]

                for run in runs:
                    text = run["text"]

                    if text != "Most replayed":
                        continue

                    start_time_seconds = decoration["visibleTimeRangeStartMillis"] / 1000    # Divide by 1000 to convert milliseconds to seconds
                    end_time_seconds = decoration["visibleTimeRangeEndMillis"] / 1000
                    time_range = {
                        "start_time": start_time_seconds,
                        "end_time": end_time_seconds
                    }
                    time_ranges.append(time_range)
    except KeyError as e:
        logging.debug(f"Missing key in data: {e}")

    return time_ranges


def main():
    if len(sys.argv) <= 1:
        logging.error("Must provide URL. Example usage:\npython main.py https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        sys.exit(1)
        
    url = sys.argv[1]
    pattern = r"https://www.youtube.com/watch\?v=[a-zA-Z0-9_]{11}"
    if not re.match(pattern, url):
        logging.error("Invalid YouTube URL.")
        sys.exit(1)

    def ranges(info_dict, ydl):
        webpage_url = info_dict["webpage_url"]
        logging.info("Extracting 'Most replayed' time ranges...")
        time_ranges = get_time_ranges(webpage_url)
        time_ranges_length = len(time_ranges)
        if time_ranges_length == 0:
            logging.error("Video has no 'Most replayed' sections.")
        else:
            logging.info(f"Extracted {time_ranges_length} 'Most replayed' time range(s).")
        return time_ranges

    paths = {
        "home": f"{os.getcwd()}\Clips"
    }
    ytdl_opts = {
        "download_ranges": ranges,
        "outtmpl": "%(title)s %(autonumber)s.%(ext)s",
        "fixup": "warn",
        "force_keyframes_at_cuts": True,
        "quiet": True,
        "paths": paths
    }

    with YoutubeDL(ytdl_opts) as ytdl:
        ytdl.download(url)


if __name__ == "__main__":
    main()
