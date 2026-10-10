# PDF 병합기

여러 PDF를 순서대로 하나로 합쳐주는 작은 앱입니다. Windows와 macOS(Apple Silicon)에서 쓸 수 있습니다.

## 설치

[Releases](https://github.com/HoyeongJeon/pdf-merger/releases/latest)에서 내려받습니다.

- **Windows:** `PDF-Merger-windows.exe`를 받아 원하는 곳에 두고 실행합니다. 설치 과정은 없습니다.
- **macOS:** `PDF-Merger-macos.zip`을 받아 풀고 `PDF-Merger.app`을 응용 프로그램 폴더로 옮깁니다. M1 이후 Mac에서 동작합니다.

이 앱은 Apple·Microsoft 개발자 서명이 없어서 처음 실행할 때 경고가 뜹니다. 한 번만 넘기면 됩니다.

- **Windows** "Windows의 PC 보호" 창: **추가 정보** → **실행**
- **macOS** "확인할 수 없는 개발자" 창: 창을 닫고 **시스템 설정 → 개인정보 보호 및 보안**으로 가서 맨 아래의 **그래도 열기**를 누릅니다.
  "손상되었기 때문에 열 수 없습니다"라고 나오면 터미널에서 `xattr -cr /Applications/PDF-Merger.app`을 실행한 뒤 다시 엽니다.

## 사용법

- PDF 파일이나 폴더를 창에 끌어다 놓거나 **파일 추가**(Ctrl+O / ⌘O)로 추가합니다.
- 목록에서 끌거나 **▲/▼**(Ctrl+↑/↓ / ⌘↑/↓)로 순서를 바꿉니다. **이름순 정렬**은 `2.pdf`를 `10.pdf`보다 앞에 둡니다.
- **병합하기**를 누르고 저장 위치를 고릅니다. 병합이 끝나면 목록이 비워집니다.
- PDF 파일들을 앱 아이콘 위에 바로 끌어다 놓아도 됩니다.

암호가 걸린 PDF는 병합할 수 없습니다. 편집 제한만 걸린 PDF는 병합됩니다.

## 개발

필요한 것: [uv](https://docs.astral.sh/uv/) (Python 3.14는 uv가 알아서 설치합니다)

```sh
uv sync                      # 가상환경 + 의존성 설치
uv run pdf-merger            # 앱 실행
uv run pytest                # 테스트
uv run ruff format .         # 코드 정리
uv run ruff check .          # 린트
```

### 빌드

```sh
uv run pyinstaller --noconfirm PDF-Merger.spec
```

Windows에서는 `dist/PDF-Merger.exe`, macOS에서는 `dist/PDF-Merger.app`이 만들어집니다. 빌드 설정은 `PDF-Merger.spec` 한 파일에 있습니다.

### 배포

`v0.2.0`처럼 `v`로 시작하는 태그를 푸시하면 GitHub Actions가 Windows와 macOS에서 빌드해 Releases에 올립니다.

```sh
# pyproject.toml의 version을 올리고 커밋한 뒤
git tag v0.2.0
git push origin v0.2.0
```

### 아이콘

`src/pdf_merger/assets/`의 `icon.png`(앱 창) / `icon.ico`(Windows) / `icon.icns`(macOS)는
`scripts/make_icon.py`가 그린 것입니다. 모양을 바꾸려면 스크립트를 고치고 다시 실행합니다.

```sh
uv run python scripts/make_icon.py
```

## 구조

- `src/pdf_merger/merge.py`: PDF 열기/병합 로직 (pypdf)
- `src/pdf_merger/app.py`: GUI (PySide6)
- `tests/`: 병합 로직 테스트 + 화면 없이 도는 GUI 테스트
- `PDF-Merger.spec`: PyInstaller 빌드 설정
- `.github/workflows/build.yml`: 테스트·빌드·배포 자동화

## 라이선스

[MIT](LICENSE)
