"""
Tool definitions untuk Kiro Telegram Agent.

Setiap tool punya:
  - JSON schema  (dikonsumsi Claude via parameter `tools`)
  - Implementasi Python (dieksekusi lokal saat Claude memanggilnya)

Cara menambah tool baru:
  1. Tambahkan schema ke TOOL_SCHEMAS
  2. Tulis fungsi Python di bawah
  3. Daftarkan ke TOOL_IMPLEMENTATIONS
"""

from __future__ import annotations

import ast
import json
import operator as op
import os
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _github_request(
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
) -> Any:
    """Minimal GitHub REST v3 helper tanpa dependensi tambahan."""
    token = token or os.environ.get("GITHUB_TOKEN", "")
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "kiro-telegram-bot/1.0",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code}: {err_body}") from exc


def _default_repo() -> tuple[str, str]:
    return os.environ.get("GITHUB_OWNER", ""), os.environ.get("GITHUB_REPO", "")


def _scripts_dir() -> Path:
    return (Path(__file__).parent.parent / "Kiro" / "scripts").resolve()


def _run_kiro_script(script: str, extra_env: dict) -> str:
    """Jalankan script TypeScript Kiro via npx tsx."""
    sd = _scripts_dir()
    if not sd.is_dir():
        return json.dumps({"error": f"Direktori Kiro/scripts tidak ditemukan di {sd}. Pastikan repo Kiro di-clone sejajar dengan telegram-bot/."})
    env = {**os.environ, **extra_env}
    try:
        result = subprocess.run(  # noqa: S603
            ["npx", "tsx", script],
            cwd=str(sd),
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        out = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
        return json.dumps({
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "output": out,
            "error": result.stderr[-1000:] if result.stderr else "",
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Script timeout setelah 120 detik."})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})



# ---------------------------------------------------------------------------
# Tool: get_current_time
# ---------------------------------------------------------------------------

def get_current_time(timezone_name: str = "UTC") -> str:
    now = datetime.now(timezone.utc)
    return json.dumps({
        "iso": now.isoformat(),
        "human": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "requested_timezone": timezone_name,
    })


# ---------------------------------------------------------------------------
# Tool: calculate  (aman via AST, tanpa eval)
# ---------------------------------------------------------------------------

_BINOPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.FloorDiv: op.floordiv,
    ast.Mod: op.mod, ast.Pow: op.pow,
}
_UNARYOPS = {ast.UAdd: op.pos, ast.USub: op.neg}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"Operasi tidak didukung: {ast.dump(node)}")


def calculate(expression: str) -> str:
    try:
        result = _eval_node(ast.parse(expression, mode="eval"))
        return json.dumps({"expression": expression, "result": result})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool: web_search  (DuckDuckGo, tanpa API key)
# ---------------------------------------------------------------------------

def web_search(query: str, max_results: int = 5) -> str:
    try:
        url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
        )
        req = urllib.request.Request(url, headers={"User-Agent": "kiro-telegram-bot/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        results: list[dict] = []
        if payload.get("AbstractText"):
            results.append({
                "title": payload.get("Heading", ""),
                "snippet": payload["AbstractText"],
                "url": payload.get("AbstractURL", ""),
            })
        for topic in payload.get("RelatedTopics", []):
            if len(results) >= max_results:
                break
            if "Text" in topic and "FirstURL" in topic:
                results.append({
                    "title": topic["Text"].split(" - ")[0],
                    "snippet": topic["Text"],
                    "url": topic["FirstURL"],
                })
        return json.dumps({"query": query, "results": results or [{"note": "Tidak ada hasil."}]})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"Pencarian gagal: {exc}"})



# ---------------------------------------------------------------------------
# Tool: read_code_file  (baca file kode dari workspace)
# ---------------------------------------------------------------------------

_WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(Path(__file__).parent.parent))).resolve()
_MAX_READ_BYTES = 20_000  # ~500 baris kode


