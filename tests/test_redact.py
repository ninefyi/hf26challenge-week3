import json
from datetime import datetime

from nightshift.chunk import chunk_messages
from nightshift.parse import Message, parse_export
from nightshift.queue import Queue, run
from nightshift.redact import load_terms, redact_messages, redact_text, summary


def r(text, terms=()):
    return redact_text(text, terms)[0]


def test_email():
    assert r("ส่งไปที่ ann.lee+x@acme-bank.co.th ด้วยนะ") == "ส่งไปที่ [EMAIL] ด้วยนะ"


def test_email_without_a_top_level_domain_and_bare_mentions():
    assert r("เช็คเมล์ dan@acmecorp ยังไม่มี") == "เช็คเมล์ [EMAIL] ยังไม่มี"
    assert r("@Dan ช่วยดูหน่อย") == "@Dan ช่วยดูหน่อย"


def test_url_keeps_only_the_domain():
    out = r("ดูที่ https://www.example.com/course/advanced-971?token=Abc123Def456 ค่ะ")
    assert out == "ดูที่ [URL:example.com] ค่ะ"
    assert r("เว็บ www.example.org/path") == "เว็บ [URL:example.org]"


def test_url_with_digits_in_domain_is_not_mangled_by_later_rules():
    assert r("https://bucket1234567.s3.amazonaws.com/x") == "[URL:bucket1234567.s3.amazonaws.com]"


def test_phone_numbers():
    assert r("โทร 081-234-5678 นะ") == "โทร [PHONE] นะ"
    assert r("โทร 0812345678") == "โทร [PHONE]"
    assert r("โทร +66 81 234 5678") == "โทร [PHONE]"


def test_long_digit_runs_are_numbers_but_short_ones_survive():
    assert r("บัตร 1234567890123 ค่ะ") == "บัตร [NUMBER] ค่ะ"
    assert r("โอน 1,000 บาท วันที่ 30 พ.ย. เวลา 9.30 ห้อง 18") == "โอน 1,000 บาท วันที่ 30 พ.ย. เวลา 9.30 ห้อง 18"
    assert r("วันที่ 2025.12.17 หรือ 15-16 มค.") == "วันที่ 2025.12.17 หรือ 15-16 มค."


def test_mixed_letter_digit_codes():
    assert r("Voucher for Dan: Mn4v8Rt29jHc6LsB") == "Voucher for Dan: [CODE]"
    assert r("ส่งcodeมาให้แล้วค่ะ Kd8f3Qw71xPz9mTb") == "ส่งcodeมาให้แล้วค่ะ [CODE]"
    assert r("รหัส:Mn4v8Rt29jHc6LsB") == "รหัส:[CODE]"  # glued to Thai, still caught


def test_dashed_keys_and_keyword_values():
    assert r("key ABCD-1234-EFGH-5678 ok") == "key [CODE] ok"
    assert r("password: hunter2! ok") == "password: [CODE] ok"
    assert "P@ss1234" not in r("รหัสผ่าน P@ss1234 ครับ")  # caught, whichever rule gets it first


def test_ordinary_words_and_course_names_survive():
    for t in ["Certified Cloud Engineer Associate", "Unit-42 workshop online 4-5 Dec 26",
              "code review tomorrow", "Troubleshooting", "สอบ data engineering basics"]:
        assert r(t) == t


def test_custom_terms_case_insensitive_longest_first_ascii_edges():
    terms = ["Acme", "Acme Bank", "แพร"]
    assert r("acme bank and ACME and Acmeville and คุณแพรครับ", terms) == "[REDACTED] and [REDACTED] and Acmeville and คุณ[REDACTED]ครับ"


def test_terms_cannot_break_an_earlier_email_placeholder():
    assert r("mail dan@acme.com", ["acme"]) == "mail [EMAIL]"


def test_placeholders_are_not_redacted_again():
    once = r("dan@x.com https://a1b2c3d4e5f6g7.example.com")
    assert r(once) == once


def test_counts_never_contain_the_secret():
    _, counts = redact_text("voucher Mn4v8Rt29jHc6LsB and 0812345678 and dan@x.com")
    assert dict(counts) == {"email": 1, "phone": 1, "code": 1}
    assert "Kd8f3" not in summary(counts)


def msg(sender, text):
    return Message(datetime(2026, 10, 1, 9, 0), sender, text)


def test_anonymise_senders_in_header_and_mentions():
    msgs = [msg("Anna Lee", "สวัสดี @Bob"), msg("Bob", "ครับ คุณ Anna Lee")]
    out, counts = redact_messages(msgs, anonymise_senders=True)
    assert [m.sender for m in out] == ["Person A", "Person B"]
    assert out[0].text == "สวัสดี @Person B"
    assert out[1].text == "ครับ คุณ Person A"
    assert counts["sender"] == 2


def test_redact_messages_leaves_senders_alone_by_default():
    out, _ = redact_messages([msg("Bob", "โทร 0812345678")])
    assert out[0].sender == "Bob" and out[0].text == "โทร [PHONE]"


def test_load_terms_skips_comments_and_blanks(tmp_path):
    f = tmp_path / "t.txt"
    f.write_text("# note\n\nAcme Bank\n  Dan  \n", encoding="utf-8")
    assert load_terms(f) == ["Acme Bank", "Dan"]


def test_chunks_and_work_files_hold_only_redacted_text(tmp_path):
    raw = "2026.10.01 Thursday\n09:00 Dan voucher Mn4v8Rt29jHc6LsB จาก dan@x.com\n09:01 Dan ขอบคุณครับ\n"
    msgs, _ = redact_messages(parse_export(raw))
    chunks = chunk_messages(msgs)
    assert "Kd8f3" not in chunks[0].text and "dan@x.com" not in chunks[0].text
    q = Queue(tmp_path)
    run(chunks, lambda c: {"id": c.id, "day": c.day, "items": [], "dropped": [], "seconds": 0},
        q, log=lambda *_: None)
    assert "Kd8f3" not in json.dumps(q.load_all())


def test_result_from_different_text_is_stale_and_redone(tmp_path):
    q = Queue(tmp_path)
    calls = []

    def summarise(c):
        calls.append(c.fingerprint)
        return {"id": c.id, "day": c.day, "items": [], "dropped": [], "seconds": 0}

    day = lambda text: chunk_messages([msg("A", text)])
    run(day("old text"), summarise, q, log=lambda *_: None)
    rep = run(day("old text"), summarise, q, log=lambda *_: None)
    assert rep.skipped == 1 and len(calls) == 1
    rep = run(day("new redacted text"), summarise, q, log=lambda *_: None)
    assert rep.done == 1 and rep.skipped == 0 and len(calls) == 2
