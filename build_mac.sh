#!/usr/bin/env bash
# build_mac.sh — SSM Tunnel macOS (.app + .dmg) 빌드 스크립트
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
info() { echo -e "${GREEN}▶${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
err()  { echo -e "${RED}✗${NC}  $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="SSM Tunnel"
VERSION=$(cat VERSION 2>/dev/null | tr -d '[:space:]' || echo "1.0.0")
DMG_NAME="SSM-Tunnel-v${VERSION}.dmg"

echo ""
echo -e "${BOLD}=====================================${NC}"
echo -e "${BOLD}   SSM Tunnel  macOS 빌드${NC}"
echo -e "${BOLD}=====================================${NC}"
echo ""

# ── 1. Python 확인 ────────────────────────────────────────────────────────────
info "Python 확인..."
PYTHON=$(command -v python3 2>/dev/null) || err "python3가 없습니다.  →  brew install python3"
PY_VER=$("$PYTHON" --version 2>&1)
ok "$PY_VER  ($PYTHON)"

# ── 2. PyQt5 확인/설치 ────────────────────────────────────────────────────────
info "PyQt5 확인..."
if ! "$PYTHON" -c "from PyQt5.QtWidgets import QApplication" 2>/dev/null; then
    warn "PyQt5 없음 — pip 설치 중..."
    pip3 install --quiet PyQt5
fi
ok "PyQt5 OK"

# ── 3. PyInstaller 확인/설치 ─────────────────────────────────────────────────
info "PyInstaller 확인..."
if ! "$PYTHON" -m PyInstaller --version &>/dev/null; then
    warn "PyInstaller 없음 — pip 설치 중..."
    pip3 install --quiet pyinstaller
fi
PI_VER=$("$PYTHON" -m PyInstaller --version 2>&1)
ok "PyInstaller $PI_VER"

# ── 4. 아이콘 생성 ────────────────────────────────────────────────────────────
info "아이콘 생성..."
if [[ -f "icon.icns" ]]; then
    ok "icon.icns 이미 존재 (재사용 — 다시 만들려면 icon.icns 삭제 후 재실행)"
else
    "$PYTHON" make_icon.py
    ok "icon.icns 생성됨"
fi

# ── 5. 이전 빌드 정리 ─────────────────────────────────────────────────────────
info "이전 빌드 정리..."
rm -rf build "dist"
ok "정리 완료"

# ── 6. PyInstaller 빌드 ───────────────────────────────────────────────────────
info "'${APP_NAME}.app' 빌드 중..."
"$PYTHON" -m PyInstaller SSM_Tunnel.spec --noconfirm
ok "빌드 완료 →  dist/${APP_NAME}.app"

# ── 6.5. Ad-hoc 코드서명 (Gatekeeper 경고 완화) ───────────────────────────────
info "Ad-hoc 코드서명 중..."
if command -v codesign &>/dev/null; then
    codesign --force --deep --sign - "dist/${APP_NAME}.app" 2>&1 | grep -v "replacing existing signature" || true
    ok "Ad-hoc 서명 완료 (Apple Developer 인증서 없이 서명)"
else
    warn "codesign 없음 — Xcode Command Line Tools 설치 필요: xcode-select --install"
fi

# ── 7. DMG 패키징 ─────────────────────────────────────────────────────────────
info "DMG 생성 중..."
rm -f "$DMG_NAME"

# .app만 담을 스테이징 폴더 (dist/ 안의 PyInstaller 내부 디렉토리 제외)
STAGING=$(mktemp -d)
cp -r "dist/${APP_NAME}.app" "$STAGING/"

if command -v create-dmg &>/dev/null; then
    # create-dmg: 예쁜 배경, Applications 링크 포함
    create-dmg \
        --volname "$APP_NAME" \
        --window-pos 200 140 \
        --window-size 560 400 \
        --icon-size 128 \
        --icon "${APP_NAME}.app" 145 200 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 415 200 \
        --no-internet-enable \
        "$DMG_NAME" \
        "$STAGING/"
else
    # create-dmg 없으면 hdiutil 기본 DMG
    warn "create-dmg 없음 — hdiutil로 기본 DMG 생성"
    warn "더 예쁜 DMG를 원하면:  brew install create-dmg  후 재실행"
    hdiutil create \
        -volname "$APP_NAME" \
        -srcfolder "$STAGING" \
        -ov -format UDZO \
        "$DMG_NAME"
fi

rm -rf "$STAGING"

DMG_SIZE=$(du -sh "$DMG_NAME" | cut -f1)
ok "DMG 생성 완료:  $DMG_NAME  ($DMG_SIZE)"

# ── 8. ZIP 생성 (자동 업데이트용) ─────────────────────────────────────────────
info "자동 업데이트용 ZIP 생성 중..."
ZIP_NAME="SSM-Tunnel-v${VERSION}-app.zip"
rm -f "$ZIP_NAME"
ditto -c -k --keepParent "dist/${APP_NAME}.app" "$ZIP_NAME"
ZIP_SIZE=$(du -sh "$ZIP_NAME" | cut -f1)
ok "ZIP 생성 완료:  $ZIP_NAME  ($ZIP_SIZE)"

# ── 완료 안내 ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}=====================================${NC}"
echo -e "${GREEN}✓  빌드 성공!${NC}  →  ${BOLD}${DMG_NAME}${NC}"
echo -e "${BOLD}=====================================${NC}"
echo ""
echo -e "${BOLD}[동료에게 보낼 내용]${NC}"
echo ""
echo "  1. ${DMG_NAME} 파일 전송 (Slack / Google Drive / AirDrop)"
echo ""
echo "  2. 동료 PC에서 사전 설치 (한 번만):"
echo "       brew install awscli"
echo "       brew install --cask session-manager-plugin"
echo "       aws configure sso  # SSO 프로파일 설정"
echo ""
echo "  3. DMG 열고 앱을 Applications 폴더로 드래그"
echo ""
echo "  4. 첫 실행 시 Gatekeeper 차단되면 Terminal에서 아래 명령 실행:"
echo "       xattr -cr \"/Applications/SSM Tunnel.app\""
echo ""