def read_code_file(file_path: str, start_line: int = 1, end_line: int = 0) -> str:
    """Baca file kode dari workspace (sandbox untuk keamanan)."""
    try:
        target = (_WORKSPACE_ROOT / file_path).resolve()
        # Path traversal guard
        if _WORKSPACE_ROOT not in target.parents and target != _WORKSPACE_ROOT:
            return json.dumps({"error": "Path di luar workspace root."})
        if not target.exists():
            return json.dumps({"error": f"File tidak ditemukan: {file_path}"})
        if target.is_dir():
            # Tampilkan isi direktori
            entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
            listing = [
                f"{'[DIR] ' if e.is_dir() else '      '}{e.name}"
                for e in entries[:100]
            ]
            return json.dumps({
                "type": "directory",
                "path": str(target.relative_to(_WORKSPACE_ROOT)),
                "entries": listing,
                "truncated": len(list(target.iterdir())) > 100,
            })
        # Baca file
        raw = target.read_bytes()
        if len(raw) > _MAX_READ_BYTES and end_line == 0:
            content = raw[:_MAX_READ_BYTES].decode("utf-8", errors="replace")
            truncated = True
        else:
            lines = raw.decode("utf-8", errors="replace").splitlines()
            sl = max(1, start_line) - 1
            el = end_line if end_line > 0 else len(lines)
            content = "\n".join(lines[sl:el])
            truncated = end_line > 0 and end_line < len(lines)
        return json.dumps({
            "path": str(target.relative_to(_WORKSPACE_ROOT)),
            "size_bytes": target.stat().st_size,
            "content": content,
            "truncated": truncated,
        })
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool: write_code_file  (tulis/edit file kode di workspace)
# ---------------------------------------------------------------------------

def write_code_file(file_path: str, content: str, create_dirs: bool = True) -> str:
    """Tulis atau timpa file kode di workspace."""
    try:
        target = (_WORKSPACE_ROOT / file_path).resolve()
        if _WORKSPACE_ROOT not in target.parents and target != _WORKSPACE_ROOT:
            return json.dumps({"error": "Path di luar workspace root."})
        if create_dirs:
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return json.dumps({
            "success": True,
            "path": str(target.relative_to(_WORKSPACE_ROOT)),
            "size_bytes": target.stat().st_size,
        })
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool: patch_code_file  (replace teks tertentu dalam file)
# ---------------------------------------------------------------------------

def patch_code_file(file_path: str, old_str: str, new_str: str) -> str:
    """Ganti teks tertentu dalam file kode (seperti find-and-replace tepat)."""
    try:
        target = (_WORKSPACE_ROOT / file_path).resolve()
        if _WORKSPACE_ROOT not in target.parents and target != _WORKSPACE_ROOT:
            return json.dumps({"error": "Path di luar workspace root."})
        if not target.is_file():
            return json.dumps({"error": f"File tidak ditemukan: {file_path}"})
        original = target.read_text(encoding="utf-8")
        if old_str not in original:
            return json.dumps({"error": "old_str tidak ditemukan dalam file. Pastikan teks cocok persis termasuk spasi/indentasi."})
        count = original.count(old_str)
        updated = original.replace(old_str, new_str, 1)
        target.write_text(updated, encoding="utf-8")
        return json.dumps({
            "success": True,
            "path": str(target.relative_to(_WORKSPACE_ROOT)),
            "occurrences_found": count,
            "replaced": 1,
        })
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool: run_shell_command  (jalankan perintah di workspace — terbatas)
# ---------------------------------------------------------------------------

_ALLOWED_COMMANDS = {
    "python", "python3", "node", "npx", "tsx", "npm", "pip",
    "git", "ls", "cat", "find", "grep", "echo", "pwd", "which",
}


def run_shell_command(command: str, cwd: str = "") -> str:
    """
    Jalankan perintah shell di workspace (whitelist perintah tertentu).
    Berguna untuk: python script.py, npm install, git status, dll.
    """
    try:
        parts = command.strip().split()
        if not parts:
            return json.dumps({"error": "Perintah kosong."})
        base_cmd = Path(parts[0]).name  # strip path prefix
        if base_cmd not in _ALLOWED_COMMANDS:
            return json.dumps({
                "error": f"Perintah '{base_cmd}' tidak diizinkan. Perintah yang diizinkan: {', '.join(sorted(_ALLOWED_COMMANDS))}"
            })
        work_dir = (_WORKSPACE_ROOT / cwd).resolve() if cwd else _WORKSPACE_ROOT
        if _WORKSPACE_ROOT not in work_dir.parents and work_dir != _WORKSPACE_ROOT:
            return json.dumps({"error": "cwd di luar workspace root."})
        result = subprocess.run(  # noqa: S603
            parts,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return json.dumps({
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout[-3000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "Perintah timeout setelah 60 detik."})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})



# ---------------------------------------------------------------------------
# GitHub Tools
# ---------------------------------------------------------------------------

