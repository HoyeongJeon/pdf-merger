"""PDF 병합기 GUI (PySide6)."""

import re
import sys
import unicodedata
from pathlib import Path

from PySide6.QtCore import QEvent, QItemSelectionModel, QObject, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFileOpenEvent,
    QIcon,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pdf_merger.merge import PasswordError, PdfError, merge_pdfs, page_count

APP_NAME = "PDF 병합기"
ICON_PATH = Path(__file__).parent / "assets" / "icon.png"
PATH_ROLE = Qt.ItemDataRole.UserRole
PAGES_ROLE = Qt.ItemDataRole.UserRole + 1
PASSWORD_ROLE = Qt.ItemDataRole.UserRole + 2  # 암호는 메모리에만 두고 파일로 저장하지 않는다


def natural_key(path: Path) -> list[int | str]:
    """'2.pdf'가 '10.pdf'보다 앞에 오도록 숫자를 숫자로 비교한다."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", display_name(path))]


def display_name(path: Path) -> str:
    """macOS가 자모로 풀어 둔(NFD) 한글 이름도 보통 글자(NFC)로 맞춘다."""
    return unicodedata.normalize("NFC", path.name)


def open_path(path: Path) -> None:
    """기본 프로그램(Windows 탐색기, macOS Finder 등)으로 연다."""
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


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

    def __init__(self, inputs: list[Path], output: Path, passwords: dict[Path, str]) -> None:
        super().__init__()
        self.inputs = inputs
        self.output = output
        self.passwords = passwords

    def run(self) -> None:
        try:
            total = merge_pdfs(self.inputs, self.output, on_progress=self.progress.emit, passwords=self.passwords)
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
        self._opened_files: list[Path] = []

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
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self.list, self.remove_selected)  # Mac의 delete 키
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

    def passwords(self) -> dict[Path, str]:
        items = (self.list.item(i) for i in range(self.list.count()))
        return {it.data(PATH_ROLE): it.data(PASSWORD_ROLE) for it in items if it.data(PASSWORD_ROLE) is not None}

    def choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "PDF 선택", self._last_dir(), "PDF 파일 (*.pdf)")
        self.add_paths([Path(f) for f in files])

    def add_paths(self, paths: list[Path]) -> None:
        errors: list[str] = []
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for path in expand_pdf_paths(paths):
                try:
                    opened = self._count_pages(path)
                except PdfError as e:
                    errors.append(str(e))
                    continue
                if opened is None:  # 암호 입력을 취소했다
                    continue
                pages, password = opened
                lock = "🔒 " if password is not None else ""
                item = QListWidgetItem(f"{lock}{display_name(path)}   ({pages}쪽)")
                item.setData(PATH_ROLE, path)
                item.setData(PAGES_ROLE, pages)
                item.setData(PASSWORD_ROLE, password)
                item.setToolTip(str(path))
                self.list.addItem(item)
        finally:
            QApplication.restoreOverrideCursor()
        if errors:
            QMessageBox.warning(self, APP_NAME, "다음 파일은 추가하지 못했습니다:\n\n" + "\n".join(errors))

    def _count_pages(self, path: Path) -> tuple[int, str | None] | None:
        """페이지 수와, 암호가 걸려 있었다면 사용자가 입력한 암호를 돌려준다. 암호 입력을 취소하면 None."""
        password: str | None = None
        while True:
            try:
                return page_count(path, password), password
            except PasswordError:
                password = self._ask_password(path, wrong=password is not None)
                if password is None:
                    return None

    def _ask_password(self, path: Path, wrong: bool) -> str | None:
        label = f"'{display_name(path)}' 파일은 암호가 걸려 있습니다.\n암호를 입력하세요."
        if wrong:
            label = "암호가 틀렸습니다. 다시 입력하세요.\n\n" + label
        QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)  # 파일 읽는 동안의 대기 커서를 잠시 푼다
        try:
            password, ok = QInputDialog.getText(self, APP_NAME, label, QLineEdit.EchoMode.Password)
        finally:
            QApplication.restoreOverrideCursor()
        return password if ok else None

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
        self._thread = MergeThread(inputs, output, self.passwords())
        self._thread.progress.connect(self._on_progress)
        self._thread.succeeded.connect(self._on_success)
        self._thread.failed.connect(self._on_failure)
        self._thread.finished.connect(lambda: self._set_busy(False))
        self._thread.start()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(done)

    def _on_success(self, output: Path, pages: int) -> None:
        self.list.clear()  # 다음 병합을 바로 시작할 수 있게 목록을 비운다 (원본 파일은 그대로)
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(f"병합을 마쳤습니다. (총 {pages}쪽)\n\n{output}")
        open_file = box.addButton("파일 열기", QMessageBox.ButtonRole.AcceptRole)
        open_dir = box.addButton("폴더 열기", QMessageBox.ButtonRole.ActionRole)
        box.addButton("닫기", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_file:
            open_path(output)
        elif box.clickedButton() is open_dir:
            open_path(output.parent)

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

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        # macOS는 앱 아이콘에 끌어다 놓은 파일을 파일마다 FileOpen 이벤트로 보낸다.
        # 한 번에 들어온 파일들을 모았다가 한꺼번에 추가한다.
        if isinstance(event, QFileOpenEvent):
            if not self._opened_files:
                QTimer.singleShot(0, self._add_opened_files)
            self._opened_files.append(Path(event.file()))
            return True
        return super().eventFilter(obj, event)

    def _add_opened_files(self) -> None:
        paths, self._opened_files = self._opened_files, []
        self.add_paths(paths)

    def closeEvent(self, event) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.wait()
        super().closeEvent(event)


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    window = MainWindow()
    app.installEventFilter(window)
    window.show()
    # 명령줄이나 exe 아이콘에 끌어다 놓은 파일도 바로 추가한다.
    if len(sys.argv) > 1:
        window.add_paths([Path(a) for a in sys.argv[1:]])
    return app.exec()
