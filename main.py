import requests
from pprint import pprint
from bs4 import BeautifulSoup
import re

url_without_most_replayed = "https://www.youtube.com/watch?v=XC8SlKJj4Zs"
url_with_most_replayed = "https://www.youtube.com/watch?v=9Oo1k_lNwlc"

resp = requests.get(url_with_most_replayed)
resp.raise_for_status()
soup = BeautifulSoup(resp.text, "html.parser")
scripts = soup.find_all("script")
script = scripts[1]
# pprint(len(scripts))

# for var in vars(script):
#     print(var)

# print(f"\nparser_class: {script.parser_class}\n")
# print(f"name: {script.name}\n")
# print(script.namespace)
# print(script._namespaces)
# print(script.prefix)
# print(script.sourceline)
# print(script.sourcepos)
# print(f"attribute_value_list_class: {script.attribute_value_list_class}\n")
# print(f"attrs: {script.attrs}\n")
# print(f"known_xml: {script.known_xml}\n")
# print(f"contents:")
# print(script.contents)
# print(type(script.contents))   # list
# print(type(script.contents[0]))   # <class 'bs4.element.Script'>
# print(script.contents[0])
# print(type(script.contents[0]))
# pprint(vars(script.contents[0]))

# print(f"cdata_list_attributes: {script.cdata_list_attributes}\n")
# print(type(script.string))
for string in script.strings:
    print(type(repr(string)))


# for script in scripts:
#     print(script.nonce)

pattern = r"var ytInitialData "
for i, script in enumerate(scripts):
    for string in script.strings:
        if re.findall(pattern, repr(string)):
            print(f"Found in script {i}")

# print(scripts[47])


import re
import json
from bs4 import BeautifulSoup

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


import requests
from bs4 import BeautifulSoup

url = url_without_most_replayed
headers = {
    # YouTube serves different variants depending on headers; a desktop UA helps.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}
html = requests.get(url, headers=headers, timeout=20).text
soup = BeautifulSoup(html, "html.parser")

data = extract_yt_initial_data(soup)
if data is None:
    print("ytInitialData not found or could not be parsed.")
else:
    # Now `data` is a Python dict; do whatever you like with it:
    print(type(data), len(data))
    # Example: print available keys at the top level
    print(list(data.keys()))

framework_updates = data["frameworkUpdates"]
print(framework_updates.keys())
entity_batch_update = framework_updates["entityBatchUpdate"]
print(entity_batch_update.keys())
mutations = entity_batch_update["mutations"]
for mutation in mutations:
    if mutation["type"] == "ENTITY_MUTATION_TYPE_REPLACE":
        payload = mutation["payload"]
        if "macroMarkersListEntity" in payload:
            macro_markers_list_entity = payload["macroMarkersListEntity"]
            markers_list = macro_markers_list_entity["markersList"]
            print(markers_list.keys())
            if "markersDecoration" in markers_list:
                markers_decoration = markers_list["markersDecoration"]
                # pprint(markers_decoration)
                print(markers_decoration.keys())
                if "timedMarkerDecorations" in markers_decoration:
                    timed_marker_decorations = markers_decoration["timedMarkerDecorations"]
                    pprint(timed_marker_decorations)
                    for timed_marker_decoration in timed_marker_decorations:
                        print(timed_marker_decoration)
                        if "label" in timed_marker_decoration:
                            label = timed_marker_decoration["label"]
                            print(label.keys())
                            if "runs" in label:
                                runs = label["runs"]
                                print(runs)
                                for run in runs:
                                    print(run)
                                    if "text" in run:
                                        text = run["text"]
                                        print(text)
                                        if text == "Most replayed":
                                            print("Video has 'Most replayed' section")