def github_get_issue(issue_number: int, owner: str = "", repo: str = "") -> str:
    """Ambil detail sebuah GitHub issue."""
    try:
        if not owner or not repo:
            owner, repo = _default_repo()
        if not owner or not repo:
            return json.dumps({"error": "owner dan repo wajib diisi. Set GITHUB_OWNER/GITHUB_REPO di .env."})
        data = _github_request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}")
        return json.dumps({
            "number": data["number"],
            "title": data["title"],
            "state": data["state"],
            "author": data.get("user", {}).get("login", ""),
            "labels": [lbl["name"] for lbl in data.get("labels", [])],
            "body": (data.get("body") or "")[:1500],
            "url": data["html_url"],
            "created_at": data["created_at"],
            "updated_at": data["updated_at"],
            "comments": data["comments"],
        })
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


def github_list_issues(
    owner: str = "", repo: str = "",
    state: str = "open", labels: str = "", limit: int = 10,
) -> str:
    """Daftar GitHub issues sebuah repo."""
    try:
        if not owner or not repo:
            owner, repo = _default_repo()
        if not owner or not repo:
            return json.dumps({"error": "owner dan repo wajib diisi."})
        params: dict[str, Any] = {"state": state, "per_page": min(limit, 30)}
        if labels:
            params["labels"] = labels
        qs = urllib.parse.urlencode(params)
        data = _github_request("GET", f"/repos/{owner}/{repo}/issues?{qs}")
        issues = []
        for issue in data[:limit]:
            if "pull_request" in issue:
                continue
            issues.append({
                "number": issue["number"],
                "title": issue["title"],
                "state": issue["state"],
                "labels": [lbl["name"] for lbl in issue.get("labels", [])],
                "author": issue.get("user", {}).get("login", ""),
                "url": issue["html_url"],
                "created_at": issue["created_at"],
            })
        return json.dumps({"repo": f"{owner}/{repo}", "count": len(issues), "issues": issues})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


def github_assign_labels(
    issue_number: int, labels: list[str],
    owner: str = "", repo: str = "", remove_pending_triage: bool = False,
) -> str:
    """Tambahkan label ke GitHub issue."""
    try:
        if not owner or not repo:
            owner, repo = _default_repo()
        if not owner or not repo:
            return json.dumps({"error": "owner dan repo wajib diisi."})
        _github_request("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/labels", body={"labels": labels})
        removed = False
        if remove_pending_triage:
            try:
                label_enc = urllib.parse.quote("pending-triage", safe="")
                _github_request("DELETE", f"/repos/{owner}/{repo}/issues/{issue_number}/labels/{label_enc}")
                removed = True
            except Exception:  # noqa: BLE001
                pass
        return json.dumps({"success": True, "issue_number": issue_number, "labels_added": labels, "pending_triage_removed": removed})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


def github_close_issue(
    issue_number: int, comment: str = "", owner: str = "", repo: str = "",
) -> str:
    """Tutup GitHub issue, opsional dengan komentar penutup."""
    try:
        if not owner or not repo:
            owner, repo = _default_repo()
        if not owner or not repo:
            return json.dumps({"error": "owner dan repo wajib diisi."})
        if comment:
            _github_request("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", body={"body": comment})
        _github_request("PATCH", f"/repos/{owner}/{repo}/issues/{issue_number}", body={"state": "closed"})
        return json.dumps({"success": True, "issue_number": issue_number, "action": "closed", "comment_posted": bool(comment)})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


def github_create_issue_comment(
    issue_number: int, body: str, owner: str = "", repo: str = "",
) -> str:
    """Posting komentar pada GitHub issue."""
    try:
        if not owner or not repo:
            owner, repo = _default_repo()
        if not owner or not repo:
            return json.dumps({"error": "owner dan repo wajib diisi."})
        data = _github_request("POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments", body={"body": body})
        return json.dumps({"success": True, "comment_id": data["id"], "url": data["html_url"]})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


def github_triage_issue(
    issue_number: int, issue_title: str,
    issue_body: str = "", owner: str = "", repo: str = "",
) -> str:
    """Jalankan pipeline triage Kiro lengkap pada sebuah issue."""
    if not owner or not repo:
        owner, repo = _default_repo()
    if not owner or not repo:
        return json.dumps({"error": "owner dan repo wajib diisi."})
    return _run_kiro_script("triage_issue.ts", {
        "ISSUE_NUMBER": str(issue_number),
        "ISSUE_TITLE": issue_title,
        "ISSUE_BODY": issue_body,
        "REPOSITORY_OWNER": owner,
        "REPOSITORY_NAME": repo,
        "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
        "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID", ""),
        "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
        "AWS_REGION": os.environ.get("AWS_REGION", "us-east-1"),
    })


