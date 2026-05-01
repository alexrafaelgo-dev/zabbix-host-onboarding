#!/usr/bin/env python3
"""Validador de inventário CSV para onboarding de hosts no Zabbix."""

from __future__ import annotations

import argparse
import csv
import ipaddress
from pathlib import Path

REQUIRED_COLUMNS = {"hostname", "group", "template"}
EXPECTED_COLUMNS = {
    "hostname",
    "visible_name",
    "ip",
    "dns",
    "group",
    "template",
    "proxy",
    "interface_type",
    "port",
    "description",
}


def validate_csv(csv_path: Path) -> list[str]:
    errors: list[str] = []
    seen_hostnames: set[str] = set()

    if not csv_path.exists():
        return [f"Arquivo CSV não encontrado: {csv_path}"]

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            return ["CSV inválido: cabeçalho não encontrado."]

        header = {name.strip() for name in reader.fieldnames}

        missing_required_cols = REQUIRED_COLUMNS - header
        if missing_required_cols:
            errors.append(
                "CSV sem colunas obrigatórias: " + ", ".join(sorted(missing_required_cols))
            )

        unknown_cols = header - EXPECTED_COLUMNS
        if unknown_cols:
            errors.append(
                "CSV contém colunas não reconhecidas (revise ou ajuste script): "
                + ", ".join(sorted(unknown_cols))
            )

        for line_number, row in enumerate(reader, start=2):
            hostname = (row.get("hostname") or "").strip()
            group = (row.get("group") or "").strip()
            template = (row.get("template") or "").strip()
            ip_value = (row.get("ip") or "").strip()
            dns_value = (row.get("dns") or "").strip()
            port_value = (row.get("port") or "").strip()

            if not hostname:
                errors.append(f"Linha {line_number}: hostname é obrigatório.")
            elif hostname in seen_hostnames:
                errors.append(f"Linha {line_number}: hostname duplicado no CSV: {hostname}")
            else:
                seen_hostnames.add(hostname)

            if not group:
                errors.append(f"Linha {line_number}: group é obrigatório.")

            if not template:
                errors.append(f"Linha {line_number}: template é obrigatório.")

            if not ip_value and not dns_value:
                errors.append(f"Linha {line_number}: informe ao menos ip ou dns.")

            if ip_value:
                try:
                    ipaddress.ip_address(ip_value)
                except ValueError:
                    errors.append(f"Linha {line_number}: IP inválido: {ip_value}")

            if port_value:
                if not port_value.isdigit():
                    errors.append(f"Linha {line_number}: porta deve ser numérica: {port_value}")
                else:
                    port = int(port_value)
                    if port < 1 or port > 65535:
                        errors.append(f"Linha {line_number}: porta fora do intervalo 1-65535: {port}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida arquivo CSV de hosts para Zabbix")
    parser.add_argument("--csv", required=True, type=Path, help="Caminho para o arquivo CSV")
    args = parser.parse_args()

    errors = validate_csv(args.csv)
    if errors:
        print("[ERRO] Falha na validação do CSV:")
        for error in errors:
            print(f" - {error}")
        return 1

    print(f"[OK] CSV válido: {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
