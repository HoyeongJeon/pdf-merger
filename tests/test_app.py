"""화면 없이(offscreen) GUI 동작을 확인하는 스모크 테스트."""

import os
from collections.abc import Iterator
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pdf_merger.app import MainWindow, expand_pdf_paths
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