def github_close_stale(owner: str = "", repo: str = "") -> str:
    """Tutup semua issue stale (pending-response + tidak aktif 7+ hari)."""
    if not owner or not repo:
        owner, repo = _default_repo()
    if not owner or not repo:
        return json.dumps({"error": "owner dan repo wajib diisi."})
    return _run_kiro_script("close_stale.ts", {
        "REPOSITORY_OWNER": owner,
        "REPOSITORY_NAME": repo,
        "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
    })



# ---------------------------------------------------------------------------
# TOOL_SCHEMAS  — dikonsumsi Claude
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    # ── Tools umum ─────────────────────────────────────────────────────────
    {
        "name": "get_current_time",
        "description": "Dapatkan tanggal dan waktu saat ini (UTC).",
        "input_schema": {
            "type": "object",
            "properties": {
                "timezone_name": {"type": "string", "description": "Label timezone opsional (informasional)."}
            },
        },
    },
    {
        "name": "calculate",
        "description": "Hitung ekspresi matematika dengan aman. Mendukung +, -, *, /, //, %, ** dan tanda kurung.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Ekspresi aritmatika, misal '(100 * 1.11) / 3'."}
            },
            "required": ["expression"],
        },
    },
    {
        "name": "web_search",
        "description": "Cari di web via DuckDuckGo. Gunakan untuk info terkini, docs, pesan error, dll.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Kata kunci pencarian."},
                "max_results": {"type": "integer", "description": "Jumlah hasil maksimal (default 5)."},
            },
            "required": ["query"],
        },
    },

    # ── Tools kode ─────────────────────────────────────────────────────────
    {
        "name": "read_code_file",
        "description": (
            "Baca file kode atau tampilkan isi direktori dari workspace. "
            "Gunakan ini sebelum mengedit file agar tahu isi terkininya. "
            "Bisa baca sebagian file dengan start_line/end_line."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path relatif dari workspace root, misal 'telegram-bot/bot.py' atau 'Kiro/scripts'."},
                "start_line": {"type": "integer", "description": "Baris mulai (1-indexed, default 1)."},
                "end_line": {"type": "integer", "description": "Baris akhir (0 = sampai akhir file, default 0)."},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "write_code_file",
        "description": (
            "Tulis atau timpa file kode di workspace. "
            "Gunakan untuk membuat file baru atau mengganti seluruh isi file. "
            "Untuk perubahan kecil/parsial, gunakan patch_code_file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path relatif dari workspace root."},
                "content": {"type": "string", "description": "Isi file yang akan ditulis."},
                "create_dirs": {"type": "boolean", "description": "Buat direktori jika belum ada (default true)."},
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "patch_code_file",
        "description": (
            "Ganti teks tertentu dalam file kode (find-and-replace tepat). "
            "Gunakan ini untuk perubahan parsial agar tidak menimpa seluruh file. "
            "old_str harus cocok PERSIS termasuk spasi dan indentasi."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path relatif dari workspace root."},
                "old_str": {"type": "string", "description": "Teks yang akan diganti (harus cocok persis)."},
                "new_str": {"type": "string", "description": "Teks pengganti."},
            },
            "required": ["file_path", "old_str", "new_str"],
        },
    },
    {
        "name": "run_shell_command",
        "description": (
            "Jalankan perintah shell di workspace. "
            "Perintah yang diizinkan: python, python3, node, npx, tsx, npm, pip, git, ls, cat, find, grep, echo, pwd, which. "
            "Berguna untuk: menjalankan script, install deps, git status/log, dll."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Perintah shell, misal 'python bot.py' atau 'git status'."},
                "cwd": {"type": "string", "description": "Working directory relatif dari workspace root (opsional)."},
            },
            "required": ["command"],
        },
    },

    # ── GitHub tools ────────────────────────────────────────────────────────
    {
        "name": "github_get_issue",
        "description": "Ambil detail sebuah GitHub issue (judul, body, label, status, dll.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_number": {"type": "integer", "description": "Nomor issue."},
                "owner": {"type": "string", "description": "Pemilik repo (default: GITHUB_OWNER di .env)."},
                "repo": {"type": "string", "description": "Nama repo (default: GITHUB_REPO di .env)."},
            },
            "required": ["issue_number"],
        },
    },
    {
        "name": "github_list_issues",
        "description": "Tampilkan daftar GitHub issues sebuah repo, bisa filter berdasarkan state atau label.",
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Pemilik repo."},
                "repo": {"type": "string", "description": "Nama repo."},
                "state": {"type": "string", "description": "'open', 'closed', atau 'all' (default: 'open')."},
                "labels": {"type": "string", "description": "Filter label (pisahkan dengan koma)."},
                "limit": {"type": "integer", "description": "Jumlah issue maksimal (default 10)."},
            },
        },
    },
    {
        "name": "github_assign_labels",
        "description": "Tambahkan satu atau lebih label ke GitHub issue. Opsional hapus label 'pending-triage'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_number": {"type": "integer", "description": "Nomor issue."},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "Daftar nama label."},
                "owner": {"type": "string", "description": "Pemilik repo."},
                "repo": {"type": "string", "description": "Nama repo."},
                "remove_pending_triage": {"type": "boolean", "description": "Hapus label 'pending-triage' setelah menambahkan label baru."},
            },
            "required": ["issue_number", "labels"],
        },
    },
    {
        "name": "github_close_issue",
        "description": "Tutup GitHub issue, opsional dengan komentar penutup.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_number": {"type": "integer", "description": "Nomor issue."},
                "comment": {"type": "string", "description": "Komentar sebelum menutup issue (opsional)."},
                "owner": {"type": "string", "description": "Pemilik repo."},
                "repo": {"type": "string", "description": "Nama repo."},
            },
            "required": ["issue_number"],
        },
    },
    {
        "name": "github_create_issue_comment",
        "description": "Posting komentar pada GitHub issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_number": {"type": "integer", "description": "Nomor issue."},
                "body": {"type": "string", "description": "Isi komentar (mendukung markdown)."},
                "owner": {"type": "string", "description": "Pemilik repo."},
                "repo": {"type": "string", "description": "Nama repo."},
            },
            "required": ["issue_number", "body"],
        },
    },
    {
        "name": "github_triage_issue",
        "description": (
            "Jalankan pipeline triage Kiro lengkap pada sebuah GitHub issue: "
            "deteksi duplikat → klasifikasi AI → assign label → posting komentar acknowledgment. "
            "Butuh Node.js dan folder Kiro/scripts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_number": {"type": "integer", "description": "Nomor issue yang akan di-triage."},
                "issue_title": {"type": "string", "description": "Judul issue."},
                "issue_body": {"type": "string", "description": "Isi/deskripsi issue (opsional, meningkatkan akurasi)."},
                "owner": {"type": "string", "description": "Pemilik repo."},
                "repo": {"type": "string", "description": "Nama repo."},
            },
            "required": ["issue_number", "issue_title"],
        },
    },
    {
        "name": "github_close_stale",
        "description": (
            "Jalankan Kiro stale-issue closer: otomatis menutup semua issue yang punya label "
            "'pending-response' dan tidak aktif selama 7+ hari. "
            "Butuh Node.js dan folder Kiro/scripts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Pemilik repo."},
                "repo": {"type": "string", "description": "Nama repo."},
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Registry + dispatcher
# ---------------------------------------------------------------------------

TOOL_IMPLEMENTATIONS: dict[str, Callable[..., str]] = {
    "get_current_time": get_current_time,
    "calculate": calculate,
    "web_search": web_search,
    "read_code_file": read_code_file,
    "write_code_file": write_code_file,
    "patch_code_file": patch_code_file,
    "run_shell_command": run_shell_command,
    "github_get_issue": github_get_issue,
    "github_list_issues": github_list_issues,
    "github_assign_labels": github_assign_labels,
    "github_close_issue": github_close_issue,
    "github_create_issue_comment": github_create_issue_comment,
    "github_triage_issue": github_triage_issue,
    "github_close_stale": github_close_stale,
}


def run_tool(name: str, tool_input: dict[str, Any]) -> str:
    """Dispatch tool call berdasarkan nama. Selalu mengembalikan string JSON."""
    func = TOOL_IMPLEMENTATIONS.get(name)
    if func is None:
        return json.dumps({"error": f"Tool tidak dikenal: '{name}'"})
    try:
        return func(**tool_input)
    except TypeError as exc:
        return json.dumps({"error": f"Argumen salah untuk '{name}': {exc}"})
