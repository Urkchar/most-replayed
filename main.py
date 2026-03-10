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


def get_time_ranges(url: str) -> list[tuple[int]] | None:
    pattern = r"https://www.youtube.com/watch\?v=[a-zA-Z0-9_]{11}"
    if not re.match(pattern, url):
        logging.error("Invalid YouTube URL.")
        sys.exit(1)
    
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    data = extract_yt_initial_data(soup)

    if data is None:
        raise RuntimeError("ytInitialData could not be found or could not be parsed.")
    
    if "frameworkUpdates" not in data:
        return None
    framework_updates = data["frameworkUpdates"]

    if "entityBatchUpdate" not in framework_updates:
        return None
    entity_batch_updates = framework_updates["entityBatchUpdate"]

    if "mutations" not in entity_batch_updates:
        return None
    mutations = entity_batch_updates["mutations"]

    pairs = []
    for mutation in mutations:
        if "type" not in mutation:
            raise RuntimeError("type not found in mutation.")
        if mutation["type"] != "ENTITY_MUTATION_TYPE_REPLACE":
            continue

        if "payload" not in mutation:
            raise RuntimeError("payload not found in mutation.")
        payload = mutation["payload"]

        if "macroMarkersListEntity" not in payload:
            continue
        macro_markers_list_entity = payload["macroMarkersListEntity"]

        if "markersList" not in macro_markers_list_entity:
            raise RuntimeError("markersList not found in macroMarkersListEntity.")
        markers_list = macro_markers_list_entity["markersList"]

        if "markersDecoration" not in markers_list:
            raise RuntimeError("markersDecoration not found in markersList.")
        markers_decoration = markers_list["markersDecoration"]

        if "timedMarkerDecorations" not in markers_decoration:
            raise RuntimeError("timedMarkerDecorations not found in markersDecoration.")
        timed_marker_decorations = markers_decoration["timedMarkerDecorations"]

        for decoration in timed_marker_decorations:
            if "label" not in decoration:
                raise RuntimeError("label not found in decoration.")
            label = decoration["label"]

            if "runs" not in label:
                raise RuntimeError("runs not found in label.")
            runs = label["runs"]

            for run in runs:
                if "text" not in run:
                    raise RuntimeError("text not found in run.")
                text = run["text"]

                if text != "Most replayed":
                    raise RuntimeError("text is not 'Most replayed'.")
                
                # pair = (decoration["visibleTimeRangeStartMillis"], decoration["visibleTimeRangeEndMillis"])
                start_time_seconds = decoration["visibleTimeRangeStartMillis"] / 1000
                end_time_seconds = decoration["visibleTimeRangeEndMillis"] / 1000
                pair = {
                    "start_time": start_time_seconds,
                    "end_time": end_time_seconds
                }
                pairs.append(pair)

    return pairs


def main():
    if len(sys.argv) <= 1:
        logging.error("Must provide URL. Example usage:\npython main.py https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        sys.exit(1)

    url = sys.argv[1]

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
