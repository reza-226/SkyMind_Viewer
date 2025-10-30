#!/usr/bin/env python3
"""Validate run directories against the registry schema and required artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Tuple, Dict, Any, List

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "registry" / "contracts" / "schema" / "run_metadata.schema.json"


class ValidationError(Exception):
    """Raised when validation errors are discovered."""


def load_schema() -> Dict[str, Any]:
    if not SCHEMA_PATH.exists():
        raise ValidationError(f"Schema file not found: {SCHEMA_PATH.relative_to(ROOT)}")
    try:
        with SCHEMA_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Schema JSON invalid: {exc}") from exc


def load_metadata(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise ValidationError(f"Metadata file missing: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Metadata JSON invalid ({path.relative_to(ROOT)}): {exc}") from exc


def iter_run_dirs(target: Path) -> Iterable[Path]:
    if target.is_file():
        raise ValidationError("Target باید یک پوشه ران باشد، نه فایل.")
    if target / "run_metadata.json" in target.iterdir():
        # اگر خود پوشه یک ران است
        yield target
        return
    # در غیر این صورت، همه زیرپوشه‌های حاوی run_metadata.json را بگرد
    found = False
    for path in sorted(target.iterdir()):
        if path.is_dir() and (path / "run_metadata.json").exists():
            found = True
            yield path
    if not found:
        raise ValidationError(
            f"در {target.relative_to(ROOT)} هیچ پوشه‌ای با run_metadata.json پیدا نشد."
        )


def validate_required_files(run_dir: Path, metadata: Dict[str, Any]) -> List[str]:
    missing: List[str] = []

    tasks_csv = metadata.get("artifacts", {}).get("tasks_csv")
    if tasks_csv:
        tasks_path = run_dir / tasks_csv
        if not tasks_path.exists():
            missing.append(f"فایل tasks_csv ({tasks_csv}) وجود ندارد.")
    else:
        missing.append("کلید artifacts.tasks_csv در متادیتا تنظیم نشده است.")

    logs = metadata.get("artifacts", {}).get("logs")
    if isinstance(logs, list):
        for log in logs:
            log_path = run_dir / log
            if not log_path.exists():
                missing.append(f"فایل لاگ ({log}) وجود ندارد.")
    else:
        missing.append("کلید artifacts.logs در متادیتا باید آرایه باشد.")

    return missing


def validate_run(run_dir: Path, validator: jsonschema.Draft202012Validator) -> Tuple[bool, List[str]]:
    run_errors: List[str] = []

    metadata_path = run_dir / "run_metadata.json"
    try:
        metadata = load_metadata(metadata_path)
    except ValidationError as exc:
        run_errors.append(str(exc))
        return False, run_errors

    # validate schema
    schema_errors = sorted(validator.iter_errors(metadata), key=lambda e: e.path)
    for err in schema_errors:
        location = ".".join(str(x) for x in err.path) or "(root)"
        run_errors.append(f"شِما نامعتبر: {location} → {err.message}")

    # check required files
    run_errors.extend(validate_required_files(run_dir, metadata))

    return len(run_errors) == 0, run_errors


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="اعتبارسنجی ران‌ها بر اساس JSON Schema و وجود فایل‌های اعلام‌شده."
    )
    parser.add_argument(
        "target",
        type=Path,
        help="مسیر پوشه ران (مثلاً runs_dev/run_2025-09-18_scenario-fogAerial) "
             "یا پوشه‌ای که تعدادی ران داخلش است (مثلاً runs_dev).",
    )
    args = parser.parse_args(argv)

    target = args.target.resolve()
    try:
        schema = load_schema()
        validator = jsonschema.Draft202012Validator(schema)
        run_dirs = list(iter_run_dirs(target))
    except ValidationError as exc:
        print(f"[!] خطا: {exc}", file=sys.stderr)
        return 1

    overall_success = True
    for run_dir in run_dirs:
        rel_name = run_dir.relative_to(ROOT)
        success, errors = validate_run(run_dir, validator)
        if success:
            print(f"[✓] {rel_name}: همه چیز درست است.")
        else:
            overall_success = False
            print(f"[×] {rel_name}:")
            for err in errors:
                print(f"    - {err}")

    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
