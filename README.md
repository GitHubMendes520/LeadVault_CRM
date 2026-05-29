# LeadVault CRM MVP

CRM operacional para distribuir leads entre root, gerentes e brokers.

## Rodar local

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

Abra:

```text
http://127.0.0.1:8000
```

## Variaveis de ambiente

Copie `.env.example` para `.env` e ajuste:

```bash
DATABASE_URL=postgresql://user:password@host:5432/leadvault_crm
ROOT_KEY=sua-chave-root
ROOT_USERNAME=root
ROOT_PASSWORD=sua-senha-root
ROOT_FULL_NAME=Administrador LeadVault
```

## Deploy Railway

1. Suba este projeto para um repositorio GitHub.
2. No Railway, crie um projeto novo.
3. Adicione um servico PostgreSQL.
4. Adicione um servico pelo GitHub apontando para este repositorio.
5. Nas variaveis do servico web, defina `DATABASE_URL` usando a URL do PostgreSQL do Railway.
6. Defina `ROOT_KEY` com uma chave privada sua.
7. Defina `ROOT_USERNAME`, `ROOT_PASSWORD` e `ROOT_FULL_NAME`.
8. O comando de start ja esta em `railway.toml`.

Depois do deploy, abra a URL publica do Railway e entre com o root criado automaticamente no primeiro start.

## Importar leads para o banco online

Depois que o PostgreSQL da Railway estiver criado, copie a `DATABASE_URL` dele e rode no seu Mac:

```bash
cd backend
source venv/bin/activate
DATABASE_URL="cole-a-url-postgres-da-railway" python scripts/import_leadvault_matrix.py
```

Isso envia os dados do `LeadVault_Matrix` para o banco online. Depois entre como root, crie brokers/gerentes e distribua leads por quantidade, segmento e pais.

## Fluxo para usar com o time

1. Root entra no sistema.
2. Root cria usuarios `GERENTE` ou `BROKER`.
3. Root importa ou limpa leads do banco.
4. Root distribui leads para brokers por segmento, pais e quantidade.
5. Broker entra com o proprio usuario e ve apenas os leads dele.
6. Gerente pode ajudar na operacao, mas somente root exclui usuarios.
