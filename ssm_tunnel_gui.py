#!/usr/bin/env python3
"""SSM Tunnel GUI — multi-profile, AWS SSM port-forwarding with auto-reconnect.

Layout
------
Top    : AWS 계정 스트립 — SSO 프로파일별 인증 상태 + 로그인 (연결과 독립)
Middle : 연결 목록 (좌) + 연결 설정 편집 (우)
Bottom : 통합 로그
"""

import sys, os, json, subprocess, time, configparser, uuid, shutil
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFormLayout,
    QGroupBox, QSystemTrayIcon, QMenu, QAction, QMessageBox,
    QFrame, QComboBox, QScrollArea, QSplitter, QInputDialog, QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QPainter, QPixmap, QColor, QBrush, QPalette, QIntValidator

# ─── 버전 ─────────────────────────────────────────────────────────────────────
def _read_version() -> str:
    try:
        # .app 번들 내부: Contents/MacOS/executable → Contents/Resources/VERSION
        for parent in Path(sys.executable).parents:
            if parent.suffix == ".app":
                return (parent / "Contents" / "Resources" / "VERSION").read_text().strip()
    except Exception:
        pass
    try:
        return (Path(__file__).parent / "VERSION").read_text().strip()
    except Exception:
        return "0.0.0"

APP_VERSION  = _read_version()
GITHUB_REPO  = "ralpioxxcs/ssm-tunnel-helper"

# ─── AWS CLI 경로 ─────────────────────────────────────────────────────────────
# GUI 앱은 Finder/Dock 실행 시 쉘 PATH를 상속하지 않으므로 직접 탐색
def _find_aws() -> str:
    extra = "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin"
    path  = f"{extra}:{os.environ.get('PATH', '')}"
    return shutil.which("aws", path=path) or "aws"

AWS_CLI = _find_aws()
MACOS   = sys.platform == "darwin"

def _brew_env(base: Optional[dict] = None) -> dict:
    """subprocess용 환경변수 — macOS GUI 앱은 쉘 PATH를 상속하지 않아
    session-manager-plugin 등 Homebrew 바이너리를 못 찾으므로 직접 주입."""
    env = (base if base is not None else os.environ).copy()
    if MACOS:
        extra = "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin"
        env["PATH"] = f"{extra}:{env.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin')}"
    return env

def _is_dark() -> bool:
    """현재 시스템이 다크 모드인지 반환."""
    if not MACOS:
        return False
    app = QApplication.instance()
    return app is not None and app.palette().color(QPalette.Window).lightness() < 128

# ─── Paths ────────────────────────────────────────────────────────────────────
if sys.platform == "win32":
    _base      = Path(os.environ.get("APPDATA", Path.home()))
    CONFIG_DIR = _base / "ssm-tunnel"
    LOG_DIR    = _base / "ssm-tunnel" / "logs"
else:
    CONFIG_DIR = Path.home() / ".config" / "ssm-tunnel"
    LOG_DIR    = Path.home() / ".local" / "log"
CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_FILE    = LOG_DIR / "ssm-tunnel-gui.log"

# ─── Constants ────────────────────────────────────────────────────────────────
REGIONS = [
    "ap-northeast-2", "ap-northeast-1", "ap-southeast-1", "ap-southeast-2",
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-central-1", "sa-east-1",
]
STATUS = {
    "disconnected": ("#9E9E9E", "연결 안됨"),
    "connecting":   ("#FFC107", "연결 중..."),
    "connected":    ("#4CAF50", "연결됨"),
    "error":        ("#F44336", "오류"),
    "expired":      ("#FF7043", "토큰 만료"),
}
CRED_STATUS = {
    "ok":       ("#4CAF50", "유효"),
    "expired":  ("#FF7043", "만료됨"),
    "unknown":  ("#9E9E9E", "—"),
    "checking": ("#FFC107", "확인 중"),
}
CHECK_INTERVAL       = 10
TOKEN_CHECK_INTERVAL = 60


# ─── macOS 스타일시트 ──────────────────────────────────────────────────────────
def _macos_stylesheet(dark: bool = False) -> str:
    if dark:
        win_bg      = "#1c1c1e"
        text        = "#ffffff"
        text2       = "#8e8e93"
        border      = "#3a3a3c"
        input_bg    = "#2c2c2e"
        input_bd    = "#48484a"
        focus_bd    = "#0a84ff"
        blue        = "#0a84ff"
        btn_bg      = "#3a3a3c"
        btn_hov     = "#48484a"
        btn_prs     = "#545458"
        btn_dis_bg  = "#2c2c2e"
        btn_dis_tx  = "#636366"
        log_bg      = "#2c2c2e"
        log_bd      = "#3a3a3c"
        scroll_h    = "#636366"
        dlg_bg      = "#1c1c1e"
        list_bg     = "#2c2c2e"
        list_bd     = "#3a3a3c"
        destr_hov   = "#3d1210"
        destr_prs   = "#4d1614"
        icon_hov_bg = "#3a3a3c"
        icon_hov_tx = "#ffffff"
        pri_hov     = "#0077ed"
        pri_prs     = "#006bc7"
        pri_dis     = "#1c4a6e"
    else:
        win_bg      = "#f2f2f7"
        text        = "#1d1d1f"
        text2       = "#8e8e93"
        border      = "#d2d2d7"
        input_bg    = "#ffffff"
        input_bd    = "#c5c5c7"
        focus_bd    = "#0071e3"
        blue        = "#0071e3"
        btn_bg      = "#e8e8ed"
        btn_hov     = "#d8d8dd"
        btn_prs     = "#c8c8cd"
        btn_dis_bg  = "#f0f0f3"
        btn_dis_tx  = "#aeaeb2"
        log_bg      = "#ffffff"
        log_bd      = "#e5e5ea"
        scroll_h    = "#c7c7cc"
        dlg_bg      = "#f2f2f7"
        list_bg     = "#ffffff"
        list_bd     = "#d2d2d7"
        destr_hov   = "#fff0ef"
        destr_prs   = "#ffe0de"
        icon_hov_bg = "#e8e8ed"
        icon_hov_tx = "#3c3c43"
        pri_hov     = "#0066cc"
        pri_prs     = "#005ab5"
        pri_dis     = "#99c8f5"

    return f"""
        QGroupBox {{
            background: transparent;
            border: none;
            border-top: 1px solid {border};
            margin-top: 24px;
            padding-top: 6px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            top: 4px; left: 0;
            padding: 0 4px;
            font-size: 11px;
            font-weight: bold;
            color: {text2};
        }}

        QDialog {{ background: {dlg_bg}; }}
        QAbstractItemView {{
            background: {list_bg};
            color: {text};
            border: 1px solid {list_bd};
            border-radius: 6px;
        }}
        QAbstractItemView::item {{ padding: 4px 8px; }}
        QAbstractItemView::item:selected {{ background: {blue}; color: white; }}

        QLineEdit {{
            background: {input_bg};
            border: 1px solid {input_bd};
            border-radius: 6px;
            padding: 4px 8px;
            color: {text};
            selection-background-color: {blue};
        }}
        QLineEdit:focus {{ border-color: {focus_bd}; }}
        QLineEdit:disabled {{ background: {btn_dis_bg}; color: {btn_dis_tx}; border-color: {border}; }}

        QComboBox {{
            background: {input_bg};
            border: 1px solid {input_bd};
            border-radius: 6px;
            padding: 4px 8px;
            color: {text};
        }}
        QComboBox:focus {{ border-color: {focus_bd}; }}
        QComboBox:disabled {{ background: {btn_dis_bg}; color: {btn_dis_tx}; }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background: {list_bg};
            border: 1px solid {list_bd};
            selection-background-color: {blue};
            selection-color: white;
        }}

        QPushButton {{
            background: {btn_bg};
            color: {text};
            border: none;
            border-radius: 6px;
            padding: 5px 10px;
            font-size: 13px;
        }}
        QPushButton:hover   {{ background: {btn_hov}; }}
        QPushButton:pressed {{ background: {btn_prs}; }}
        QPushButton:disabled {{ background: {btn_dis_bg}; color: {btn_dis_tx}; }}

        QPushButton[role="primary"] {{
            background: {blue}; color: white; font-weight: bold;
        }}
        QPushButton[role="primary"]:hover   {{ background: {pri_hov}; }}
        QPushButton[role="primary"]:pressed {{ background: {pri_prs}; }}
        QPushButton[role="primary"]:disabled {{ background: {pri_dis}; color: white; }}

        QPushButton[role="destructive"] {{
            background: transparent; color: #ff3b30;
        }}
        QPushButton[role="destructive"]:hover   {{ background: {destr_hov}; }}
        QPushButton[role="destructive"]:pressed {{ background: {destr_prs}; }}

        QPushButton[role="connected"] {{
            background: #ff3b30; color: white; font-weight: bold;
        }}
        QPushButton[role="connected"]:hover {{ background: #e62e24; }}

        QPushButton[role="connecting"] {{
            background: #ff9500; color: white; font-weight: bold;
        }}

        QPushButton[role="icon"] {{
            background: transparent; color: {text2};
            border: none; padding: 2px; font-size: 11px;
        }}
        QPushButton[role="icon"]:hover {{ color: {icon_hov_tx}; background: {icon_hov_bg}; border-radius: 4px; }}

        QTextEdit {{
            background: {log_bg};
            border: 1px solid {log_bd};
            border-radius: 8px;
            color: {text};
        }}

        QSplitter::handle:horizontal {{ background: {border}; width: 1px; }}

        QScrollBar:vertical {{
            border: none; background: transparent; width: 8px; margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {scroll_h}; border-radius: 4px; min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical  {{ background: none; }}
        QScrollBar:horizontal {{
            border: none; background: transparent; height: 8px; margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {scroll_h}; border-radius: 4px; min-width: 20px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    """


