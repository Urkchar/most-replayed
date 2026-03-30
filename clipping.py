import logging

from web_parsing import get_markers_list


def clip_strict(markers_list: dict) -> list[dict[str: float]]:
    """Extract the start and end times of the "Most replayed" sections.

    Invoked with --strategy strict.
    
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


def clip_intensity(markers_list: list, intensity: float) -> list[dict[str: float]]:
    """Extract the start and end times of clips whose intensity is at least the
    specified intensity.
    
    Invoked with --strategy intensity.
    
    Positional arguments:
    markers_list -- the "markersList" dictionary from the initial data.
    intensity -- the minimum intensity for a clip to be included.

    Returns:
    A list of dictionaries, each containing the "start_time" and "end_time" of 
    a clip.
    """
    # markers is a list of dictionaries, each with startMillies (str), 
    # durationMillis (str), and intensityScoreNormalized (float) keys.
    markers = markers_list["markers"]

    clipping = False   # Flag indicating whether we're currently in a clip
    clips = []

    for marker in markers:
        # If the intensity of the heatmap at the current time is above the 
        # threshold and we're not currently in a clip, start a new clip.
        if marker["intensityScoreNormalized"] >= intensity and not clipping:
            clipping = True
            clip = {
                "start_time": int(marker["startMillis"]) / 1000
            }
            continue
        # If the intensity of the heatmap at the current time is below the 
        # threshold and we're currently in a clip, end the current clip and
        # add it to the list of clips.
        if marker["intensityScoreNormalized"] < intensity and clipping:
            clipping = False
            clip["end_time"] = int(marker["startMillis"]) / 1000
            clips.append(clip)

    return clips


def clip_time(markers_list: dict, duration: int) -> list[dict[str: float]]:
    """Extract the start and end times of clips such that the total duration of
    the clips is at least the specified duration.

    Invoked with --strategy time.
    
    Positional arguments:
    markers_list -- the "markersList" dictionary from the initial data.
    duration -- the minimum total duration of the clips (in seconds).

    Returns:
    A list of dictionaries, each containing the "start_time" and "end_time" of 
    a clip.
    """
    # markers is a list of dictionaries, each with startMillies (str), 
    # durationMillis (str), and intensityScoreNormalized (float) keys.
    markers = markers_list["markers"]

    total_seconds = 0
    intensity = 1

    # If we haven't reached the desired total duration of clips and the 
    # threshold can't be lowered, lower the threshold and try again.
    while total_seconds < duration and intensity > 0:
        intensity -= 0.01

        clips = []
        clipping = False   # Flag indicating whether we're currently in a clip
        for marker in markers:
            # If the intensity of the heatmap at the current time is above the 
            # threshold and we're not currently in a clip, start a new clip.
            if (marker["intensityScoreNormalized"] >= intensity 
                and not clipping):
                clipping = True
                clip = {
                    "start_time": int(marker["startMillis"]) / 1000
                }
                continue
            # If the intensity of the heatmap at the current time is below the 
            # threshold and we're currently in a clip, end the current clip and
            # add it to the list of clips.
            if marker["intensityScoreNormalized"] < intensity and clipping:
                clipping = False
                clip["end_time"] = int(marker["startMillis"]) / 1000
                clips.append(clip)
        
        durations = [clip["end_time"] - clip["start_time"] for clip in clips]
        total_seconds = sum(durations)
    
    return clips


# TODO Strict slow motion
# TODO Strict slow motion time-based
# TODO Fuzzy slow motion time-based


def get_time_ranges(data: dict, *, strategy: str, intensity: float, duration: int):
    """"""
    logging.debug("Extracting markers list...")
    markers_list = get_markers_list(data)
    logging.debug("Markers list extracted.")
    if strategy == "strict":
        clips = clip_strict(markers_list)
    if strategy == "intensity":
        clips = clip_intensity(markers_list, intensity)
    if strategy == "time":
        logging.debug("Clipping using time-based strategy...")
        clips = clip_time(markers_list, duration)
        logging.debug("Clipped using time-based strategy.")

    return clips
