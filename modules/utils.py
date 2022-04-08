import traceback
import sys
import re


def extract_thread_ids(text: str):
    ids = []
    for match in re.finditer("threads/(?:[^\./]*\.)?(\d+)", text):
        ids.append(int(match.group(1)))
    return ids


def get_traceback():
    exc_info = sys.exc_info()
    tb_lines = traceback.format_exception(*exc_info)
    tb = "".join(tb_lines)
    return tb
