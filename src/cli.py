"""CLI entry point for config-file-validator."""

import json as json_mod
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .config import VERSION
from .diffing import diff_configs
from .parsers import ParseError, parse_file
from .validators import validate

console = Console()


def _render_result(result, verbose: bool, strict: bool = False):
    """Pretty-print a ValidationResult to the terminal."""
    effective_valid = result.strict_valid() if strict else result.valid
    icon = "✅" if effective_valid else "❌"
    fmt_label = f"[bold]{result.fmt.upper()}[/bold]"
    file_label = f"[cyan]{result.path}[/cyan]"

    if effective_valid:
        msg = f"{icon} {file_label} ({fmt_label}) — [green]válido[/green]"
        if result.warnings:
            msg += f"  [yellow]({len(result.warnings)} advertencia(s))[/yellow]"
        console.print(msg)
    else:
        console.print(f"{icon} {file_label} ({fmt_label}) — [red bold]inválido[/red bold]")

    if result.errors:
        tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold red")
        tbl.add_column("Campo", style="yellow", no_wrap=True)
        tbl.add_column("Error", style="white")
        tbl.add_column("Detalle", style="dim")
        for e in result.errors:
            tbl.add_row(e.get("field") or "—", e["message"], e.get("detail") or "")
        console.print(tbl)

    if result.warnings and verbose:
        tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        tbl.add_column("Campo", style="yellow", no_wrap=True)
        tbl.add_column("Advertencia", style="dim")
        for w in result.warnings:
            tbl.add_row(w.get("field") or "—", w["message"])
        console.print(tbl)
    elif result.warnings and not verbose:
        console.print(
            f"  [yellow]⚠ {len(result.warnings)} advertencia(s) — usa --verbose para verlas[/yellow]"
        )


@click.group()
@click.version_option(VERSION, prog_name="cfv")
def cli():
    """Config File Validator — valida, compara y exporta archivos .env, JSON y YAML."""


# ── validate ──────────────────────────────────────────────────────────────────

@cli.command("validate")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-s", "--schema", "schema_path", default=None, help="Schema file (.json o .yaml)")
@click.option("-f", "--format", "fmt", default=None,
              type=click.Choice(["env", "json", "yaml"]),
              help="Forzar formato (auto-detectado por defecto)")
@click.option("-v", "--verbose", is_flag=True, help="Mostrar advertencias detalladas")
@click.option("--strict", is_flag=True, help="Fallar si hay advertencias además de errores")
@click.option("--exit-zero", is_flag=True, help="Siempre salir con código 0 (útil en CI)")
@click.option("--json-output", is_flag=True, help="Salida en formato JSON")
def validate_cmd(files, schema_path, fmt, verbose, strict, exit_zero, json_output):
    """Valida uno o más archivos de configuración."""
    results = []
    for f in files:
        r = validate(f, schema_path=schema_path, fmt=fmt)
        results.append(r)

    if json_output:
        output = [r.to_dict() for r in results]
        print(json_mod.dumps(output, indent=2, ensure_ascii=False))
        if exit_zero:
            sys.exit(0)
        sys.exit(0 if all(r.valid for r in results) else 1)

    for r in results:
        _render_result(r, verbose, strict=strict)

    if strict:
        all_valid = all(r.strict_valid() for r in results)
    else:
        all_valid = all(r.valid for r in results)

    if len(results) > 1:
        valid_count = sum(1 for r in results if (r.strict_valid() if strict else r.valid))
        total = len(results)
        color = "green" if all_valid else "red"
        console.print(f"\n[{color}]{valid_count}/{total} archivos válidos[/{color}]")

    if exit_zero:
        sys.exit(0)
    sys.exit(0 if all_valid else 1)


# ── schema-init ───────────────────────────────────────────────────────────────

