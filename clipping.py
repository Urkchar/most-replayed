import logging

from web_parsing import get_markers_list


def clip_strict(markers_list: dict) -> list[dict[str: float]]:
    """Extract the start and end times of the "Most replayed" sections.
    
    Positional arguments:
    markers_list -- the "markersList" dictionary from the initial data. 

    Returns:
    A list of dictionaries, each containing the "start_time" and "end_time" of 
    a "Most replayed" section.
    """
    clips = []

    # Labels on areas of the heatmap
    markers_decoration = markers_list["markersDecoration"]
    timed_marker_decorations = markers_decoration["timedMarkerDecorations"]

    for decoration in timed_marker_decorations:
        label = decoration["label"]   # The text on the area of the heatmap

        # label is a dictionary with a "runs" key. The value of "runs" is a 
        # list of dictionaries, each with a "text" key.
        if any(run["text"] == "Most replayed" for run in label["runs"]):

            start_millis = decoration["visibleTimeRangeStartMillis"]
            end_millis = decoration["visibleTimeRangeEndMillis"]
            start_seconds = start_millis / 1000
            end_seconds = end_millis / 1000
            clip = {
                "start_time": start_seconds,
                "end_time": end_seconds
            }
            clips.append(clip)

    return clips


def clip_fuzzy(markers_list: list) -> list:
    """"""
    # TODO Intensity-based. Clips intensity > 0.5 etc.
    clips = []
    raise NotImplementedError


def clip_auto(markers_list: list) -> list:
    """"""
    markers = markers_list["markers"]
    total_seconds = 0
    intensity = 0.9
    while total_seconds < 61 and intensity > 0:
    # while intensity > 0:
        clips = []
        clipping = False
        for marker in markers:
            if (marker["intensityScoreNormalized"] >= intensity 
                and not clipping):
                clipping = True
                clip = {
                    "start_time": int(marker["startMillis"]) / 1000
                }
                continue
            if marker["intensityScoreNormalized"] < intensity and clipping:
                clipping = False
                clip["end_time"] = int(marker["startMillis"]) / 1000
                clips.append(clip)
        intensity -= 0.1
        durations = [clip["end_time"] - clip["start_time"] for clip in clips]
        total_seconds = sum(durations)
    
    return clips


# TODO Time-based fuzzy clip i.e. duration >= 60s
# TODO Strict slow motion
# TODO Strict slow motion time-based
# TODO Fuzzy slow motion time-based


def get_time_ranges(data: dict, *, strategy: str):
    """"""
    logging.debug("Extracting markers list...")
    markers_list = get_markers_list(data)
    logging.debug("Markers list extracted.")
    if strategy == "strict":
        clips = clip_strict(markers_list)
    if strategy == "fuzzy":
        clips = clip_fuzzy(markers_list)
    if strategy == "auto":
        logging.debug("Clipping using auto strategy...")
        clips = clip_auto(markers_list)
        logging.debug("Clipped using auto strategy.")

    return clips
