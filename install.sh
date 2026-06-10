#!/usr/bin/env bash
# install.sh — ssm-tunnel-gui 설치 스크립트 (Ubuntu)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_FILE="$SCRIPT_DIR/ssm_tunnel_gui.py"
DESKTOP_DIR="${HOME}/.local/share/applications"
BIN_DIR="${HOME}/.local/bin"

echo "=== SSM Tunnel GUI 설치 ==="

# 1. 의존성 확인 및 설치
echo "[1/4] 의존성 확인..."

if ! command -v python3 &>/dev/null; then
    echo "오류: python3이 없습니다."
    exit 1
fi

PYTHON=$(command -v python3)

# PyQt5 설치 (시스템 패키지 우선)
if ! "$PYTHON" -c "from PyQt5.QtWidgets import QApplication" 2>/dev/null; then
    echo "  PyQt5 설치 중..."
    if command -v apt &>/dev/null; then
        sudo apt install -y python3-pyqt5
    else
        pip3 install --user PyQt5
    fi
fi

echo "  의존성 확인 완료"

# 2. AWS CLI 확인
echo "[2/4] AWS CLI 확인..."
if ! command -v aws &>/dev/null; then
    echo "  경고: AWS CLI가 설치되지 않았습니다."
    echo "  설치: curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o awscliv2.zip"
    echo "         unzip awscliv2.zip && sudo ./aws/install"
else
    echo "  AWS CLI: $(aws --version 2>&1)"
fi

# 3. 실행 파일 링크 생성
echo "[3/4] 실행 파일 설정..."
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/ssm-tunnel-gui" <<EOF
#!/usr/bin/env bash
exec "$PYTHON" "$APP_FILE" "\$@"
EOF
chmod +x "$BIN_DIR/ssm-tunnel-gui"
echo "  실행 파일: $BIN_DIR/ssm-tunnel-gui"

# 4. 데스크탑 런처 생성
echo "[4/4] 데스크탑 런처 생성..."
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_DIR/ssm-tunnel.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=SSM Tunnel
Comment=AWS SSM port-forwarding with auto-reconnect
Exec=$PYTHON $APP_FILE
Icon=network-transmit-receive
Categories=Network;Utility;
Terminal=false
StartupNotify=true
EOF

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
echo "  데스크탑 파일: $DESKTOP_DIR/ssm-tunnel.desktop"

# PATH 안내
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "  PATH에 $BIN_DIR 추가가 필요합니다:"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
fi

echo ""
echo "=== 설치 완료 ==="
echo "  터미널 실행: ssm-tunnel-gui"
echo "  앱 메뉴에서 'SSM Tunnel'로 검색"
