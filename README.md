# PDF 병합기

여러 PDF를 순서대로 하나로 합쳐주는 Windows용 작은 앱입니다.

## 사용법

- PDF 파일이나 폴더를 창에 끌어다 놓거나 **파일 추가**(Ctrl+O)로 추가합니다.
- 목록에서 끌거나 **▲/▼**(Ctrl+↑/↓)로 순서를 바꿉니다. **이름순 정렬**은 `2.pdf`를 `10.pdf`보다 앞에 둡니다.
- **병합하기**를 누르고 저장 위치를 고릅니다.
- PDF 파일들을 `PDF-Merger.exe` 아이콘 위에 바로 끌어다 놓아도 됩니다.

암호가 걸린 PDF는 병합할 수 없습니다. 편집 제한만 걸린 PDF는 병합됩니다.

## 개발

필요한 것: [uv](https://docs.astral.sh/uv/) (Python 3.14는 uv가 알아서 설치합니다)

```powershell
uv sync                      # 가상환경 + 의존성 설치
uv run pdf-merger            # 앱 실행
uv run pytest                # 테스트
uv run ruff format .         # 코드 정리
uv run ruff check .          # 린트
```

### exe 빌드

```powershell
uv run pyinstaller --noconfirm --onefile --windowed --name PDF-Merger `
  --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml `
  --exclude-module PySide6.QtQuick --exclude-module PySide6.QtPdf `
  src/pdf_merger/__main__.py
```

결과물은 `dist\PDF-Merger.exe`입니다.

## 구조

- `src/pdf_merger/merge.py`: PDF 열기/병합 로직 (pypdf)
- `src/pdf_merger/app.py`: GUI (PySide6)
- `tests/`: 병합 로직 테스트 + 화면 없이 도는 GUI 테스트
