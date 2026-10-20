from datetime import datetime
from pathlib import Path

from nightshift.parse import parse_export

DEMO = Path(__file__).parent.parent / "demo" / "demo_chat.txt"


def test_basic_message_and_header_skipped():
    msgs = parse_export("[LINE] Chat\nSaved on: x\n\n2026.10.19 Monday\n09:12\tAnn\thello there\n")
    assert len(msgs) == 1
    assert msgs[0].when == datetime(2026, 10, 19, 9, 12)
    assert (msgs[0].sender, msgs[0].text) == ("Ann", "hello there")


def test_buddhist_year_is_converted():
    msgs = parse_export("2569.10.19 จันทร์\n09:00\tAnn\tสวัสดี\n")
    assert msgs[0].when.year == 2026


def test_weekday_first_day_month_year_header():
    msgs = parse_export("Mon, 19/10/2026\n09:00\tAnn\thi\n")
    assert msgs[0].when == datetime(2026, 10, 19, 9, 0)


def test_am_pm_times():
    msgs = parse_export("2026.10.19 Monday\n12:05 AM\tA\tx\n01:30 PM\tA\ty\n")
    assert [m.when.hour for m in msgs] == [0, 13]


def test_multiline_quoted_message_is_one_message_without_quotes():
    raw = '2026.10.19 Monday\n09:00\tAnn\t"line one\nline two"\n09:01\tBob\tok\n'
    msgs = parse_export(raw)
    assert [m.text for m in msgs] == ["line one\nline two", "ok"]


def test_system_media_and_empty_lines_dropped():
    raw = (
        "2026.10.19 Monday\n"
        "08:00\tAnn renamed the group\n"
        "08:01\tAnn\t[Sticker]\n"
        "08:02\tAnn\t[สติกเกอร์]\n"
        "08:03\tAnn\t[รูปภาพ]\n"
        "08:04\tAnn\treal message\n"
    )
    assert [m.text for m in parse_export(raw)] == ["real message"]


def test_messages_before_any_date_header_are_ignored():
    assert parse_export("09:00\tAnn\torphan\n") == []


def test_crlf_and_bom():
    msgs = parse_export("﻿2026.10.19 Monday\r\n09:00\tAnn\thi\r\n")
    assert len(msgs) == 1


def test_demo_chat_parses_to_three_days():
    msgs = parse_export(DEMO.read_text(encoding="utf-8"))
    assert {f"{m.when:%Y-%m-%d}" for m in msgs} == {"2026-10-17", "2026-10-18", "2026-10-19"}
    assert all(m.sender and m.text for m in msgs)
    assert not any("สติกเกอร์" in m.text or "รูปภาพ" in m.text for m in msgs)
    multi = [m for m in msgs if "\n" in m.text]
    assert len(multi) == 1 and "3,500" in multi[0].text
