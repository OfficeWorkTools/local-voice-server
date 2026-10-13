"""Deterministic script conversion only; keep ASR words, English and numbers."""
from opencc import OpenCC

_converter = OpenCC("s2t")


def convert_text(text):
    return _converter.convert(text)