# ─── Data model ───────────────────────────────────────────────────────────────
@dataclass
class Profile:
    id:          str
    name:        str  = "새 연결"
    auth_mode:   str  = "sso"      # "sso" | "manual"
    aws_profile: str  = ""
    target:      str  = ""
    region:      str  = "ap-northeast-2"
    remote_host: str  = "localhost"
    remote_port: int  = 5432
    local_port:  int  = 5432

    @classmethod
    def new(cls) -> "Profile":
        return cls(id=str(uuid.uuid4()))

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─── Helpers ──────────────────────────────────────────────────────────────────
def dot_pixmap(color: str, size: int = 12) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor(color))); p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return px

def parse_aws_profiles() -> list:
    cfg_path = Path.home() / ".aws" / "config"
    if not cfg_path.exists():
        return []
    cp = configparser.ConfigParser()
    cp.read(cfg_path)
    out = []
    for s in cp.sections():
        if s == "default":          out.append("default")
        elif s.startswith("profile "): out.append(s[8:])
    return out

def is_sso_profile(profile: str) -> bool:
    cfg_path = Path.home() / ".aws" / "config"
    if not cfg_path.exists(): return False
    cp = configparser.ConfigParser()
    cp.read(cfg_path)
    sec = "default" if profile == "default" else f"profile {profile}"
    return sec in cp and ("sso_start_url" in cp[sec] or "sso_session" in cp[sec])

