from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from pdf_merger.merge import PasswordError, PdfError, merge_pdfs, page_count


def make_pdf(path: Path, widths: list[int], password: str | None = None, algorithm: str = "RC4-128") -> Path:
    """페이지 너비로 각 페이지를 구분할 수 있는 테스트용 PDF를 만든다."""
    writer = PdfWriter()
    for w in widths:
        writer.add_blank_page(width=w, height=100)
    if password is not None:
        writer.encrypt(user_password=password, owner_password="owner", algorithm=algorithm)
    writer.write(path)
    return path


def widths_of(path: Path) -> list[int]:
    return [int(p.mediabox.width) for p in PdfReader(path).pages]


def test_merge_keeps_order(tmp_path: Path) -> None:
    a = make_pdf(tmp_path / "a.pdf", [100, 101])
    b = make_pdf(tmp_path / "b.pdf", [200])
    c = make_pdf(tmp_path / "c.pdf", [300, 301, 302])
    out = tmp_path / "out" / "merged.pdf"

    total = merge_pdfs([c, a, b], out)

    assert total == 6
    assert widths_of(out) == [300, 301, 302, 100, 101, 200]


def test_merge_reports_progress(tmp_path: Path) -> None:
    files = [make_pdf(tmp_path / f"{i}.pdf", [100]) for i in range(3)]
    calls: list[tuple[int, int]] = []

    merge_pdfs(files, tmp_path / "out.pdf", on_progress=lambda d, t: calls.append((d, t)))

    assert calls == [(1, 3), (2, 3), (3, 3)]


def test_same_file_twice_is_allowed(tmp_path: Path) -> None:
    a = make_pdf(tmp_path / "a.pdf", [100])
    assert merge_pdfs([a, a], tmp_path / "out.pdf") == 2


def test_korean_paths(tmp_path: Path) -> None:
    folder = tmp_path / "한글 폴더"
    folder.mkdir()
    a = make_pdf(folder / "첫번째.pdf", [100])
    b = make_pdf(folder / "두번째.pdf", [200])
    out = folder / "병합된 파일.pdf"

    merge_pdfs([a, b], out)

    assert widths_of(out) == [100, 200]


def test_empty_password_pdf_is_merged(tmp_path: Path) -> None:
    locked = make_pdf(tmp_path / "locked.pdf", [100], password="")
    plain = make_pdf(tmp_path / "plain.pdf", [200])

    merge_pdfs([locked, plain], tmp_path / "out.pdf")

    assert widths_of(tmp_path / "out.pdf") == [100, 200]


def test_password_pdf_needs_password(tmp_path: Path) -> None:
    locked = make_pdf(tmp_path / "secret.pdf", [100], password="1234")
    with pytest.raises(PasswordError, match="secret"):
        page_count(locked)


@pytest.mark.parametrize("algorithm", ["RC4-128", "AES-256"])
def test_password_pdf_opens_with_password(tmp_path: Path, algorithm: str) -> None:
    locked = make_pdf(tmp_path / "secret.pdf", [100, 101], password="1234", algorithm=algorithm)
    assert page_count(locked, password="1234") == 2


def test_wrong_password_is_rejected(tmp_path: Path) -> None:
    locked = make_pdf(tmp_path / "secret.pdf", [100], password="1234", algorithm="AES-256")
    with pytest.raises(PasswordError):
        page_count(locked, password="0000")


def test_merge_unlocks_with_given_passwords(tmp_path: Path) -> None:
    locked = make_pdf(tmp_path / "locked.pdf", [100], password="1234", algorithm="AES-256")
    plain = make_pdf(tmp_path / "plain.pdf", [200])
    out = tmp_path / "out.pdf"

    merge_pdfs([locked, plain, locked], out, passwords={locked: "1234"})

    assert widths_of(out) == [100, 200, 100]
    assert not PdfReader(out).is_encrypted  # 결과 파일에는 암호가 없다


def test_broken_pdf_is_rejected(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"this is not a pdf")
    with pytest.raises(PdfError, match=r"broken\.pdf"):
        page_count(broken)


def test_output_cannot_be_an_input(tmp_path: Path) -> None:
    a = make_pdf(tmp_path / "a.pdf", [100])
    b = make_pdf(tmp_path / "b.pdf", [200])
    with pytest.raises(PdfError, match="원본"):
        merge_pdfs([a, b], a)
    assert widths_of(a) == [100]  # 원본이 망가지지 않아야 한다


def test_failed_merge_leaves_existing_output_untouched(tmp_path: Path) -> None:
    out = make_pdf(tmp_path / "out.pdf", [999])
    a = make_pdf(tmp_path / "a.pdf", [100])
    with pytest.raises(PdfError):
        merge_pdfs([a, tmp_path / "missing.pdf"], out)
    assert widths_of(out) == [999]
    assert list(tmp_path.glob("tmp*.pdf")) == []  # 임시 파일도 남지 않아야 한다
