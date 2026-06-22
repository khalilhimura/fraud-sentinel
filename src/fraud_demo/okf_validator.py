"""OKF v0.1 validation for Phase 5."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
DATE_HEADING_RE = re.compile(r"^## \d{4}-\d{2}-\d{2}\s*$", re.MULTILINE)
RECOMMENDED_FIELDS = ["title", "description"]
PRIVACY_TERMS = [
    "transaction_description",
    "customer_email",
    "customer_name",
    "customer_phone",
    "raw customer note",
]


@dataclass(frozen=True)
class OkfValidationResult:
    """Validation result and optional report path."""

    okf_version: str
    bundle_path: Path
    valid: bool
    concept_count: int
    link_count: int
    hard_errors: list[dict[str, str]]
    warnings: list[dict[str, str]]
    report_path: Path | None


def _issue(code: str, path: Path | str, message: str) -> dict[str, str]:
    return {"code": code, "path": str(path), "message": message}


def _is_reserved(path: Path) -> bool:
    return path.name in {"index.md", "log.md"}


def _concept_id(relative: Path) -> str:
    return relative.with_suffix("").as_posix()


def _decode_markdown(path: Path, bundle: Path) -> tuple[str | None, dict[str, str] | None]:
    try:
        resolved = path.resolve()
        resolved.relative_to(bundle.resolve())
    except ValueError:
        return None, _issue("path_escape", path, "Markdown path escapes bundle root.")
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, _issue("invalid_utf8", path, "Markdown file is not valid UTF-8.")


def _parse_frontmatter(
    text: str,
    relative: Path,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, _issue(
            "missing_frontmatter",
            relative,
            "Non-reserved concept lacks YAML frontmatter.",
        )
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        return None, _issue(
            "invalid_frontmatter",
            relative,
            f"YAML frontmatter could not be parsed: {exc}",
        )
    if not isinstance(data, dict):
        return None, _issue(
            "invalid_frontmatter",
            relative,
            "YAML frontmatter must be a mapping.",
        )
    return data, None


def _reserved_error(text: str, relative: Path) -> dict[str, str] | None:
    has_frontmatter = FRONTMATTER_RE.match(text) is not None
    if relative.as_posix() == "index.md":
        if not has_frontmatter:
            return None
        data, error = _parse_frontmatter(text, relative)
        if error:
            return error
        extra_keys = set(data or {}) - {"okf_version"}
        if extra_keys:
            return _issue(
                "reserved_frontmatter",
                relative,
                "Root index frontmatter may only declare okf_version.",
            )
        return None
    if relative.name == "index.md" and has_frontmatter:
        return _issue(
            "reserved_frontmatter",
            relative,
            "Subdirectory index.md must not be an ordinary concept.",
        )
    if relative.name == "log.md":
        if has_frontmatter:
            return _issue(
                "reserved_frontmatter",
                relative,
                "log.md must not be an ordinary concept.",
            )
        if not DATE_HEADING_RE.search(text):
            return _issue("reserved_structure", relative, "log.md must use YYYY-MM-DD headings.")
    return None


def _timestamp_warning(frontmatter: dict[str, Any], relative: Path) -> dict[str, str] | None:
    value = frontmatter.get("timestamp")
    if value is None:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        datetime.fromisoformat(text)
    except ValueError:
        return _issue("invalid_timestamp", relative, "timestamp is not ISO 8601.")
    return None


def _privacy_warnings(text: str, relative: Path) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    lowered = text.lower()
    for term in PRIVACY_TERMS:
        if term in lowered:
            warnings.append(
                _issue("privacy_pattern", relative, f"Privacy scanner matched {term}.")
            )
    if EMAIL_RE.search(text):
        warnings.append(_issue("privacy_pattern", relative, "Privacy scanner matched email."))
    return warnings


def _link_target(path: str, source: Path, bundle: Path) -> Path | None:
    parsed = urlparse(path)
    if parsed.scheme or parsed.netloc or path.startswith("#"):
        return None
    target = unquote(parsed.path)
    if not target:
        return None
    resolved = (bundle / target[1:]) if target.startswith("/") else (source.parent / target)
    if resolved.suffix == "":
        resolved = resolved / "index.md" if str(path).endswith("/") else resolved.with_suffix(".md")
    return resolved.resolve()


def _validate_links(
    text: str,
    relative: Path,
    source: Path,
    bundle: Path,
) -> tuple[int, list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    link_count = 0
    for match in MARKDOWN_LINK_RE.finditer(text):
        link_count += 1
        target = _link_target(match.group(1), source, bundle)
        if target is None:
            continue
        try:
            target.relative_to(bundle.resolve())
        except ValueError:
            warnings.append(
                _issue(
                    "broken_link",
                    relative,
                    f"Internal link escapes bundle: {match.group(1)}",
                )
            )
            continue
        if not target.exists():
            warnings.append(
                _issue(
                    "broken_link",
                    relative,
                    f"Internal link target missing: {match.group(1)}",
                )
            )
    return link_count, warnings


def _relation_warnings(
    frontmatter: dict[str, Any],
    relative: Path,
    concept_ids: set[str],
) -> list[dict[str, str]]:
    relations = frontmatter.get("relations", [])
    if relations is None:
        return []
    if not isinstance(relations, list):
        return [_issue("invalid_relation", relative, "relations must be a list.")]
    warnings: list[dict[str, str]] = []
    for relation in relations:
        if not isinstance(relation, dict):
            warnings.append(
                _issue("invalid_relation", relative, "relation entry must be a mapping.")
            )
            continue
        target = relation.get("target_concept_id")
        if target and str(target) not in concept_ids:
            warnings.append(
                _issue(
                    "broken_relation",
                    relative,
                    f"Relation target does not exist: {target}",
                )
            )
    return warnings


def _directory_index_warnings(bundle: Path) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for directory in sorted(path for path in bundle.rglob("*") if path.is_dir()):
        if directory == bundle:
            continue
        if any(child.suffix == ".md" for child in directory.iterdir()) and not (
            directory / "index.md"
        ).exists():
            warnings.append(
                _issue(
                    "missing_directory_index",
                    directory.relative_to(bundle),
                    "Directory containing Markdown lacks index.md.",
                )
            )
    return warnings


def _write_report(result: OkfValidationResult, report_path: Path) -> None:
    payload = {
        "okf_version": result.okf_version,
        "bundle_path": str(result.bundle_path),
        "valid": result.valid,
        "concept_count": result.concept_count,
        "link_count": result.link_count,
        "hard_errors": result.hard_errors,
        "warnings": result.warnings,
        "validated_at": datetime.now(UTC).isoformat(),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_okf_bundle(
    bundle: Path | str,
    *,
    report_path: Path | str | None = None,
    max_file_size_bytes: int = 512_000,
) -> OkfValidationResult:
    """Validate OKF hard rules and soft warnings for a bundle."""

    bundle_path = Path(bundle)
    hard_errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    concept_frontmatter: dict[str, dict[str, Any]] = {}
    concept_ids: set[str] = set()
    okf_version = "0.1"
    link_count = 0

    markdown_paths = sorted(bundle_path.rglob("*.md"))
    for path in markdown_paths:
        text, decode_error = _decode_markdown(path, bundle_path)
        relative = path.relative_to(bundle_path)
        if decode_error:
            hard_errors.append(decode_error)
            continue
        assert text is not None
        if _is_reserved(relative):
            reserved_error = _reserved_error(text, relative)
            if reserved_error:
                hard_errors.append(reserved_error)
            if relative.as_posix() == "index.md":
                match = FRONTMATTER_RE.match(text)
                if match:
                    data = yaml.safe_load(match.group(1)) or {}
                    okf_version = str(data.get("okf_version", okf_version))
            continue

        frontmatter, frontmatter_error = _parse_frontmatter(text, relative)
        if frontmatter_error:
            hard_errors.append(frontmatter_error)
            continue
        assert frontmatter is not None
        if not str(frontmatter.get("type") or "").strip():
            hard_errors.append(
                _issue("missing_type", relative, "Concept lacks a non-empty type.")
            )
        concept_id = _concept_id(relative)
        if concept_id in concept_ids:
            hard_errors.append(_issue("duplicate_concept_id", relative, "Duplicate concept ID."))
        concept_ids.add(concept_id)
        concept_frontmatter[concept_id] = frontmatter

        for field in RECOMMENDED_FIELDS:
            if not str(frontmatter.get(field) or "").strip():
                warnings.append(
                    _issue("missing_recommended_field", relative, f"Missing {field}.")
                )
        timestamp_warning = _timestamp_warning(frontmatter, relative)
        if timestamp_warning:
            warnings.append(timestamp_warning)
        if path.stat().st_size > max_file_size_bytes:
            warnings.append(_issue("file_too_large", relative, "Concept exceeds file-size limit."))
        file_link_count, link_warnings = _validate_links(text, relative, path, bundle_path)
        link_count += file_link_count
        warnings.extend(link_warnings)
        warnings.extend(_privacy_warnings(text, relative))

    for concept_id, frontmatter in concept_frontmatter.items():
        warnings.extend(
            _relation_warnings(frontmatter, Path(f"{concept_id}.md"), concept_ids)
        )

    warnings.extend(_directory_index_warnings(bundle_path))

    result = OkfValidationResult(
        okf_version=okf_version,
        bundle_path=bundle_path,
        valid=not hard_errors,
        concept_count=len(concept_ids),
        link_count=link_count,
        hard_errors=hard_errors,
        warnings=warnings,
        report_path=Path(report_path) if report_path is not None else None,
    )
    if report_path is not None:
        _write_report(result, Path(report_path))
    return result
