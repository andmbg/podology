from datetime import timedelta


def sec_to_time(sec: int):
    td = timedelta(seconds=sec)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, sec = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02}:{sec:02}"
    else:
        return f"{minutes:02}:{sec:02}"
