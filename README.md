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
MATRIX_IMPORT_TOKEN=token-seguro-para-integracao-matrix
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
7. Defina `MATRIX_IMPORT_TOKEN` com um token seguro para integracao automatica.
8. Defina `ROOT_USERNAME`, `ROOT_PASSWORD` e `ROOT_FULL_NAME`.
9. O comando de start ja esta em `railway.toml`.

Depois do deploy, abra a URL publica do Railway e entre com o root criado automaticamente no primeiro start.

## Importar leads para o banco online

Depois que o PostgreSQL da Railway estiver criado, copie a `DATABASE_URL` dele e rode no seu Mac:

```bash
cd backend
source venv/bin/activate
DATABASE_URL="cole-a-url-postgres-da-railway" python scripts/import_leadvault_matrix.py
```

Isso envia os dados do `LeadVault_Matrix` para o banco online. Depois entre como root, crie brokers/gerentes e distribua leads por quantidade, segmento e pais.

## Endpoint de importacao automatica (LeadVault Matrix)

Endpoint:

```text
POST /imports/matrix/leads
Authorization: Bearer <MATRIX_IMPORT_TOKEN>
Content-Type: application/json
```

Exemplo de payload:

```json
{
  "source": "LeadVault_Matrix",
  "batch_id": "mx-2026-06-03-001",
  "sent_at": "2026-06-03T18:00:00Z",
  "records": [
    {
      "nome": "Empresa ABC",
      "contato": "+52 998 123 4567",
      "email": "ventas@empresaabc.mx",
      "site": "https://empresaabc.mx",
      "endereco": "Cancun, Quintana Roo",
      "nicho": "HOTEL",
      "pais": "MX",
      "score": 92
    }
  ]
}
```

Campos aceitos por registro:

- `nome`
- `contato`
- `email`
- `site`
- `endereco`
- `nicho`
- `pais`
- `score`
- `instagram`
- `linkedin`
- `facebook`
- `redes_sociais`
- `observacoes`
- `valor_negocio`

Logs de importacao:

- `GET /imports/jobs`
- `GET /imports/jobs/{job_id}`

Regras atuais:

- `batch_id` nao pode repetir para a mesma origem.
- O endpoint aceita ate `20.000` registros por chamada.
- Deduplicacao considera email, telefone e dominio/site normalizado.

## Fluxo para usar com o time

1. Root entra no sistema.
2. Root cria usuarios `GERENTE` ou `BROKER`.
3. Root importa ou limpa leads do banco.
4. Root distribui leads para brokers por segmento, pais e quantidade.
5. Broker entra com o proprio usuario e ve apenas os leads dele.
6. Gerente pode ajudar na operacao, mas somente root exclui usuarios.
