from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path


INCLUDE_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".cfg",
    ".ini",
    ".json",
    ".yaml",
    ".yml",
    ".sql",
    ".ui",
    ".qrc",
    ".bat",
    ".ps1",
    ".sh",
}

EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".idea",
    ".vscode",
    ".cache",
    "logs",
    "tmp",
    "data",
    "secrets",
    ".ai",
}

EXCLUDE_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "secrets.json",
    "credentials.json",
    "config.local.py",
    "settings.local.py",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
    ".7z",
    ".rar",
    ".exe",
    ".dll",
    ".so",
    ".bin",
}


def should_skip_dir(dir_name: str) -> bool:
    if dir_name.startswith("."):
        return True
    return dir_name in EXCLUDE_DIRS


def should_include_file(file_path: Path, output_name: str) -> bool:
    if file_path.name == output_name:
        return False

    if file_path.name in EXCLUDE_FILES:
        return False

    if file_path.name.lower().startswith(".env"):
        return False

    ext = file_path.suffix.lower()

    if ext in EXCLUDE_EXTENSIONS:
        return False

    if ext not in INCLUDE_EXTENSIONS:
        return False

    return True


def collect_files(root: Path, output_name: str) -> list[Path]:
    files: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames) if not should_skip_dir(d)]

        for filename in sorted(filenames):
            file_path = Path(dirpath) / filename

            if should_include_file(file_path, output_name):
                files.append(file_path)

    return files


def read_file_safely(file_path: Path, max_size: int) -> str:
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[READ ERROR: {exc}]"

    if len(text) > max_size:
        text = text[:max_size] + "\n\n... [FILE TRUNCATED DUE TO SIZE] ..."

    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export project text files into one txt context file."
    )

    parser.add_argument(
        "--root",
        default=".",
        help="Project root folder. Default: current directory",
    )

    parser.add_argument(
        "--out",
        default="project_context.txt",
        help="Output txt file name. Default: project_context.txt",
    )

    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only export file list, not file contents.",
    )

    parser.add_argument(
        "--max-size",
        type=int,
        default=300_000,
        help="Maximum characters per file. Default: 300000",
    )

    parser.add_argument(
        "--max-files",
        type=int,
        default=2000,
        help="Maximum number of files to export. Default: 2000",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    root = Path(args.root).resolve()
    output_path = Path(args.out).resolve()

    if not root.exists():
        print(f"❌ Root folder does not exist: {root}")
        return

    files = collect_files(root, output_path.name)

    if not files:
        print("❌ No exportable files found.")
        return

    if len(files) > args.max_files:
        print(
            f"⚠️ Found {len(files)} files. "
            f"Exporting only first {args.max_files}. "
            f"Use --max-files to increase."
        )
        files = files[: args.max_files]

    with output_path.open("w", encoding="utf-8") as out:
        out.write("PROJECT EXPORT\n")
        out.write("=" * 80 + "\n")
        out.write(f"Generated At : {datetime.now().isoformat()}\n")
        out.write(f"Project Root : {root}\n")
        out.write(f"Total Files  : {len(files)}\n")
        out.write(f"List Only    : {args.list_only}\n")
        out.write("=" * 80 + "\n\n")

        out.write("FILE LIST\n")
        out.write("-" * 80 + "\n")

        for file_path in files:
            relative_path = file_path.relative_to(root).as_posix()
            out.write(f"{relative_path}\n")

        if args.list_only:
            print(f"✅ File list exported: {output_path}")
            return

        for file_path in files:
            relative_path = file_path.relative_to(root).as_posix()

            out.write("\n\n")
            out.write("=" * 80 + "\n")
            out.write(f"FILE: {relative_path}\n")
            out.write("=" * 80 + "\n\n")

            content = read_file_safely(file_path, args.max_size)
            out.write(content)

            if not content.endswith("\n"):
                out.write("\n")

    print(f"✅ Exported {len(files)} files.")
    print(f"📄 Output file: {output_path}")


if __name__ == "__main__":
    main()