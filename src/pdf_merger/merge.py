"""PDF 읽기/병합 로직 (GUI와 독립적)."""

import os
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError


class PdfError(Exception):
    """사용자에게 그대로 보여줄 수 있는 PDF 관련 오류."""


def open_pdf(path: Path) -> PdfReader:
    """PDF를 열어 검증한다. 열 수 없으면 PdfError를 던진다."""
    try:
        reader = PdfReader(path)
    except FileNotFoundError:
        raise PdfError(f"파일을 찾을 수 없습니다: {path.name}") from None
    except (PdfReadError, OSError, ValueError) as e:
        raise PdfError(f"PDF를 읽을 수 없습니다: {path.name} ({e})") from None

    # 빈 암호로 열리는 PDF(편집 제한만 걸린 경우)는 그대로 병합할 수 있다.
    if reader.is_encrypted and not reader.decrypt(""):
        raise PdfError(f"암호가 걸린 PDF는 병합할 수 없습니다: {path.name}")
    return reader


def page_count(path: Path) -> int:
    return len(open_pdf(path).pages)


def merge_pdfs(
    inputs: Sequence[Path],
    output: Path,
    on_progress: Callable[[int, int], None] | None = None,
) -> int:
    """inputs를 순서대로 합쳐 output에 저장하고 총 페이지 수를 돌려준다."""
    if not inputs:
        raise PdfError("병합할 PDF가 없습니다.")

    output = output.resolve()
    if any(p.resolve() == output for p in inputs):
        raise PdfError("원본 PDF 중 하나를 저장 파일로 지정할 수 없습니다.")

    writer = PdfWriter()
    for i, path in enumerate(inputs, start=1):
        writer.append(open_pdf(path))
        if on_progress:
            on_progress(i, len(inputs))

    # 임시 파일에 먼저 쓴 뒤 교체해서, 실패해도 기존 파일이 깨지지 않게 한다.
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(suffix=".pdf", dir=output.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            writer.write(f)
        tmp.replace(output)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        raise PdfError(
            f"저장할 수 없습니다. '{output.name}' 파일이 다른 프로그램에서 열려 있는지 확인하세요."
        ) from None
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    return len(writer.pages)
