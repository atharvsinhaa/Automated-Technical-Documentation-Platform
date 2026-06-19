"""utils.py — shared helpers"""
import re
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
def safe_str(v, maxlen=0) -> str:
    if v is None: return ""
    t = _CTRL.sub("", str(v))
    return t[:maxlen] + "…" if maxlen and len(t) > maxlen else t
