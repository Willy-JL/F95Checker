import re


def extract_thread_ids(text):
    ids = []
    for match in re.finditer("threads/(?:[^\./]*\.)?(\d+)", text):
        ids.append(int(match.group(1)))
    return ids