def check_credentials(profile: Optional[str], region: str,
                      env: Optional[dict] = None) -> bool:
    cmd = [AWS_CLI, "sts", "get-caller-identity", "--region", region]
    if profile: cmd += ["--profile", profile]
    try:
        return subprocess.run(cmd, env=_brew_env(env), capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


# ─── 업데이트 체크 스레드 ────────────────────────────────────────────────────────
class UpdateCheckThread(QThread):
    update_available = pyqtSignal(str, str, str)   # version, html_url, zip_url
    check_error      = pyqtSignal(str)             # error message

    def __init__(self, current: str, repo: str):
        super().__init__()
        self.current = current
        self.repo    = repo

    def run(self):
        if not self.repo:
            return
        try:
            import urllib.request, ssl
            # repo의 VERSION 파일을 직접 읽음 — API/리다이렉트 불필요
            url = f"https://raw.githubusercontent.com/{self.repo}/main/VERSION"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
                tag = resp.read().decode().strip()
            rel_url = f"https://github.com/{self.repo}/releases/tag/v{tag}"
            zip_url = (f"https://github.com/{self.repo}/releases/download/"
                       f"v{tag}/SSM-Tunnel-v{tag}-app.zip")
            if tag and self._newer(tag):
                self.update_available.emit(tag, rel_url, zip_url)
        except Exception as e:
            self.check_error.emit(str(e))

    def _newer(self, remote: str) -> bool:
        try:
            def t(v): return tuple(int(x) for x in v.split("."))
            return t(remote) > t(self.current)
        except Exception:
            return False


# ─── 자동 업데이트 다운로드 스레드 ────────────────────────────────────────────
class AutoUpdateThread(QThread):
    progress = pyqtSignal(int)   # 0-100
    done     = pyqtSignal(str)   # 추출된 .app 경로
    error    = pyqtSignal(str)

    def __init__(self, zip_url: str):
        super().__init__()
        self.zip_url = zip_url
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        import urllib.request, tempfile, ssl, subprocess
        try:
            ctx = ssl.create_default_context()
            req = urllib.request.Request(self.zip_url,
                                         headers={"User-Agent": "SSM-Tunnel-App"})
            tmp_zip = tempfile.mktemp(suffix=".zip")
            with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
                total      = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(tmp_zip, "wb") as f:
                    while not self._cancel:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress.emit(int(downloaded * 100 / total))
            if self._cancel:
                os.unlink(tmp_zip)
                return
            self.progress.emit(100)
            tmp_dir = tempfile.mkdtemp(prefix="ssm-update-")
            # ditto -x -k: macOS 확장 속성(코드서명) 보존하며 ZIP 해제
            subprocess.run(["ditto", "-x", "-k", tmp_zip, tmp_dir], check=True)
            os.unlink(tmp_zip)
            app_path = next(
                (os.path.join(tmp_dir, e) for e in os.listdir(tmp_dir) if e.endswith(".app")),
                None
            )
            if not app_path:
                self.error.emit("ZIP에서 .app을 찾을 수 없습니다.")
                return
            self.done.emit(app_path)
        except Exception as e:
            self.error.emit(str(e))


# ─── Credential check thread (safe Qt signal, no QTimer from non-main thread) ─
class CredCheckThread(QThread):
    done = pyqtSignal(str, bool)   # aws_profile, ok

    def __init__(self, aws_profile: str, region: str):
        super().__init__()
        self.aws_profile = aws_profile
        self.region      = region

    def run(self):
        ok = check_credentials(self.aws_profile, self.region)
        self.done.emit(self.aws_profile, ok)


# ─── SSO login thread ─────────────────────────────────────────────────────────
class SSOLoginThread(QThread):
    done = pyqtSignal(bool, str)   # success, message

    def __init__(self, aws_profile: str, region: str):
        super().__init__()
        self.aws_profile = aws_profile
        self.region      = region

    def run(self):
        try:
            r = subprocess.run(
                [AWS_CLI, "sso", "login", "--profile", self.aws_profile],
                env=_brew_env(), capture_output=True, timeout=300, text=True,
            )
        except subprocess.TimeoutExpired:
            self.done.emit(False, "타임아웃"); return
        except FileNotFoundError:
            self.done.emit(False, "aws CLI를 찾을 수 없습니다"); return
        except Exception as e:
            self.done.emit(False, str(e)); return

        if r.returncode != 0:
            self.done.emit(False, r.stderr.strip() or "로그인 실패"); return

        ok = check_credentials(self.aws_profile, self.region)
        self.done.emit(ok, "로그인 성공" if ok else "자격증명 확인 실패")


# ─── Tunnel thread ────────────────────────────────────────────────────────────
class TunnelThread(QThread):
    log_signal     = pyqtSignal(str, str)   # (profile_name, message)
    status_signal  = pyqtSignal(str)
    relogin_needed = pyqtSignal(str)        # aws_profile that expired

    def __init__(self, profile: Profile, manual_creds: Optional[dict] = None):
        super().__init__()
        self.profile      = profile
        self.manual_creds = manual_creds
        self._running     = True
        self._proc: Optional[subprocess.Popen] = None

    def stop(self):
        self._running = False
        self._kill()

    def run(self):
        p   = self.profile
        aws = p.aws_profile if p.auth_mode == "sso" else None
        env = _brew_env()   # 항상 Homebrew PATH 포함 (session-manager-plugin 탐색용)
        if p.auth_mode == "manual" and self.manual_creds:
            env.update({
                "AWS_ACCESS_KEY_ID":     self.manual_creds["access_key"],
                "AWS_SECRET_ACCESS_KEY": self.manual_creds["secret_key"],
                "AWS_SESSION_TOKEN":     self.manual_creds["session_token"],
                "AWS_DEFAULT_REGION":    p.region,
            })

        self._log(f"인증: {'SSO (' + aws + ')' if aws else '수동 입력'}")
        self._log(f"터널: localhost:{p.local_port} → {p.remote_host}:{p.remote_port}")

        if not check_credentials(aws, p.region, env):
            self._log("자격증명이 유효하지 않습니다.")
            if aws: self.relogin_needed.emit(aws)
            self.status_signal.emit("error"); return

        target = p.target.strip()
        if not target.startswith("i-"):
            self._log(f"인스턴스 조회: Name={target}")
            self.status_signal.emit("connecting")
            target = self._resolve(target, p.region, aws, env)
            if not target:
                self._log("실행 중인 인스턴스를 찾을 수 없습니다.")
                self.status_signal.emit("error"); return
            self._log(f"인스턴스 ID: {target}")

        self._log(f"대상: {target}")
        last_check = time.time()
        self.status_signal.emit("connecting")

        while self._running:
            now = time.time()
            if now - last_check >= TOKEN_CHECK_INTERVAL:
                if not check_credentials(aws, p.region, env):
                    self._log("자격증명 만료.")
                    if aws: self.relogin_needed.emit(aws)
                    self.status_signal.emit("expired"); break
                last_check = now

            if self._proc is None or self._proc.poll() is not None:
                if self._proc is not None:
                    self._log("세션 종료 — 재연결 중...")
                    self.status_signal.emit("connecting")
                self._proc = self._start(target, p.region, aws, env)
                if self._proc:
                    self._log(f"SSM 세션 시작 (PID {self._proc.pid})")
                    self.status_signal.emit("connected")
                else:
                    self.status_signal.emit("error")
                    for _ in range(15):
                        if not self._running: break
                        time.sleep(1)
                    continue
            time.sleep(CHECK_INTERVAL)

        self._kill()
        self.status_signal.emit("disconnected")

    def _resolve(self, name, region, profile, env) -> Optional[str]:
        cmd = [
            AWS_CLI, "ec2", "describe-instances",
            "--filters", f"Name=tag:Name,Values={name}",
            "Name=instance-state-name,Values=running",
            "--query", "Reservations[0].Instances[0].InstanceId",
            "--output", "text", "--region", region,
        ]
        if profile: cmd += ["--profile", profile]
        try:
            r = subprocess.run(cmd, env=env, capture_output=True, timeout=15)
            result = r.stdout.decode().strip()
            if r.returncode == 0 and result and result != "None":
                return result
            self._log(f"조회 오류: {r.stderr.decode().strip()}")
        except Exception as e:
            self._log(f"인스턴스 조회 실패: {e}")
        return None

    def _start(self, target, region, profile, env) -> Optional[subprocess.Popen]:
        p = self.profile
        params = json.dumps({
            "host": [p.remote_host],
            "portNumber": [str(p.remote_port)],
            "localPortNumber": [str(p.local_port)],
        })
        cmd = [
            AWS_CLI, "ssm", "start-session",
            "--target", target,
            "--document-name", "AWS-StartPortForwardingSessionToRemoteHost",
            "--parameters", params,
            "--region", region,
        ]
        if profile: cmd += ["--profile", profile]
        self._log("SSM 세션 시작 중...")
        try:
            proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(2)
            if proc.poll() is not None:
                err = (proc.stderr.read().decode().strip() if proc.stderr else "") or "(출력 없음)"
                self._log(f"SSM 즉시 종료: {err}")
                return None
            return proc
        except FileNotFoundError:
            self._log("오류: aws CLI를 찾을 수 없습니다.")
        except Exception as e:
            self._log(f"SSM 시작 실패: {e}")
        return None

    def _kill(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try: self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired: self._proc.kill()
        self._proc = None

    def _log(self, msg: str):
        ts   = datetime.now().strftime("%H:%M:%S")
        self.log_signal.emit(self.profile.name, f"[{ts}] {msg}")
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a") as f:
                f.write(f"[{self.profile.name}] [{ts}] {msg}\n")
        except Exception:
            pass


# ─── AWS 계정 카드 (상단 스트립 내 개별 위젯) ───────────────────────────────
class AccountCard(QFrame):
    """One AWS profile — shows cred status, SSO login, and remove button."""
    login_clicked   = pyqtSignal(str)   # aws_profile
    check_clicked   = pyqtSignal(str)   # aws_profile
    remove_clicked  = pyqtSignal(str)   # aws_profile

    def _frame_style(self, highlight: bool = False) -> str:
        if highlight:
            bg = "#3a2200" if _is_dark() else "#fff8ee"
        else:
            bg = "#2c2c2e" if _is_dark() else "#ffffff"
        return f"QFrame {{ background:{bg}; border-radius:8px; }}"

    def refresh_style(self):
        self.setStyleSheet(self._frame_style())

    def __init__(self, aws_profile: str):
        super().__init__()
        self.aws_profile = aws_profile
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(60)
        self.setMinimumWidth(220)
        if MACOS:
            self.setStyleSheet(self._frame_style())

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 6, 8, 6)
        h.setSpacing(8)

        info = QVBoxLayout()
        info.setSpacing(2)
        lbl = QLabel(aws_profile)
        f = QFont(); f.setBold(True); lbl.setFont(f)

        status_row = QHBoxLayout(); status_row.setSpacing(4)
        self.dot   = QLabel()
        self.dot.setPixmap(dot_pixmap(CRED_STATUS["unknown"][0]))
        self.state = QLabel(CRED_STATUS["unknown"][1])
        self.state.setStyleSheet("font-size: 11px; color: #8e8e93;" if MACOS else "font-size: 11px; color: gray;")
        status_row.addWidget(self.dot); status_row.addWidget(self.state); status_row.addStretch()
        info.addWidget(lbl); info.addLayout(status_row)

        btn_col = QVBoxLayout(); btn_col.setSpacing(3)
        self.login_btn = QPushButton("SSO 로그인")
        self.login_btn.setFixedWidth(96)
        if MACOS: self.login_btn.setProperty("role", "primary")
        self.login_btn.clicked.connect(lambda: self.login_clicked.emit(self.aws_profile))
        self.check_btn = QPushButton("상태 확인")
        self.check_btn.setFixedWidth(96)
        self.check_btn.clicked.connect(lambda: self.check_clicked.emit(self.aws_profile))
        btn_col.addWidget(self.login_btn); btn_col.addWidget(self.check_btn)

        rm_btn = QPushButton("✕")
        rm_btn.setFixedSize(20, 20)
        if MACOS:
            rm_btn.setProperty("role", "icon")
        else:
            rm_btn.setStyleSheet("color: gray; border: none; font-size: 11px;")
        rm_btn.clicked.connect(lambda: self.remove_clicked.emit(self.aws_profile))

        h.addLayout(info, 1); h.addLayout(btn_col)
        h.addWidget(rm_btn, alignment=Qt.AlignTop)

    def set_status(self, key: str):
        color, label = CRED_STATUS.get(key, CRED_STATUS["unknown"])
        self.dot.setPixmap(dot_pixmap(color))
        self.state.setText(label)
        is_sso = is_sso_profile(self.aws_profile)
        self.login_btn.setVisible(is_sso)
        busy = key == "checking"
        self.login_btn.setEnabled(not busy)
        self.check_btn.setEnabled(not busy)
        self.check_btn.setText("확인 중..." if busy else "상태 확인")

    def highlight(self, on: bool):
        if MACOS:
            self.setStyleSheet(self._frame_style(highlight=on))
        else:
            self.setStyleSheet("background: #FFF3E0; border-radius:4px;" if on else "")


# ─── AWS 계정 스트립 (상단 전체) ──────────────────────────────────────────────
class AccountStrip(QGroupBox):
    """Top bar: manages AWS credentials independently from tunnel connections.
    Accounts are added manually — ~/.aws/config is NOT auto-scanned on startup.
    """
    login_done      = pyqtSignal(str, bool, str)  # aws_profile, success, message
    account_added   = pyqtSignal(str)             # aws_profile
    account_removed = pyqtSignal(str)             # aws_profile

    def __init__(self):
        super().__init__("AWS 계정")
        self._cards:       dict = {}   # aws_profile → AccountCard
        self._sso_threads: dict = {}
        self._chk_threads: dict = {}

        outer = QHBoxLayout(self)
        outer.setContentsMargins(6, 4, 6, 4); outer.setSpacing(6)

        # "+ 추가" button + hint label (left of scroll area)
        add_col = QVBoxLayout(); add_col.setSpacing(3)
        add_btn = QPushButton("+ 계정 추가")
        add_btn.setFixedWidth(88)
        add_btn.clicked.connect(self._on_add_clicked)
        hint = QLabel("~/.aws/config\n에서 불러옵니다")
        hint.setStyleSheet("font-size: 9px; color: #8e8e93;")
        hint.setAlignment(Qt.AlignHCenter)
        add_col.addWidget(add_btn)
        add_col.addWidget(hint)
        outer.addLayout(add_col)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setFixedHeight(70)

        self._inner = QWidget()
        self._layout = QHBoxLayout(self._inner)
        self._layout.setContentsMargins(0, 0, 0, 0); self._layout.setSpacing(6)
        self._layout.addStretch()
        scroll.setWidget(self._inner)
        outer.addWidget(scroll, 1)

    # ── Public API ────────────────────────────────────────────────────────────
    def add_account(self, aws_profile: str):
        """Manually add an account card (idempotent)."""
        if not aws_profile or aws_profile in self._cards:
            return
        card = AccountCard(aws_profile)
        card.login_clicked.connect(self._on_login)
        card.check_clicked.connect(self._on_check)
        card.remove_clicked.connect(self._on_remove)
        self._cards[aws_profile] = card
        self._layout.insertWidget(self._layout.count() - 1, card)
        self.account_added.emit(aws_profile)

    def account_names(self) -> list:
        return list(self._cards.keys())

    def set_status(self, aws_profile: str, key: str):
        if aws_profile in self._cards:
            self._cards[aws_profile].set_status(key)

    def highlight(self, aws_profile: str, on: bool):
        if aws_profile in self._cards:
            self._cards[aws_profile].highlight(on)

    # ── Internal ──────────────────────────────────────────────────────────────
    def _on_add_clicked(self):
        suggestions = parse_aws_profiles()
        if not suggestions:
            QMessageBox.information(
                self, "AWS 계정 추가",
                "~/.aws/config 에 프로파일이 없습니다.\n"
                "먼저 터미널에서 'aws configure sso' 를 실행하세요.",
            )
            return
        profile, ok = QInputDialog.getItem(
            self, "AWS 계정 추가", "추가할 AWS 프로파일을 선택하세요:",
            suggestions, 0, False,
        )
        if ok and profile.strip():
            self.add_account(profile.strip())

    def _on_check(self, aws_profile: str):
        self.set_status(aws_profile, "checking")
        th = CredCheckThread(aws_profile, "ap-northeast-2")
        th.done.connect(lambda ap, ok: self.set_status(ap, "ok" if ok else "expired"))
        th.start()
        self._chk_threads[aws_profile] = th   # keep reference

    def _on_login(self, aws_profile: str):
        self.set_status(aws_profile, "checking")
        th = SSOLoginThread(aws_profile, "ap-northeast-2")
        th.done.connect(lambda ok, msg, ap=aws_profile: self._on_login_done(ap, ok, msg))
        th.start()
        self._sso_threads[aws_profile] = th

    def _on_login_done(self, aws_profile: str, success: bool, message: str):
        self.set_status(aws_profile, "ok" if success else "expired")
        self.login_done.emit(aws_profile, success, message)

    def _on_remove(self, aws_profile: str):
        card = self._cards.pop(aws_profile, None)
        if card:
            self._layout.removeWidget(card); card.deleteLater()
        self.account_removed.emit(aws_profile)


# ─── 연결 카드 (좌측 목록) ────────────────────────────────────────────────────
class ProfileCard(QFrame):
    selected        = pyqtSignal(str)
    connect_clicked = pyqtSignal(str)

    def _frame_style(self, selected: bool = False) -> str:
        if selected:
            bg = "#0a2d4a" if _is_dark() else "#dceeff"
        else:
            bg = "#2c2c2e" if _is_dark() else "#ffffff"
        return f"QFrame {{ background:{bg}; border-radius:8px; }}"

    def refresh_style(self):
        self.setStyleSheet(self._frame_style(self._is_selected))

    def __init__(self, profile: Profile):
        super().__init__()
        self.profile_id  = profile.id
        self._is_selected = False
        self.setFrameShape(QFrame.NoFrame)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(58)
        if MACOS:
            self.setStyleSheet(self._frame_style())

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 6, 10, 6); h.setSpacing(8)

        self.dot = QLabel()
        self.dot.setFixedWidth(12)
        self.dot.setPixmap(dot_pixmap(STATUS["disconnected"][0]))

        info = QVBoxLayout(); info.setSpacing(1)
        self.lbl_name = QLabel(profile.name)
        f = QFont(); f.setBold(True); self.lbl_name.setFont(f)
        self.lbl_name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_port = QLabel()
        self.lbl_port.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.lbl_port.setStyleSheet("color: #8e8e93; font-size: 11px;")
        self.lbl_port.setTextFormat(Qt.PlainText)
        # Elide long text so the button always stays visible
        self._raw_port_str = ""
        info.addWidget(self.lbl_name); info.addWidget(self.lbl_port)

        self.btn = QPushButton("연결")
        self.btn.setFixedWidth(54)
        if MACOS:
            self.btn.setProperty("role", "primary")
        else:
            self.btn.setStyleSheet("font-weight: bold;")
        self.btn.clicked.connect(lambda: self.connect_clicked.emit(self.profile_id))

        h.addWidget(self.dot)
        h.addLayout(info, 1)   # info takes all remaining space
        h.addWidget(self.btn)  # button always has fixed room on the right

        self._apply_port_str(profile)

    def _apply_port_str(self, p: Profile):
        self._raw_port_str = f":{p.local_port} → {p.remote_host}:{p.remote_port}"
        self.lbl_port.setToolTip(self._raw_port_str)   # full text on hover
        self._elide_port()

    def _elide_port(self):
        fm = self.lbl_port.fontMetrics()
        available = self.lbl_port.width() if self.lbl_port.width() > 10 else 160
        elided = fm.elidedText(self._raw_port_str, Qt.ElideMiddle, available)
        self.lbl_port.setText(elided)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide_port()

    def mousePressEvent(self, _): self.selected.emit(self.profile_id)

    def set_selected(self, on: bool):
        self._is_selected = on
        if MACOS:
            self.setStyleSheet(self._frame_style(on))
        else:
            self.setStyleSheet("background:#E3F2FD; border-radius:4px;" if on else "")

    def update_profile(self, p: Profile):
        self.lbl_name.setText(p.name)
        self._apply_port_str(p)

    def update_status(self, key: str):
        color, _ = STATUS.get(key, STATUS["disconnected"])
        self.dot.setPixmap(dot_pixmap(color))
        if MACOS:
            role = "connected" if key == "connected" else "connecting" if key == "connecting" else "primary"
            text = "해제"    if key == "connected"  else "..." if key == "connecting" else "연결"
            self.btn.setText(text)
            self.btn.setProperty("role", role)
            self.btn.style().unpolish(self.btn)
            self.btn.style().polish(self.btn)
        else:
            if key == "connected":
                self.btn.setText("해제"); self.btn.setStyleSheet("font-weight:bold; color:#c62828;")
            elif key == "connecting":
                self.btn.setText("..."); self.btn.setStyleSheet("font-weight:bold; color:#e65100;")
            else:
                self.btn.setText("연결"); self.btn.setStyleSheet("font-weight:bold;")


