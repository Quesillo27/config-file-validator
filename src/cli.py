"""CLI entry point for config-file-validator."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .validators import validate

console = Console()


def _render_result(result, verbose: bool):
    """Pretty-print a ValidationResult to the terminal."""
    icon = "✅" if result.valid else "❌"
    fmt_label = f"[bold]{result.fmt.upper()}[/bold]"
    file_label = f"[cyan]{result.path}[/cyan]"

    if result.valid:
        msg = f"{icon} {file_label} ({fmt_label}) — [green]válido[/green]"
        if result.warnings:
            msg += f"  [yellow]({len(result.warnings)} advertencia(s))[/yellow]"
        console.print(msg)
    else:
        console.print(f"{icon} {file_label} ({fmt_label}) — [red bold]inválido[/red bold]")

    # Errors table
    if result.errors:
        tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold red")
        tbl.add_column("Campo", style="yellow", no_wrap=True)
        tbl.add_column("Error", style="white")
        tbl.add_column("Detalle", style="dim")
        for e in result.errors:
            tbl.add_row(e.get("field") or "—", e["message"], e.get("detail") or "")
        console.print(tbl)

    # Warnings
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
@click.version_option("1.0.0", prog_name="cfv")
def cli():
    """Config File Validator — valida archivos .env, JSON y YAML."""


@cli.command("validate")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-s", "--schema", "schema_path", default=None, help="Schema file (.json or .yaml)")
@click.option("-f", "--format", "fmt", default=None,
              type=click.Choice(["env", "json", "yaml"]),
              help="Forzar formato (auto-detectado por defecto)")
@click.option("-v", "--verbose", is_flag=True, help="Mostrar advertencias detalladas")
@click.option("--json-output", is_flag=True, help="Salida en formato JSON")
def validate_cmd(files, schema_path, fmt, verbose, json_output):
    """Valida uno o más archivos de configuración."""
    import json as json_mod

    results = []
    for f in files:
        r = validate(f, schema_path=schema_path, fmt=fmt)
        results.append(r)

    if json_output:
        output = []
        for r in results:
            output.append({
                "file": r.path,
                "format": r.fmt,
                "valid": r.valid,
                "errors": r.errors,
                "warnings": r.warnings,
            })
        print(json_mod.dumps(output, indent=2, ensure_ascii=False))
        sys.exit(0 if all(r.valid for r in results) else 1)

    # Human output
    for r in results:
        _render_result(r, verbose)

    all_valid = all(r.valid for r in results)
    if len(results) > 1:
        valid_count = sum(1 for r in results if r.valid)
        total = len(results)
        color = "green" if all_valid else "red"
        console.print(f"\n[{color}]{valid_count}/{total} archivos válidos[/{color}]")

    sys.exit(0 if all_valid else 1)


@cli.command("schema-init")
@click.argument("file", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Ruta de salida (default: schema.yaml)")
@click.option("-f", "--format", "fmt", default=None,
              type=click.Choice(["env", "json", "yaml"]))
def schema_init(file, output, fmt):
    """Genera un schema base a partir de un archivo de configuración existente."""
    import yaml as yaml_mod
    from .parsers import parse_file, ParseError

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
        # Generate a minimal JSON Schema
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

    out_path = output or "schema.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml_mod.dump(schema, f, default_flow_style=False, allow_unicode=True)

    console.print(f"[green]✅ Schema generado:[/green] [cyan]{out_path}[/cyan]")


def main():
    cli()


if __name__ == "__main__":
    main()