@cli.command("schema-init")
@click.argument("file", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Ruta de salida (default: schema.yaml)")
@click.option("-f", "--format", "fmt", default=None,
              type=click.Choice(["env", "json", "yaml"]))
@click.option("--dry-run", is_flag=True, help="Mostrar schema sin escribir archivo")
def schema_init(file, output, fmt, dry_run):
    """Genera un schema base a partir de un archivo de configuración existente."""
    import yaml as yaml_mod

    try:
        data, detected_fmt = parse_file(Path(file), fmt)
    except ParseError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if detected_fmt == "env":
        schema = {
            "required": list(data.keys()),
            "no_empty_values": True,
            "forbidden": [],
            "patterns": {},
        }
    else:
        def infer_type(val):
            if val is None:
                return {"type": ["null", "string"]}
            if isinstance(val, bool):
                return {"type": "boolean"}
            if isinstance(val, int):
                return {"type": "integer"}
            if isinstance(val, float):
                return {"type": "number"}
            if isinstance(val, list):
                return {"type": "array"}
            if isinstance(val, dict):
                props = {k: infer_type(v) for k, v in val.items()}
                return {"type": "object", "properties": props, "required": list(val.keys())}
            return {"type": "string"}

        schema = infer_type(data)
        schema["$schema"] = "http://json-schema.org/draft-07/schema#"

    schema_str = yaml_mod.dump(schema, default_flow_style=False, allow_unicode=True)

    if dry_run:
        console.print("[dim]--- schema (dry-run) ---[/dim]")
        console.print(schema_str)
        return

    out_path = output or "schema.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(schema_str)

    console.print(f"[green]✅ Schema generado:[/green] [cyan]{out_path}[/cyan]")


# ── diff ──────────────────────────────────────────────────────────────────────

@cli.command("diff")
@click.argument("file_a", type=click.Path(exists=True))
@click.argument("file_b", type=click.Path(exists=True))
@click.option("-f", "--format", "fmt", default=None,
              type=click.Choice(["env", "json", "yaml"]),
              help="Forzar formato para ambos archivos")
@click.option("--show-unchanged", is_flag=True, help="Mostrar también claves sin cambios")
@click.option("--json-output", is_flag=True, help="Salida en formato JSON")
def diff_cmd(file_a, file_b, fmt, show_unchanged, json_output):
    """Compara dos archivos de configuración y muestra las diferencias."""
    try:
        data_a, fmt_a = parse_file(Path(file_a), fmt)
        data_b, fmt_b = parse_file(Path(file_b), fmt)
    except ParseError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    result = diff_configs(data_a, data_b, file_a, file_b, fmt_a, fmt_b)

    if json_output:
        print(json_mod.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        sys.exit(0 if not result.has_differences else 1)

    if not result.has_differences:
        console.print(f"[green]✅ Los archivos son idénticos[/green]")
        sys.exit(0)

    console.print(
        f"\n[bold]Diferencias:[/bold] [cyan]{file_a}[/cyan] → [cyan]{file_b}[/cyan]\n"
    )

    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    tbl.add_column("Clave", style="bold", no_wrap=True)
    tbl.add_column("Estado")
    tbl.add_column(f"← {Path(file_a).name}", style="dim")
    tbl.add_column(f"→ {Path(file_b).name}")

    status_colors = {
        "added": "green",
        "removed": "red",
        "changed": "yellow",
        "unchanged": "dim",
    }
    status_labels = {
        "added": "➕ añadida",
        "removed": "➖ eliminada",
        "changed": "✏️  cambiada",
        "unchanged": "  igual",
    }

    for entry in result.entries:
        if entry.status == "unchanged" and not show_unchanged:
            continue
        color = status_colors[entry.status]
        label = status_labels[entry.status]
        old_v = str(entry.old_value) if entry.old_value is not None else ""
        new_v = str(entry.new_value) if entry.new_value is not None else ""
        tbl.add_row(
            entry.key,
            f"[{color}]{label}[/{color}]",
            old_v,
            f"[{color}]{new_v}[/{color}]",
        )

    console.print(tbl)

    summary = result.to_dict()["summary"]
    parts = []
    if summary["added"]:
        parts.append(f"[green]{summary['added']} añadidas[/green]")
    if summary["removed"]:
        parts.append(f"[red]{summary['removed']} eliminadas[/red]")
    if summary["changed"]:
        parts.append(f"[yellow]{summary['changed']} cambiadas[/yellow]")
    console.print(f"\nResumen: {' · '.join(parts)}")

    sys.exit(1 if result.has_differences else 0)


# ── keys ──────────────────────────────────────────────────────────────────────

@cli.command("keys")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-f", "--format", "fmt", default=None,
              type=click.Choice(["env", "json", "yaml"]))
@click.option("--json-output", is_flag=True, help="Salida en formato JSON")
@click.option("--count", is_flag=True, help="Mostrar solo el número de claves")
def keys_cmd(files, fmt, json_output, count):
    """Lista todas las claves de uno o más archivos de configuración."""
    all_results = {}

    for f in files:
        try:
            data, detected_fmt = parse_file(Path(f), fmt)
        except ParseError as e:
            console.print(f"[red]Error ({f}):[/red] {e}")
            sys.exit(1)

        if isinstance(data, dict):
            from .parsers import flatten_keys
            keys = flatten_keys(data)
        elif isinstance(data, list):
            from .parsers import flatten_keys
            keys = flatten_keys(data)
        else:
            keys = []

        all_results[f] = {"format": detected_fmt, "keys": sorted(keys), "count": len(keys)}

    if json_output:
        print(json_mod.dumps(all_results, indent=2, ensure_ascii=False))
        return

    for fname, info in all_results.items():
        if len(files) > 1:
            console.print(f"\n[bold cyan]{fname}[/bold cyan] ([bold]{info['format'].upper()}[/bold])")

        if count:
            console.print(f"[green]{info['count']}[/green] claves")
        else:
            for k in info["keys"]:
                console.print(f"  [yellow]{k}[/yellow]")
            console.print(f"\n[dim]{info['count']} claves en total[/dim]")


# ── export ────────────────────────────────────────────────────────────────────

@cli.command("export")
@click.argument("file", type=click.Path(exists=True))
@click.option("-f", "--format", "fmt", default=None,
              type=click.Choice(["env", "json", "yaml"]))
@click.option("-o", "--output-format", "out_fmt",
              type=click.Choice(["json", "yaml"]), default="json",
              help="Formato de salida (default: json)")
@click.option("--indent", default=2, show_default=True, help="Indentación JSON")
def export_cmd(file, fmt, out_fmt, indent):
    """Exporta un archivo de configuración a JSON o YAML."""
    import yaml as yaml_mod

    try:
        data, _ = parse_file(Path(file), fmt)
    except ParseError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if out_fmt == "json":
        print(json_mod.dumps(data, indent=indent, ensure_ascii=False, default=str))
    else:
        print(yaml_mod.dump(data, default_flow_style=False, allow_unicode=True), end="")


def main():
    cli()


if __name__ == "__main__":
    main()
