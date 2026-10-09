"""화면 없이(offscreen) GUI 동작을 확인하는 스모크 테스트."""

import os
import unicodedata
from collections.abc import Iterator
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFileOpenEvent, QIcon
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from pdf_merger.app import ICON_PATH, MainWindow, expand_pdf_paths, natural_key
from tests.test_merge import make_pdf


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp: QApplication) -> Iterator[MainWindow]:
    w = MainWindow()
    yield w
    w.close()


def names(w: MainWindow) -> list[str]:
    return [p.name for p in w.paths()]


def test_add_folder_uses_natural_order(tmp_path: Path, window: MainWindow) -> None:
    for n in ("10", "2", "1"):
        make_pdf(tmp_path / f"{n}.pdf", [100])
    (tmp_path / "memo.txt").write_text("not a pdf")

    window.add_paths([tmp_path])

    assert names(window) == ["1.pdf", "2.pdf", "10.pdf"]
    assert window.summary.text() == "파일 3개 · 총 3쪽"
    assert window.btn_merge.isEnabled()


def test_move_and_remove(tmp_path: Path, window: MainWindow) -> None:
    files = [make_pdf(tmp_path / f"{c}.pdf", [100]) for c in "abc"]
    window.add_paths(files)

    window.list.item(2).setSelected(True)
    window.move_selected(-1)
    assert names(window) == ["a.pdf", "c.pdf", "b.pdf"]

    window.move_selected(-1)
    window.move_selected(-1)  # 이미 맨 위면 그대로
    assert names(window) == ["c.pdf", "a.pdf", "b.pdf"]

    window.remove_selected()
    assert names(window) == ["a.pdf", "b.pdf"]

    window.sort_by_name()
    assert names(window) == ["a.pdf", "b.pdf"]


def test_merge_button_needs_two_files(tmp_path: Path, window: MainWindow) -> None:
    window.add_paths([make_pdf(tmp_path / "a.pdf", [100])])
    assert not window.btn_merge.isEnabled()


def test_expand_ignores_non_pdf(tmp_path: Path) -> None:
    txt = tmp_path / "a.txt"
    txt.write_text("x")
    upper = make_pdf(tmp_path / "B.PDF", [100])
    assert expand_pdf_paths([txt, upper]) == [upper]


def test_list_cleared_after_successful_merge(
    tmp_path: Path, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = [make_pdf(tmp_path / f"{c}.pdf", [100]) for c in "ab"]
    window.add_paths(files)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)  # 완료 창을 띄우지 않는다

    window._on_success(tmp_path / "out.pdf", 2)

    assert window.paths() == []
    assert all(f.exists() for f in files)  # 원본 파일은 그대로 둔다


def test_list_kept_after_failed_merge(tmp_path: Path, window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    window.add_paths([make_pdf(tmp_path / f"{c}.pdf", [100]) for c in "ab"])
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: None)

    window._on_failure("실패")

    assert names(window) == ["a.pdf", "b.pdf"]


def test_open_file_button_opens_merged_pdf(tmp_path: Path, window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[QUrl] = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox, "clickedButton", lambda self: next(b for b in self.buttons() if b.text() == "파일 열기")
    )
    output = tmp_path / "out.pdf"

    window._on_success(output, 2)

    assert opened == [QUrl.fromLocalFile(str(output))]


def test_file_open_event_adds_files(tmp_path: Path, qapp: QApplication, window: MainWindow) -> None:
    # macOS는 앱 아이콘에 끌어다 놓은 파일을 실행 인자 대신 FileOpen 이벤트로 넘겨준다.
    files = [make_pdf(tmp_path / f"{n}.pdf", [100]) for n in ("10", "2")]
    qapp.installEventFilter(window)
    try:
        for f in files:
            QApplication.sendEvent(qapp, QFileOpenEvent(str(f)))
        QTest.qWait(50)
    finally:
        qapp.removeEventFilter(window)

    assert names(window) == ["10.pdf", "2.pdf"]  # 넘겨받은 순서 그대로


def test_backspace_removes_selected(tmp_path: Path, window: MainWindow) -> None:
    # Mac 키보드의 delete 키는 Qt에서 Backspace로 들어온다.
    window.add_paths([make_pdf(tmp_path / f"{c}.pdf", [100]) for c in "ab"])
    window.show()
    QTest.qWaitForWindowExposed(window)
    window.list.setFocus()
    window.list.item(0).setSelected(True)

    QTest.keyClick(window.list, Qt.Key.Key_Backspace)

    assert names(window) == ["b.pdf"]


def test_natural_key_ignores_unicode_normalization() -> None:
    # macOS에서는 한글 파일 이름이 자모로 풀린(NFD) 형태로 들어오기도 한다.
    ga = Path(unicodedata.normalize("NFC", "가.pdf"))
    na = Path(unicodedata.normalize("NFD", "나.pdf"))
    assert sorted([na, ga], key=natural_key) == [ga, na]


def test_app_icon_loads(qapp: QApplication) -> None:
    assert not QIcon(str(ICON_PATH)).isNull()
