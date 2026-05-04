#!/usr/bin/env python3
"""Criação idempotente de hosts no Zabbix a partir de CSV."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from validate_csv import validate_csv

INTERFACE_TYPE_MAP = {
    "agent": 1,
    "snmp": 2,
    "ipmi": 3,
    "jmx": 4,
}
SNMP_VERSIONS = {"2", "2c", "snmpv2", "snmpv2c"}


class ZabbixAPIError(RuntimeError):
    """Erro da API Zabbix."""


class ZabbixClient:
    def __init__(self, url: str, token: str, timeout: int = 30) -> None:
        self.url = url
        self.token = token
        self.timeout = timeout
        self._request_id = 1

    def call(self, method: str, params: dict[str, Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._request_id,
        }
        self._request_id += 1

        response = requests.post(
            self.url,
            json=payload,
            headers={
                "Content-Type": "application/json-rpc",
                "Authorization": f"Bearer {self.token}",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            error = data["error"]
            raise ZabbixAPIError(
                f"API error ({error.get('code')}): {error.get('message')} - {error.get('data')}"
            )

        return data.get("result")


def load_env(env_file: Path) -> tuple[str, str, int]:
    load_dotenv(env_file)

    url = os.getenv("ZABBIX_URL", "").strip()
    token = os.getenv("ZABBIX_API_TOKEN", "").strip()
    timeout_raw = os.getenv("ZABBIX_TIMEOUT", "30").strip()

    if not url:
        raise ValueError("Variável ZABBIX_URL não definida.")
    if not token:
        raise ValueError("Variável ZABBIX_API_TOKEN não definida.")
    if not timeout_raw.isdigit():
        raise ValueError("Variável ZABBIX_TIMEOUT deve ser numérica.")

    return url, token, int(timeout_raw)


def get_id_by_name(client: ZabbixClient, method: str, key: str, value: str, id_field: str) -> str:
    result = client.call(method, {"output": [id_field, key], "filter": {key: [value]}})
    if not result:
        raise ZabbixAPIError(
            f"Dependência não encontrada no Zabbix: método={method}, campo={key}, valor={value}"
        )
    return result[0][id_field]


def host_exists(client: ZabbixClient, hostname: str) -> bool:
    result = client.call("host.get", {"output": ["hostid"], "filter": {"host": [hostname]}})
    return bool(result)


def build_interface(row: dict[str, str]) -> dict[str, Any]:
    interface_label = (row.get("interface_type") or "agent").strip().lower() or "agent"
    if interface_label not in INTERFACE_TYPE_MAP:
        raise ValueError(
            f"interface_type inválido '{interface_label}'. Valores suportados: {', '.join(INTERFACE_TYPE_MAP)}"
        )

    ip = (row.get("ip") or "").strip()
    dns = (row.get("dns") or "").strip()
    default_port = "161" if interface_label == "snmp" else "10050"
    port = (row.get("port") or default_port).strip() or default_port
    useip = 1 if ip else 0

    interface: dict[str, Any] = {
        "type": INTERFACE_TYPE_MAP[interface_label],
        "main": 1,
        "useip": useip,
        "ip": ip,
        "dns": dns,
        "port": port,
    }

    if interface_label == "snmp":
        snmp_version = (row.get("snmp_version") or "").strip().lower()
        snmp_community = (row.get("snmp_community") or "").strip()

        if snmp_version not in SNMP_VERSIONS:
            raise ValueError(
                "SNMP requer snmp_version em: 2, 2c, snmpv2 ou snmpv2c."
            )
        if not snmp_community:
            raise ValueError("SNMP requer snmp_community.")

        interface["details"] = {
            "version": 2,
            "community": snmp_community,
        }

    return interface


def create_hosts(csv_path: Path, client: ZabbixClient, dry_run: bool = False) -> int:
    created = 0
    skipped = 0

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for line_number, row in enumerate(reader, start=2):
            hostname = (row.get("hostname") or "").strip()
            visible_name = (row.get("visible_name") or "").strip()
            group_name = (row.get("group") or "").strip()
            template_name = (row.get("template") or "").strip()
            proxy_name = (row.get("proxy") or "").strip()
            description = (row.get("description") or "").strip()

            if host_exists(client, hostname):
                print(f"[SKIP] Linha {line_number}: host já existe: {hostname}")
                skipped += 1
                continue

            group_id = get_id_by_name(client, "hostgroup.get", "name", group_name, "groupid")
            template_id = get_id_by_name(client, "template.get", "host", template_name, "templateid")
            interface = build_interface(row)

            payload: dict[str, Any] = {
                "host": hostname,
                "groups": [{"groupid": group_id}],
                "templates": [{"templateid": template_id}],
                "interfaces": [interface],
                "description": description,
            }
            if visible_name:
                payload["name"] = visible_name

            if proxy_name:
                proxy_id = get_id_by_name(client, "proxy.get", "name", proxy_name, "proxyid")
                payload["proxyid"] = proxy_id

            if dry_run:
                print(f"[DRY-RUN] Linha {line_number}: criaria host {hostname} com payload: {payload}")
                created += 1
                continue

            client.call("host.create", payload)
            print(f"[OK] Linha {line_number}: host criado: {hostname}")
            created += 1

    print(f"Resumo: criados={created}, existentes/skipped={skipped}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cria hosts no Zabbix a partir de CSV")
    parser.add_argument("--csv", required=True, type=Path, help="Caminho do CSV")
    parser.add_argument("--env-file", default=Path(".env"), type=Path, help="Arquivo .env")
    parser.add_argument("--dry-run", action="store_true", help="Somente simula sem criar host")
    args = parser.parse_args()

    validation_errors = validate_csv(args.csv)
    if validation_errors:
        print("[ERRO] CSV inválido. Corrija antes de executar a criação:")
        for error in validation_errors:
            print(f" - {error}")
        return 1

    try:
        url, token, timeout = load_env(args.env_file)
        client = ZabbixClient(url=url, token=token, timeout=timeout)
        return create_hosts(args.csv, client, dry_run=args.dry_run)
    except (ValueError, requests.RequestException, ZabbixAPIError) as exc:
        print(f"[ERRO] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
