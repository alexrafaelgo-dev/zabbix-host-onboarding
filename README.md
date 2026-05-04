# Zabbix Host Onboarding Automation

Estrutura inicial para cadastro em lote de hosts no **Zabbix 7.4.x** via API, com inventário em CSV versionado no Git e validação prévia.

## Estrutura

- `inventory/hosts.example.csv`: modelo de inventário.
- `scripts/validate_csv.py`: validação de estrutura e dados do CSV.
- `scripts/create_hosts.py`: criação idempotente de hosts via API do Zabbix.
- `config/example.env`: exemplo de variáveis de ambiente.
- `requirements.txt`: dependências Python.

## Pré-requisitos

- Python 3.10+
- Acesso à API do Zabbix 7.4.7
- Token de API de um usuário com permissões para leitura/criação de hosts, grupos, templates e proxy.

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuração

1. Copie o arquivo de exemplo:

```bash
cp config/example.env .env
```

2. Ajuste os valores em `.env`:
   - `ZABBIX_URL` (ex: `https://zabbix.seudominio.com/api_jsonrpc.php`)
   - `ZABBIX_API_TOKEN`

> Nenhum segredo é hardcoded no código.

## CSV de inventário

Use `inventory/hosts.example.csv` como base e crie seu arquivo, por exemplo `inventory/hosts.csv`.

Campos sugeridos:

- `hostname` (obrigatório)
- `visible_name` (opcional)
- `ip` (opcional, porém obrigatório se `dns` vazio)
- `dns` (opcional, porém obrigatório se `ip` vazio)
- `group` (obrigatório)
- `template` (obrigatório)
- `proxy` (opcional)
- `interface_type` (opcional; padrão: `agent`)
- `port` (opcional; padrão: `10050`)
- `description` (opcional)
- `snmp_version` (obrigatório quando `interface_type=snmp`; suportado: `2`, `2c`, `snmpv2`, `snmpv2c`)
- `snmp_community` (obrigatório quando `interface_type=snmp`)

## Validação do CSV

```bash
python scripts/validate_csv.py --csv inventory/hosts.csv
```

A validação verifica:

- presença de campos obrigatórios;
- hostnames duplicados no CSV;
- formato de IP (quando informado);
- porta numérica e no intervalo válido (1-65535);
- validação específica de SNMP (`snmp_version` e `snmp_community` quando `interface_type=snmp`).

## Dry-run (sem criar no Zabbix)

```bash
python scripts/create_hosts.py --csv inventory/hosts.csv --env-file .env --dry-run
```

## Execução real

```bash
python scripts/create_hosts.py --csv inventory/hosts.csv --env-file .env
```

## Comportamento idempotente

- Se o host já existir (`host` igual ao `hostname` do CSV), o script **não cria duplicado**.
- O script reporta host existente e segue para o próximo item.

## Observações de design

- Este bootstrap cria apenas a interface principal e associação com 1 grupo e 1 template por linha.
- Para SNMP, esta versão implementa SNMPv2 com `details.version=2` e community vinda da coluna `snmp_community`.
- Se você precisar de múltiplos grupos/templates por host, mantenha este desenho simples e evolua com parsing separado (placeholder para evolução futura).
