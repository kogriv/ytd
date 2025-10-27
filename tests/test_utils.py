from __future__ import annotations

import json
from pathlib import Path

from ytd.utils import sanitize_filename, save_metadata_jsonl


def test_sanitize_filename_basic_cases():
    # недопустимые символы заменяются
    assert sanitize_filename('a<b>c:"d/e\\f|g?h*i') == "a_b_c__d_e_f_g_h_i"
    # управляющие символы и пробелы/точки в конце удаляются
    assert sanitize_filename('name. ') == 'name'
    assert sanitize_filename('') == ''


def test_sanitize_filename_reserved_and_length():
    # зарезервированное имя
    assert sanitize_filename('CON') == 'CON_'
    assert sanitize_filename('con.txt') == 'con_.txt'

    # ограничение длины 255, с сохранением расширения когда возможно
    long_base = 'a' * 300
    safe = sanitize_filename(long_base + '.mp4')
    assert len(safe) <= 255
    assert safe.endswith('.mp4')


def test_save_metadata_jsonl_appends(tmp_path: Path):
    meta_path = tmp_path / 'data' / 'meta.jsonl'

    obj1 = {"id": "1", "title": "First"}
    obj2 = {"id": "2", "title": "Second"}

    save_metadata_jsonl(obj1, meta_path)
    save_metadata_jsonl(obj2, meta_path)

    assert meta_path.exists()

    lines = meta_path.read_text(encoding='utf-8').splitlines()
    assert len(lines) == 2
    parsed = [json.loads(l) for l in lines]
    assert parsed[0]["id"] == "1"
    assert parsed[1]["id"] == "2"