# ─── 연결 설정 편집 패널 (우측) ───────────────────────────────────────────────
class EditPanel(QWidget):
    """Connection settings only. Auth is managed by AccountStrip."""
    saved   = pyqtSignal(object)   # Profile
    deleted = pyqtSignal(str)      # profile_id

    def __init__(self, aws_profiles: list):
        super().__init__()
        self._profile_id: Optional[str] = None
        self._aws_profiles = aws_profiles
        self._build()
        self.set_profile(None)

    def _title_style(self) -> str:
        color = "#f2f2f7" if _is_dark() else "#1d1d1f"
        return f"font-size: 15px; font-weight: 600; color: {color};"

    def refresh_style(self):
        if MACOS:
            self.w_title.setStyleSheet(self._title_style())

    def refresh_profiles(self, aws_profiles: list):
        self._aws_profiles = aws_profiles
        current = self.w_aws_profile.currentText()
        self.w_aws_profile.clear()
        self.w_aws_profile.addItems(["(없음 — 직접 입력)"] + aws_profiles)
        idx = self.w_aws_profile.findText(current)
        if idx >= 0: self.w_aws_profile.setCurrentIndex(idx)

    def _build(self):
        vbox = QVBoxLayout(self)
        if MACOS:
            vbox.setContentsMargins(16, 14, 16, 12); vbox.setSpacing(10)
        else:
            vbox.setContentsMargins(12, 8, 8, 8); vbox.setSpacing(8)

        self.w_title = QLabel("연결 설정")
        if MACOS:
            self.w_title.setStyleSheet(self._title_style())
        else:
            f = QFont(); f.setBold(True); f.setPointSize(11); self.w_title.setFont(f)
        vbox.addWidget(self.w_title)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        if MACOS:
            form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            form.setHorizontalSpacing(10)
            form.setVerticalSpacing(10)
        else:
            form.setSpacing(6)

        # Name
        self.w_name = QLineEdit(placeholderText="dev-db")
        form.addRow("이름", self.w_name)

        # AWS profile selector
        self.w_aws_profile = QComboBox()
        self.w_aws_profile.addItems(["(없음 — 직접 입력)"] + self._aws_profiles)
        self.w_aws_profile.currentIndexChanged.connect(self._on_profile_sel_changed)
        form.addRow("AWS 계정", self.w_aws_profile)

        # Manual credentials (shown only when "직접 입력" selected)
        self.w_manual = QWidget()
        mf = QFormLayout(self.w_manual)
        mf.setContentsMargins(0, 0, 0, 0)
        if MACOS:
            mf.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            mf.setHorizontalSpacing(12)
            mf.setVerticalSpacing(6)
        else:
            mf.setSpacing(4)
        self.w_access_key    = QLineEdit(placeholderText="ASIA...")
        self.w_secret_key    = self._secret("••••••••••")
        self.w_session_token = self._secret("IQoJ...")
        mf.addRow("Access Key ID",     self.w_access_key)
        mf.addRow("Secret Access Key", self._reveal(self.w_secret_key))
        mf.addRow("Session Token",     self._reveal(self.w_session_token))
        form.addRow("", self.w_manual)
        self.w_manual.hide()

        # Connection settings
        self.w_target = QLineEdit(placeholderText="i-0abc1234... 또는 EC2 Name 태그")
        form.addRow("Target", self.w_target)

        self.w_region = QComboBox(); self.w_region.addItems(REGIONS)
        form.addRow("Region", self.w_region)

        self.w_remote_host = QLineEdit(
            placeholderText="rds.cluster-xxx.ap-northeast-2.rds.amazonaws.com")
        form.addRow("Remote Host", self.w_remote_host)

        pw = QWidget(); ph = QHBoxLayout(pw); ph.setContentsMargins(0,0,0,0); ph.setSpacing(8)
        _port_v = QIntValidator(1, 65535)
        self.w_remote_port = QLineEdit("5432"); self.w_remote_port.setValidator(_port_v); self.w_remote_port.setFixedWidth(64)
        self.w_local_port  = QLineEdit("5432"); self.w_local_port.setValidator(_port_v);  self.w_local_port.setFixedWidth(64)
        ph.addWidget(QLabel("Remote:")); ph.addWidget(self.w_remote_port)
        ph.addWidget(QLabel("→   Local:")); ph.addWidget(self.w_local_port); ph.addStretch()
        form.addRow("Port", pw)

        vbox.addLayout(form)

        # 구분선
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        if MACOS:
            sep.setStyleSheet("background:#d2d2d7; border:none; max-height:1px;")
            sep.setMaximumHeight(1)
        else:
            sep.setFrameShadow(QFrame.Sunken)
        vbox.addWidget(sep)

        btn_row = QHBoxLayout()
        self.w_del = QPushButton("삭제")
        if MACOS:
            self.w_del.setProperty("role", "destructive")
        else:
            self.w_del.setStyleSheet("color:#c62828;")
        self.w_del.clicked.connect(self._on_delete)
        self.w_save = QPushButton("저장")
        if MACOS:
            self.w_save.setProperty("role", "primary")
        else:
            self.w_save.setStyleSheet("font-weight:bold;")
        self.w_save.clicked.connect(self._on_save)
        btn_row.addWidget(self.w_del); btn_row.addStretch(); btn_row.addWidget(self.w_save)
        vbox.addLayout(btn_row)
        vbox.addStretch()

    @staticmethod
    def _secret(ph: str) -> QLineEdit:
        f = QLineEdit(placeholderText=ph); f.setEchoMode(QLineEdit.Password); return f

    @staticmethod
    def _reveal(field: QLineEdit) -> QWidget:
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0,0,0,0); h.setSpacing(4)
        h.addWidget(field)
        btn = QPushButton("표시"); btn.setFixedWidth(46); btn.setCheckable(True)
        btn.toggled.connect(lambda c, f=field, b=btn: (
            f.setEchoMode(QLineEdit.Normal if c else QLineEdit.Password),
            b.setText("숨김" if c else "표시")))
        h.addWidget(btn); return w

    def _on_profile_sel_changed(self, idx: int):
        self.w_manual.setVisible(idx == 0)

    # ── Public API ────────────────────────────────────────────────────────────
    def set_profile(self, profile: Optional[Profile]):
        enabled = profile is not None
        for w in (self.w_name, self.w_aws_profile, self.w_target, self.w_region,
                  self.w_remote_host, self.w_remote_port, self.w_local_port,
                  self.w_save, self.w_del,
                  self.w_access_key, self.w_secret_key, self.w_session_token):
            w.setEnabled(enabled)
        if not enabled:
            self._profile_id = None
            self.w_name.clear()
            self.w_name.setPlaceholderText("← 연결을 선택하거나 추가하세요")
            return

        self._profile_id = profile.id
        self.w_name.setText(profile.name)

        if profile.auth_mode == "sso" and profile.aws_profile:
            idx = self.w_aws_profile.findText(profile.aws_profile)
            self.w_aws_profile.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self.w_aws_profile.setCurrentIndex(0)

        self.w_target.setText(profile.target)
        ri = self.w_region.findText(profile.region)
        self.w_region.setCurrentIndex(ri if ri >= 0 else 0)
        self.w_remote_host.setText(profile.remote_host)
        self.w_remote_port.setText(str(profile.remote_port))
        self.w_local_port.setText(str(profile.local_port))

    def get_manual_creds(self) -> dict:
        return {
            "access_key":    self.w_access_key.text().strip(),
            "secret_key":    self.w_secret_key.text().strip(),
            "session_token": self.w_session_token.text().strip(),
        }

    def lock(self, locked: bool):
        for w in (self.w_name, self.w_aws_profile, self.w_target, self.w_region,
                  self.w_remote_host, self.w_remote_port, self.w_local_port, self.w_save):
            w.setEnabled(not locked)

    def _on_save(self):
        if not self._profile_id: return
        idx      = self.w_aws_profile.currentIndex()
        aws_prof = self.w_aws_profile.currentText() if idx > 0 else ""
        p = Profile(
            id          = self._profile_id,
            name        = self.w_name.text().strip() or "새 연결",
            auth_mode   = "sso" if idx > 0 else "manual",
            aws_profile = aws_prof,
            target      = self.w_target.text().strip(),
            region      = self.w_region.currentText().strip() or "ap-northeast-2",
            remote_host = (lambda h: h[5:] if h.startswith("host=") else h)(self.w_remote_host.text().strip()) or "localhost",
            remote_port = int(self.w_remote_port.text() or "5432"),
            local_port  = int(self.w_local_port.text() or "5432"),
        )
        self.saved.emit(p)
        self.w_save.setText("✓  저장됨")
        QTimer.singleShot(1500, lambda: self.w_save.setText("저장"))

    def _on_delete(self):
        if not self._profile_id: return
        if QMessageBox.question(self, "삭제 확인", "이 연결을 삭제할까요?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.deleted.emit(self._profile_id)


# ─── Main window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._profiles: list          = []
        self._threads:  dict          = {}   # profile_id → TunnelThread
        self._cards:    dict          = {}   # profile_id → ProfileCard
        self._selected: Optional[str] = None
        self._tray:     Optional[QSystemTrayIcon] = None
        self._tray_warned = False

        self._update_thread:      Optional[UpdateCheckThread] = None
        self._auto_update_thread: Optional[AutoUpdateThread]  = None
        self._manual_check_found: bool = False

        self._build_ui()
        self._build_tray()
        self._load_config()
        QTimer.singleShot(4000, self._start_update_check)

    # ── Log collapse helpers ──────────────────────────────────────────────────
    def _refresh_log_hdr(self):
        dark = _is_dark()
        bd   = "#3a3a3c" if dark else "#d2d2d7"
        txt  = "#ffffff" if dark else "#1d1d1f"
        txt2 = "#8e8e93"
        self._log_hdr.setStyleSheet(
            f"QFrame {{ border:none; border-top:1px solid {bd}; background:transparent; }}"
            f"QLabel {{ color:{txt}; background:transparent; border:none; }}"
            f"QPushButton {{ color:{txt2}; background:transparent; border:none; "
            f"padding:2px 6px; font-size:12px; }} "
            f"QPushButton:hover {{ color:{txt}; }}"
        )
        self._log_chevron.setText("▼" if self._log_expanded else "▶")
        if self._log_unread > 0 and not self._log_expanded:
            self._log_badge.setText(f"  +{self._log_unread}개")
            self._log_badge.setStyleSheet(
                f"color:{'#ff9f0a' if dark else '#f59e0b'}; font-size:11px; font-weight:bold;")
            self._log_badge.show()
        else:
            self._log_badge.hide()

    def _toggle_log(self):
        self._log_expanded = not self._log_expanded
        self._log_body.setVisible(self._log_expanded)
        if self._log_expanded:
            self._log_unread = 0
        self._refresh_log_hdr()

    def _log_clear(self):
        self.w_log.clear()
        self._log_unread = 0
        self._refresh_log_hdr()

    # ── Dark mode helpers ─────────────────────────────────────────────────────
    @staticmethod
    def _apply_root_bg(widget: QWidget):
        p = QPalette()
        p.setColor(QPalette.Window, QColor("#1c1c1e" if _is_dark() else "#f2f2f7"))
        widget.setAutoFillBackground(True)
        widget.setPalette(p)

    @staticmethod
    def _sep_style() -> str:
        color = "#3a3a3c" if _is_dark() else "#d2d2d7"
        return f"background:{color}; border:none;"

    def _on_mode_changed(self):
        dark = _is_dark()
        QApplication.instance().setStyleSheet(_macos_stylesheet(dark))
        self._apply_root_bg(self.centralWidget())
        self.vsep.setStyleSheet(self._sep_style())
        for card in self._cards.values():
            card.refresh_style()
        for card in self.account_strip._cards.values():
            card.refresh_style()
        self.edit_panel.refresh_style()
        if not self.update_banner.isHidden():
            self.update_banner.setStyleSheet(self._banner_style())
        self._refresh_log_hdr()

    @staticmethod
    def _banner_style() -> str:
        if _is_dark():
            return ("QFrame { background:#2d2000; border:1px solid #7c5a00; border-radius:6px; }"
                    "QLabel { color:#fcd34d; background:transparent; border:none; }"
                    "QPushButton { color:#fcd34d; background:#3d2e00; border:1px solid #7c5a00;"
                    " border-radius:4px; padding:2px 8px; }"
                    "QPushButton:hover { background:#4d3a00; }")
        return ("QFrame { background:#fffbeb; border:1px solid #f59e0b; border-radius:6px; }"
                "QLabel { color:#92400e; background:transparent; border:none; }"
                "QPushButton { color:#92400e; background:#fef3c7; border:1px solid #f59e0b;"
                " border-radius:4px; padding:2px 8px; }"
                "QPushButton:hover { background:#fde68a; }")

    def _make_update_banner(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(self._banner_style())
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        self._banner_lbl = QLabel()
        lay.addWidget(self._banner_lbl, 1)

        self._banner_action = QPushButton()
        self._banner_action.setFixedHeight(24)
        self._banner_action.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self._banner_action)

        self._banner_close = QPushButton("✕")
        self._banner_close.setFixedSize(24, 24)
        self._banner_close.setCursor(Qt.PointingHandCursor)
        self._banner_close.clicked.connect(self._banner_dismiss)
        lay.addWidget(self._banner_close)

        return frame

    def _banner_dismiss(self):
        if self._auto_update_thread and self._auto_update_thread.isRunning():
            self._auto_update_thread.cancel()
        self.update_banner.hide()

    # state: "notify_auto" | "notify_web" | "downloading" | "ready" | "error"
    def _banner_set_state(self, state: str, **kw):
        lbl = self._banner_lbl
        btn = self._banner_action
        cls = self._banner_close

        # disconnect all previous action connections
        try:
            btn.clicked.disconnect()
        except Exception:
            pass

        if state == "notify_auto":
            lbl.setText(f"⬆  v{kw['version']} 업데이트 있음")
            btn.setText("자동 설치"); btn.show()
            cls.setText("✕"); cls.show()
            btn.clicked.connect(lambda: self._start_download(kw["zip_url"]))

        elif state == "notify_web":
            lbl.setText(f"⬆  v{kw['version']} 업데이트 있음")
            import webbrowser
            btn.setText("다운로드"); btn.show()
            cls.setText("✕"); cls.show()
            btn.clicked.connect(lambda: webbrowser.open(kw["html_url"]))

        elif state == "downloading":
            lbl.setText("다운로드 중...  0%")
            btn.setText("취소"); btn.show()
            cls.setText("✕"); cls.show()
            btn.clicked.connect(self._banner_dismiss)

        elif state == "ready":
            lbl.setText("✓  설치 준비 완료 — 앱을 재시작하면 업데이트가 적용됩니다.")
            btn.setText("지금 재시작"); btn.show()
            cls.setText("나중에"); cls.show()
            btn.clicked.connect(lambda: self._do_restart(kw["app_path"]))

        elif state == "error":
            lbl.setText(f"업데이트 오류: {kw['msg']}")
            btn.hide()
            cls.setText("✕"); cls.show()

        self.update_banner.show()
        self.update_banner.setStyleSheet(self._banner_style())

    def _start_download(self, zip_url: str):
        self._banner_set_state("downloading")
        self._auto_update_thread = AutoUpdateThread(zip_url)
        self._auto_update_thread.progress.connect(self._on_dl_progress)
        self._auto_update_thread.done.connect(self._on_dl_done)
        self._auto_update_thread.error.connect(
            lambda msg: self._banner_set_state("error", msg=msg))
        self._auto_update_thread.start()

    def _on_dl_progress(self, pct: int):
        self._banner_lbl.setText(f"다운로드 중...  {pct}%")

    def _on_dl_done(self, app_path: str):
        self._banner_set_state("ready", app_path=app_path)

    def _do_restart(self, new_app_path: str):
        import tempfile, subprocess
        cur = self._find_app_bundle()
        script = (
            "#!/bin/bash\n"
            "sleep 1\n"
            f'rm -rf "{cur}"\n'
            f'ditto "{new_app_path}" "{cur}"\n'
            f'xattr -rd com.apple.quarantine "{cur}" 2>/dev/null || true\n'
            f'codesign --force --deep --sign - "{cur}" 2>/dev/null || true\n'
            f'open "{cur}"\n'
            f'rm -rf "{os.path.dirname(new_app_path)}"\n'
        )
        tmp = tempfile.mktemp(suffix=".sh")
        with open(tmp, "w") as f:
            f.write(script)
        os.chmod(tmp, 0o755)
        subprocess.Popen(["bash", tmp])
        QApplication.quit()

    @staticmethod
    def _find_app_bundle() -> str:
        p = Path(sys.executable)
        for parent in p.parents:
            if parent.suffix == ".app":
                return str(parent)
        return str(p.parents[2])   # .../SSM Tunnel.app/Contents/MacOS → parents[2]

    def _start_update_check(self):
        if not GITHUB_REPO:
            return
        self._update_thread = UpdateCheckThread(APP_VERSION, GITHUB_REPO)
        self._update_thread.update_available.connect(self._on_update_available)
        self._update_thread.check_error.connect(
            lambda e: self._log("업데이트", f"버전 체크 실패: {e}"))
        self._update_thread.start()

    def _check_update_manual(self):
        if not GITHUB_REPO:
            QMessageBox.information(self, "업데이트 확인", "GITHUB_REPO가 설정되지 않았습니다.")
            return
        if self._update_thread and self._update_thread.isRunning():
            return
        # 즉각적인 피드백: 배너에 "확인 중" 표시
        self._banner_lbl.setText("업데이트 확인 중...")
        try: self._banner_action.clicked.disconnect()
        except Exception: pass
        self._banner_action.hide()
        self._banner_close.setText("✕")
        self.update_banner.show()
        self.update_banner.setStyleSheet(self._banner_style())
        self.show(); self.activateWindow()

        self._manual_check_found = False
        self._update_thread = UpdateCheckThread(APP_VERSION, GITHUB_REPO)
        self._update_thread.update_available.connect(self._on_update_available)
        self._update_thread.check_error.connect(self._on_check_error)
        self._update_thread.finished.connect(self._on_manual_check_done)
        self._update_thread.start()

    def _on_check_error(self, msg: str):
        self._manual_check_found = True   # "최신 버전" 메시지 방지
        self._banner_set_state("error", msg=msg)

    def _on_manual_check_done(self):
        if not self._manual_check_found:
            # 최신 버전 — 배너에 표시 후 3초 뒤 숨김
            self._banner_lbl.setText(f"✓  최신 버전입니다. (v{APP_VERSION})")
            try: self._banner_action.clicked.disconnect()
            except Exception: pass
            self._banner_action.hide()
            self._banner_close.setText("✕")
            self.update_banner.show()
            self.update_banner.setStyleSheet(self._banner_style())
            QTimer.singleShot(3000, self.update_banner.hide)

    def _on_update_available(self, version: str, html_url: str, zip_url: str):
        self._manual_check_found = True
        if zip_url:
            self._banner_set_state("notify_auto", version=version, zip_url=zip_url)
        else:
            self._banner_set_state("notify_web", version=version, html_url=html_url)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setWindowTitle("SSM Tunnel")
        self.setMinimumSize(720, 620)

        root = QWidget()
        self.setCentralWidget(root)
        if MACOS:
            self._apply_root_bg(root)
        vbox = QVBoxLayout(root)
        if MACOS:
            vbox.setContentsMargins(12, 10, 12, 10); vbox.setSpacing(8)
        else:
            vbox.setContentsMargins(8, 8, 8, 8); vbox.setSpacing(6)

        # ── Top: AWS account strip ────────────────────────────────────────
        self.account_strip = AccountStrip()
        self.account_strip.login_done.connect(
            lambda ap, ok, msg: self._log("SSO", f"[{ap}] {msg}"))
        self.account_strip.account_added.connect(self._on_account_changed)
        self.account_strip.account_removed.connect(self._on_account_changed)
        vbox.addWidget(self.account_strip)

        # ── Update banner (hidden until update found) ─────────────────────
        self.update_banner = self._make_update_banner()
        vbox.addWidget(self.update_banner)
        self.update_banner.hide()

        # ── Middle: 고정폭 목록 + 편집 패널 ──────────────────────────────
        mid = QWidget()
        mid_lay = QHBoxLayout(mid)
        mid_lay.setContentsMargins(0, 0, 0, 0)
        mid_lay.setSpacing(0)

        # Left: connection list (고정폭)
        left = QWidget()
        left.setFixedWidth(240)
        lv = QVBoxLayout(left)
        if MACOS:
            lv.setContentsMargins(0, 0, 0, 0); lv.setSpacing(6)
        else:
            lv.setContentsMargins(0, 0, 4, 0); lv.setSpacing(4)

        hdr = QHBoxLayout()
        lbl = QLabel("연결 목록")
        f = QFont(); f.setBold(True); f.setPointSize(11); lbl.setFont(f)
        add_btn = QPushButton("+ 추가"); add_btn.setFixedWidth(60)
        add_btn.clicked.connect(self._add_profile)
        hdr.addWidget(lbl); hdr.addStretch(); hdr.addWidget(add_btn)
        lv.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        self.w_list_ctn = QWidget()
        self.w_list_lay = QVBoxLayout(self.w_list_ctn)
        self.w_list_lay.setContentsMargins(0, 0, 0, 0)
        self.w_list_lay.setSpacing(4)
        self.w_list_lay.addStretch()
        scroll.setWidget(self.w_list_ctn)
        lv.addWidget(scroll)

        # 세로 구분선
        self.vsep = QFrame()
        self.vsep.setFrameShape(QFrame.VLine)
        self.vsep.setFixedWidth(1)
        if MACOS:
            self.vsep.setStyleSheet(self._sep_style())
        else:
            self.vsep.setFrameShadow(QFrame.Sunken)
        vsep = self.vsep

        # Right: edit panel
        self.edit_panel = EditPanel([])
        self.edit_panel.saved.connect(self._on_saved)
        self.edit_panel.deleted.connect(self._on_deleted)

        mid_lay.addWidget(left)
        mid_lay.addWidget(vsep)
        mid_lay.addWidget(self.edit_panel, 1)
        vbox.addWidget(mid, 1)

        # ── Bottom: collapsible log ───────────────────────────────────────
        self._log_expanded = False
        self._log_unread   = 0

        log_wrap = QWidget()
        log_vbox = QVBoxLayout(log_wrap)
        log_vbox.setContentsMargins(0, 0, 0, 0)
        log_vbox.setSpacing(0)

        # Header row (always visible, clickable)
        self._log_hdr = QFrame()
        self._log_hdr.setCursor(Qt.PointingHandCursor)
        hdr_lay = QHBoxLayout(self._log_hdr)
        hdr_lay.setContentsMargins(2, 5, 2, 5)
        hdr_lay.setSpacing(6)

        self._log_chevron = QLabel("▶")
        lbl_log = QLabel("로그")
        f = QFont(); f.setBold(True); f.setPointSize(11)
        lbl_log.setFont(f)

        self._log_badge = QLabel()
        self._log_badge.setFixedHeight(16)
        self._log_badge.hide()

        clr = QPushButton("지우기")
        clr.setFixedWidth(60)
        clr.setFixedHeight(24)
        clr.clicked.connect(self._log_clear)

        hdr_lay.addWidget(self._log_chevron)
        hdr_lay.addWidget(lbl_log)
        hdr_lay.addWidget(self._log_badge)
        hdr_lay.addStretch()
        hdr_lay.addWidget(clr)
        log_vbox.addWidget(self._log_hdr)
        self._log_hdr.mousePressEvent = lambda _: self._toggle_log()

        # Body (collapsed by default)
        self._log_body = QWidget()
        body_lay = QVBoxLayout(self._log_body)
        body_lay.setContentsMargins(0, 4, 0, 0)
        body_lay.setSpacing(0)
        mono = "Menlo" if MACOS else ("Courier New" if sys.platform == "win32" else "Monospace")
        self.w_log = QTextEdit()
        self.w_log.setReadOnly(True)
        self.w_log.setFont(QFont(mono, 9))
        self.w_log.setFixedHeight(150)
        body_lay.addWidget(self.w_log)
        self._log_body.hide()
        log_vbox.addWidget(self._log_body)

        self._refresh_log_hdr()
        vbox.addWidget(log_wrap)

    # ── Profile list helpers ──────────────────────────────────────────────────
    def _add_card(self, profile: Profile):
        card = ProfileCard(profile)
        card.selected.connect(self._on_card_selected)
        card.connect_clicked.connect(self._on_connect_clicked)
        self._cards[profile.id] = card
        self.w_list_lay.insertWidget(self.w_list_lay.count() - 1, card)

    def _remove_card(self, pid: str):
        card = self._cards.pop(pid, None)
        if card: self.w_list_lay.removeWidget(card); card.deleteLater()

    def _find(self, pid: str) -> Optional[Profile]:
        return next((p for p in self._profiles if p.id == pid), None)

    def _select(self, pid: str):
        if self._selected == pid: return
        if self._selected and self._selected in self._cards:
            self._cards[self._selected].set_selected(False)
        self._selected = pid
        if pid in self._cards: self._cards[pid].set_selected(True)
        p = self._find(pid)
        self.edit_panel.set_profile(p)
        if pid in self._threads and self._threads[pid].isRunning():
            self.edit_panel.lock(True)

    def _add_profile(self):
        p = Profile.new()
        self._profiles.append(p)
        self._add_card(p)
        self._select(p.id)
        self._save_config()

    # ── Slot: card events ─────────────────────────────────────────────────────
    def _on_card_selected(self, pid: str):
        self._select(pid)

    def _on_connect_clicked(self, pid: str):
        if pid in self._threads and self._threads[pid].isRunning():
            self._disconnect(pid)
        else:
            self._connect(pid)

    # ── Connection control ────────────────────────────────────────────────────
    def _connect(self, pid: str):
        p = self._find(pid)
        if not p: return

        manual_creds = None
        if p.auth_mode == "manual":
            if self._selected != pid: self._select(pid)
            creds = self.edit_panel.get_manual_creds()
            if not all(creds.values()):
                QMessageBox.warning(self, "자격증명 필요",
                    "직접 입력 모드에서는 Access Key, Secret Key, Session Token을 모두 입력하세요.")
                return
            manual_creds = creds

        th = TunnelThread(p, manual_creds)
        th.log_signal.connect(self._log)
        th.status_signal.connect(lambda s, _pid=pid: self._on_status(_pid, s))
        th.relogin_needed.connect(self._on_relogin_needed)
        th.start()
        self._threads[pid] = th
        if self._selected == pid: self.edit_panel.lock(True)

    def _disconnect(self, pid: str):
        th = self._threads.pop(pid, None)
        if th: th.stop(); th.wait(8000)
        card = self._cards.get(pid)
        if card: card.update_status("disconnected")
        if self._selected == pid: self.edit_panel.lock(False)

    def _on_account_changed(self, _: str = ""):
        """Sync EditPanel dropdown whenever accounts are added/removed."""
        self.edit_panel.refresh_profiles(self.account_strip.account_names())
        self._save_config()

    # ── Slot: edit panel events ───────────────────────────────────────────────
    def _on_saved(self, profile: Profile):
        idx = next((i for i, p in enumerate(self._profiles) if p.id == profile.id), None)
        if idx is not None: self._profiles[idx] = profile
        card = self._cards.get(profile.id)
        if card: card.update_profile(profile)
        self._save_config()

    def _on_deleted(self, pid: str):
        self._disconnect(pid)
        self._profiles = [p for p in self._profiles if p.id != pid]
        self._remove_card(pid)
        if self._selected == pid:
            self._selected = None; self.edit_panel.set_profile(None)
        self._save_config()

    # ── Status / log ──────────────────────────────────────────────────────────
    def _on_status(self, pid: str, key: str):
        card = self._cards.get(pid)
        if card: card.update_status(key)
        if key in ("error", "expired"):
            self._threads.pop(pid, None)
            if self._selected == pid: self.edit_panel.lock(False)
        n = sum(1 for t in self._threads.values() if t.isRunning())
        if self._tray:
            color = STATUS["connected"][0] if n else STATUS["disconnected"][0]
            self._tray.setIcon(QIcon(dot_pixmap(color, 16)))
            self._tray.setToolTip(f"SSM Tunnel — {n}개 연결 중" if n else "SSM Tunnel — 연결 안됨")

    def _on_relogin_needed(self, aws_profile: str):
        self._log("SSO", f"[{aws_profile}] 세션 만료 — 상단 계정 카드에서 SSO 로그인하세요.")
        self.account_strip.set_status(aws_profile, "expired")
        self.account_strip.highlight(aws_profile, True)
        if self._tray:
            self._tray.showMessage(
                "SSM Tunnel — 재로그인 필요",
                f"{aws_profile} 세션이 만료되었습니다.",
                QSystemTrayIcon.Warning, 5000)
        self.show(); self.activateWindow()

    def _log(self, profile_name: str, line: str):
        prefix = f"<b style='color:#1565C0'>[{profile_name}]</b>"
        self.w_log.append(f"{prefix} {line}")
        self.w_log.verticalScrollBar().setValue(self.w_log.verticalScrollBar().maximum())
        if not self._log_expanded:
            self._log_unread += 1
            self._refresh_log_hdr()

    # ── Config ────────────────────────────────────────────────────────────────
    def _load_config(self):
        try:
            if not CONFIG_FILE.exists(): return
            data = json.loads(CONFIG_FILE.read_text())
            # Restore manually added accounts (no auto-scan)
            for ap in data.get("accounts", []):
                self.account_strip.add_account(ap)
            # Restore tunnel connections
            for pd in data.get("profiles", []):
                p = Profile.from_dict(pd)
                self._profiles.append(p); self._add_card(p)
        except Exception:
            pass
        if not self._profiles: self._add_profile()

    def _save_config(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(json.dumps({
                "accounts": self.account_strip.account_names(),
                "profiles": [asdict(p) for p in self._profiles],
            }, indent=2, ensure_ascii=False))
        except Exception:
            pass

    # ── Tray ──────────────────────────────────────────────────────────────────
    def _build_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
        self._tray = QSystemTrayIcon(QIcon(dot_pixmap(STATUS["disconnected"][0], 16)), self)
        self._tray.setToolTip("SSM Tunnel")
        self._tray.activated.connect(
            lambda r: (self.show(), self.activateWindow()) if r == QSystemTrayIcon.Trigger and not self.isVisible()
            else self.hide() if r == QSystemTrayIcon.Trigger else None)
        menu = QMenu()
        menu.addAction("창 열기", lambda: (self.show(), self.activateWindow()))
        menu.addSeparator()
        menu.addAction("업데이트 확인", self._check_update_manual)
        menu.addSeparator()
        menu.addAction("종료", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.show()

    def closeEvent(self, event):
        if self._tray and self._tray.isVisible():
            if not self._tray_warned:
                self._tray.showMessage("SSM Tunnel",
                    "트레이에서 계속 실행 중입니다.", QSystemTrayIcon.Information, 3000)
                self._tray_warned = True
            self.hide(); event.ignore()
        else:
            self._quit()

    def _quit(self):
        for th in list(self._threads.values()): th.stop(); th.wait(3000)
        QApplication.quit()


# ─── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("SSM Tunnel")
    app.setQuitOnLastWindowClosed(False)
    if MACOS:
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        app.setStyleSheet(_macos_stylesheet(_is_dark()))
    win = MainWindow()
    if MACOS:
        app.paletteChanged.connect(lambda _: win._on_mode_changed())
    win.show()
    sys.exit(app.exec_())
