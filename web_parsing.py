import re
import json
import logging
import requests
from bs4 import BeautifulSoup
import sys

# YouTube serves different variants depending on headers; a desktop UA helps.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}


def extract_js_object_from_var(script_text: str, var_name: str) -> str | None:
    """
    Given the full text of a <script> tag and a variable name,
    returns the substring containing the JS object assigned to that var.
    Uses brace matching to handle nested objects safely.
    """
    # 1) Find "var|let|const varName =" or just "varName ="
    m = re.search(
        rf"(?:var|let|const)\s+{re.escape(var_name)}\s*=\s*", script_text)
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
    """Finds the inline <script> that defines ytInitialData and returns it as
    a Python dict.
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


def fetch_html(url: str) -> str | None:
    """Fetch HTML content from the URL with error handling."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logging.error(f"Failed to fetch HTML: {e}")
        return None


def get_markers_list(data: dict) -> list:
    """"""
    framework_updates = data["frameworkUpdates"]
    entity_batch_update = framework_updates["entityBatchUpdate"]
    mutations = entity_batch_update["mutations"]

    markers_list = None
    for mutation in mutations:
        if mutation["type"] != "ENTITY_MUTATION_TYPE_REPLACE":
            continue
        payload = mutation["payload"]
        if "macroMarkersListEntity" not in payload:
            continue
        macro_markers_list_entity = payload["macroMarkersListEntity"]
        if "markersList" not in macro_markers_list_entity:
            continue
        markers_list = macro_markers_list_entity["markersList"]
        break

    if not markers_list:
        logging.error("Video has no heartbeat.")
        sys.exit(1)

    return markers_list
