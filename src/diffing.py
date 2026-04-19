"""Config file diffing logic — compares two parsed configs and returns a diff."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import DIFF_ADDED, DIFF_CHANGED, DIFF_REMOVED, DIFF_UNCHANGED


@dataclass
class DiffEntry:
    key: str
    status: str  # added | removed | changed | unchanged
    old_value: Any = None
    new_value: Any = None

    def to_dict(self) -> dict:
        d: dict = {"key": self.key, "status": self.status}
        if self.status == DIFF_CHANGED:
            d["old"] = _safe_repr(self.old_value)
            d["new"] = _safe_repr(self.new_value)
        elif self.status == DIFF_ADDED:
            d["value"] = _safe_repr(self.new_value)
        elif self.status == DIFF_REMOVED:
            d["value"] = _safe_repr(self.old_value)
        return d


@dataclass
class DiffResult:
    file_a: str
    file_b: str
    fmt_a: str
    fmt_b: str
    entries: list[DiffEntry] = field(default_factory=list)

    @property
    def added(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.status == DIFF_ADDED]

    @property
    def removed(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.status == DIFF_REMOVED]

    @property
    def changed(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.status == DIFF_CHANGED]

    @property
    def unchanged(self) -> list[DiffEntry]:
        return [e for e in self.entries if e.status == DIFF_UNCHANGED]

    @property
    def has_differences(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def to_dict(self) -> dict:
        return {
            "file_a": self.file_a,
            "file_b": self.file_b,
            "fmt_a": self.fmt_a,
            "fmt_b": self.fmt_b,
            "summary": {
                "added": len(self.added),
                "removed": len(self.removed),
                "changed": len(self.changed),
                "unchanged": len(self.unchanged),
            },
            "entries": [e.to_dict() for e in self.entries if e.status != DIFF_UNCHANGED],
        }


def _safe_repr(value: Any) -> Any:
    """Return a JSON-serializable representation, masking potential secrets."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return str(value)


def _flatten(data: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict/list into dot-notation key→value pairs."""
    result: dict[str, Any] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            full = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (dict, list)):
                result.update(_flatten(v, full))
            else:
                result[full] = v
    elif isinstance(data, list):
        for i, v in enumerate(data):
            full = f"{prefix}[{i}]"
            if isinstance(v, (dict, list)):
                result.update(_flatten(v, full))
            else:
                result[full] = v
    else:
        result[prefix] = data
    return result


def diff_configs(
    data_a: dict | list,
    data_b: dict | list,
    file_a: str,
    file_b: str,
    fmt_a: str,
    fmt_b: str,
) -> DiffResult:
    """Compare two parsed config objects and return a DiffResult."""
    result = DiffResult(file_a=file_a, file_b=file_b, fmt_a=fmt_a, fmt_b=fmt_b)

    flat_a = _flatten(data_a)
    flat_b = _flatten(data_b)
    all_keys = sorted(set(flat_a) | set(flat_b))

    for key in all_keys:
        in_a = key in flat_a
        in_b = key in flat_b

        if in_a and in_b:
            if flat_a[key] == flat_b[key]:
                result.entries.append(DiffEntry(key, DIFF_UNCHANGED, flat_a[key], flat_b[key]))
            else:
                result.entries.append(DiffEntry(key, DIFF_CHANGED, flat_a[key], flat_b[key]))
        elif in_a:
            result.entries.append(DiffEntry(key, DIFF_REMOVED, old_value=flat_a[key]))
        else:
            result.entries.append(DiffEntry(key, DIFF_ADDED, new_value=flat_b[key]))

    return result
