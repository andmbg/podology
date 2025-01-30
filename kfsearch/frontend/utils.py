import re
from datetime import timedelta
from dash.html import Mark


def sec_to_time(sec: int):
    td = timedelta(seconds=sec)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, sec = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02}:{sec:02}"
    else:
        return f"{minutes:02}:{sec:02}"


def split_highlight_string(highlight, tag="bling") -> tuple:
    pattern = f"(<{tag}>.*</{tag}>)"
    match = re.search(pattern, highlight)

    if match:
        prefix = highlight[: match.start()]
        mid = match.group(1)
        suffix = highlight[match.end() :]

        # Split mid into segments, remove tags and wrap them in Mark elements:
        mid_list = re.split(rf"(<{tag}>.*?</{tag}>)", mid)
        mid_list = [i for i in mid_list if i != ""]
        hl = []
        for segment in mid_list:
            if segment.startswith(f"<{tag}"):
                addendum = re.sub(rf"<{tag}>(.*)</{tag}>", r"\1", segment)
                hl.append(Mark(addendum))
            else:
                hl.append(segment)

        # Calculate the string length of the middle part:
        len_hl = sum([len(i) if type(i) == str else len(i.children) for i in mid_list])

        return (prefix, hl, suffix), len_hl
