"""PDF 병합기 GUI (PySide6)."""

import os
import re
import sys
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pdf_merger.merge import PdfError, merge_pdfs, page_count

APP_NAME = "PDF 병합기"
PATH_ROLE = Qt.ItemDataRole.UserRole
PAGES_ROLE = Qt.ItemDataRole.UserRole + 1


def natural_key(path: Path) -> list[int | str]:
    """'2.pdf'가 '10.pdf'보다 앞에 오도록 숫자를 숫자로 비교한다."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def expand_pdf_paths(paths: list[Path]) -> list[Path]:
    """폴더는 안의 PDF들(이름순)로 펼치고, PDF가 아닌 파일은 버린다."""
    result: list[Path] = []
    for p in paths:
        if p.is_dir():
            result.extend(sorted((c for c in p.iterdir() if c.suffix.lower() == ".pdf"), key=natural_key))
        elif p.suffix.lower() == ".pdf":
            result.append(p)
    return result


class PdfListWidget(QListWidget):
    """탐색기에서 끌어다 놓기 + 목록 안에서 끌어서 순서 바꾸기를 지원하는 목록."""

    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAlternatingRowColors(True)

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e: QDragMoveEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e: QDropEvent) -> None:
        if e.mimeData().hasUrls():
            paths = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
            e.acceptProposedAction()
            self.files_dropped.emit(paths)
        else:
            super().dropEvent(e)


class MergeThread(QThread):
    """병합 중에도 창이 멈추지 않도록 백그라운드에서 병합한다."""

    progress = Signal(int, int)
    succeeded = Signal(object, int)  # (출력 경로, 총 페이지 수)
    failed = Signal(str)

    def __init__(self, inputs: list[Path], output: Path) -> None:
        super().__init__()
        self.inputs = inputs
        self.output = output

    def run(self) -> None:
        try:
            total = merge_pdfs(self.inputs, self.output, on_progress=self.progress.emit)
        except PdfError as e:
            self.failed.emit(str(e))
        except Exception as e:  # 예상 못한 오류도 사용자에게 보여준다
            self.failed.emit(f"알 수 없는 오류가 발생했습니다: {e}")
        else:
            self.succeeded.emit(self.output, total)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(640, 480)
        self.setMinimumSize(480, 320)
        self._thread: MergeThread | None = None

        self.list = PdfListWidget()
        self.list.files_dropped.connect(self.add_paths)
        self.list.model().rowsInserted.connect(self._update_state)
        self.list.model().rowsRemoved.connect(self._update_state)
        self.list.model().rowsMoved.connect(self._update_state)
        self.list.itemSelectionChanged.connect(self._update_state)

        self.hint = QLabel(
            "PDF 파일이나 폴더를 여기로 끌어다 놓거나 [파일 추가]를 누르세요.\n목록에서 끌어서 순서를 바꿀 수 있습니다."
        )
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet("color: gray;")

        self.btn_add = QPushButton("파일 추가…")
        self.btn_up = QPushButton("▲ 위로")
        self.btn_down = QPushButton("▼ 아래로")
        self.btn_sort = QPushButton("이름순 정렬")
        self.btn_remove = QPushButton("선택 삭제")
        self.btn_clear = QPushButton("모두 지우기")
        self.btn_merge = QPushButton("병합하기")
        self.btn_merge.setDefault(True)
        self.btn_merge.setMinimumHeight(36)

        self.btn_add.clicked.connect(self.choose_files)
        self.btn_up.clicked.connect(lambda: self.move_selected(-1))
        self.btn_down.clicked.connect(lambda: self.move_selected(1))
        self.btn_sort.clicked.connect(self.sort_by_name)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear.clicked.connect(self.list.clear)
        self.btn_merge.clicked.connect(self.merge)

        QShortcut(QKeySequence.StandardKey.Delete, self.list, self.remove_selected)
        QShortcut(QKeySequence.StandardKey.Open, self, self.choose_files)
        QShortcut(QKeySequence("Ctrl+Up"), self.list, lambda: self.move_selected(-1))
        QShortcut(QKeySequence("Ctrl+Down"), self.list, lambda: self.move_selected(1))

        side = QVBoxLayout()
        for b in (self.btn_add, self.btn_up, self.btn_down, self.btn_sort, self.btn_remove, self.btn_clear):
            side.addWidget(b)
        side.addStretch()

        body = QHBoxLayout()
        body.addWidget(self.list, 1)
        body.addLayout(side)

        self.summary = QLabel()
        self.progress = QProgressBar()
        self.progress.setVisible(False)

        bottom = QHBoxLayout()
        bottom.addWidget(self.summary, 1)
        bottom.addWidget(self.progress)
        bottom.addWidget(self.btn_merge)

        root = QVBoxLayout()
        root.addWidget(self.hint)
        root.addLayout(body, 1)
        root.addLayout(bottom)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)
        self._update_state()

    # ---- 목록 조작 -------------------------------------------------------

    def paths(self) -> list[Path]:
        return [self.list.item(i).data(PATH_ROLE) for i in range(self.list.count())]

    def choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "PDF 선택", self._last_dir(), "PDF 파일 (*.pdf)")
        self.add_paths([Path(f) for f in files])

    def add_paths(self, paths: list[Path]) -> None:
        errors: list[str] = []
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for path in expand_pdf_paths(paths):
                try:
                    pages = page_count(path)
                except PdfError as e:
                    errors.append(str(e))
                    continue
                item = QListWidgetItem(f"{path.name}   ({pages}쪽)")
                item.setData(PATH_ROLE, path)
                item.setData(PAGES_ROLE, pages)
                item.setToolTip(str(path))
                self.list.addItem(item)
        finally:
            QApplication.restoreOverrideCursor()
        if errors:
            QMessageBox.warning(self, APP_NAME, "다음 파일은 추가하지 못했습니다:\n\n" + "\n".join(errors))

    def remove_selected(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))

    def move_selected(self, delta: int) -> None:
        rows = sorted(self.list.row(i) for i in self.list.selectedItems())
        if not rows or rows[0] + delta < 0 or rows[-1] + delta >= self.list.count():
            return
        for row in rows if delta < 0 else reversed(rows):
            self.list.insertItem(row + delta, self.list.takeItem(row))
        self.list.clearSelection()
        for row in rows:
            self.list.item(row + delta).setSelected(True)
        self.list.setCurrentRow(rows[0] + delta, QItemSelectionModel.SelectionFlag.NoUpdate)

    def sort_by_name(self) -> None:
        items = [self.list.takeItem(0) for _ in range(self.list.count())]
        for item in sorted(items, key=lambda it: natural_key(it.data(PATH_ROLE))):
            self.list.addItem(item)

    # ---- 병합 -----------------------------------------------------------

    def merge(self) -> None:
        inputs = self.paths()
        if len(inputs) < 2:
            return
        default = Path(self._last_dir()) / "병합된 파일.pdf"
        out, _ = QFileDialog.getSaveFileName(self, "저장할 위치", str(default), "PDF 파일 (*.pdf)")
        if not out:
            return
        output = Path(out)
        if output.suffix.lower() != ".pdf":
            output = output.with_name(output.name + ".pdf")

        self._set_busy(True)
        self._thread = MergeThread(inputs, output)
        self._thread.progress.connect(self._on_progress)
        self._thread.succeeded.connect(self._on_success)
        self._thread.failed.connect(self._on_failure)
        self._thread.finished.connect(lambda: self._set_busy(False))
        self._thread.start()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(done)

    def _on_success(self, output: Path, pages: int) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(f"병합을 마쳤습니다. (총 {pages}쪽)\n\n{output}")
        open_file = box.addButton("파일 열기", QMessageBox.ButtonRole.AcceptRole)
        open_dir = box.addButton("폴더 열기", QMessageBox.ButtonRole.ActionRole)
        box.addButton("닫기", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_file:
            os.startfile(output)
        elif box.clickedButton() is open_dir:
            os.startfile(output.parent)

    def _on_failure(self, message: str) -> None:
        QMessageBox.critical(self, APP_NAME, message)

    # ---- 상태 -----------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.progress.setRange(0, 0)  # 첫 진행 신호 전까지는 '진행 중' 애니메이션
        self.list.setEnabled(not busy)
        self.setAcceptDrops(not busy)
        for b in (self.btn_add, self.btn_up, self.btn_down, self.btn_sort, self.btn_remove, self.btn_clear):
            b.setEnabled(not busy)
        if busy:
            self.btn_merge.setEnabled(False)
        else:
            self._update_state()

    def _update_state(self) -> None:
        count = self.list.count()
        has_sel = bool(self.list.selectedItems())
        pages = sum(self.list.item(i).data(PAGES_ROLE) for i in range(count))
        self.summary.setText(f"파일 {count}개 · 총 {pages}쪽" if count else "")
        self.btn_merge.setEnabled(count >= 2)
        self.btn_up.setEnabled(has_sel)
        self.btn_down.setEnabled(has_sel)
        self.btn_remove.setEnabled(has_sel)
        self.btn_sort.setEnabled(count >= 2)
        self.btn_clear.setEnabled(count > 0)

    def _last_dir(self) -> str:
        paths = self.paths()
        return str(paths[-1].parent) if paths else str(Path.home() / "Documents")

    def closeEvent(self, event) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.wait()
        super().closeEvent(event)


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    # 명령줄이나 exe 아이콘에 끌어다 놓은 파일도 바로 추가한다.
    if len(sys.argv) > 1:
        window.add_paths([Path(a) for a in sys.argv[1:]])
    return app.exec()
