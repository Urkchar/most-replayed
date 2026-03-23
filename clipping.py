from web_parsing import get_markers_list


def clip_strict(markers_list: list) -> list:
    """"""
    clips = []
    markers_decoration = markers_list["markersDecoration"]
    timed_marker_decorations = markers_decoration["timedMarkerDecorations"]
    for decoration in timed_marker_decorations:
        label = decoration["label"]
        if any(run["text"] == "Most replayed" for run in label["runs"]):
            start_millis = int(decoration["visibleTimeRangeStartMillis"])
            start_seconds = start_millis / 1000
            end_millis = int(decoration["visibleTimeRangeEndMillis"])
            end_seconds = end_millis / 1000
            clip = {
                "start_time": start_seconds,
                "end_time": end_seconds
            }
            clips.append(clip)

    return clips


def clip_fuzzy(markers_list: list) -> list:
    """"""
    clips = []
    raise NotImplementedError


def clip_auto(markers_list: list) -> list:
    """"""
    markers = markers_list["markers"]
    total_seconds = 0
    intensity = 0.9
    while total_seconds < 61:
        clips = []
        clipping = False
        for marker in markers:
            if (marker["intensityScoreNormalized"] >= intensity 
                and not clipping):
                clipping = True
                clip = {
                    "start_time": int(marker["startMillis"])
                }
                continue
            if marker["intensityScoreNormalized"] < intensity and clipping:
                clipping = False
                clip["end_time"] = int(marker["startMillis"])
                clips.append(clip)
        intensity -= 0.1
        durations = [clip["end_time"] - clip["start_time"] for clip in clips]
        total_seconds = sum(durations) / 1000
    
    return clips


def get_time_ranges(data: dict, *, strategy: str):
    """"""
    markers_list = get_markers_list(data)
    if strategy == "strict":
        clips = clip_strict(markers_list)
    if strategy == "fuzzy":
        clips = clip_fuzzy(markers_list)
    if strategy == "auto":
        clips = clip_auto(markers_list)

    return clips
