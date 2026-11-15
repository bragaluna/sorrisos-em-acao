# Segurança

## O que não está neste repositório

| Item | Onde fica |
|------|-----------|
| Chave da API do Gemini e acesso OAuth ao Google Sheets | Credenciais do n8n, criptografadas com `N8N_ENCRYPTION_KEY` |
| ID da planilha, ID da aba e ID do grupo do WhatsApp | Arquivo `.env` local, lido pelo workflow via `{{ $env.VAR }}` |
| Mensagens e registros reais | Somente na planilha da campanha |

O export do n8n inclui IDs de credenciais, metadados da instância e, às vezes, dados de teste fixados
(`pinData`). Por isso o workflow passa por `scripts/sanitize_workflows.py` antes de ser versionado:

```bash
# Limpa um export bruto e grava em workflows/
python3 scripts/sanitize_workflows.py exports_brutos/ -o workflows/

# Verifica sem alterar (retorna código 1 se encontrar algo)
python3 scripts/sanitize_workflows.py workflows/ --check
```

O script remove `pinData`, `staticData`, metadados, IDs de credenciais e IDs de webhook. Ele também
troca o ID da planilha, da aba e do grupo por variáveis de ambiente. Depois disso, procura
tokens, chaves de API, e-mails, telefones e links de planilha que tenham sobrado.

O hook em `.githooks/pre-commit` executa essa verificação a cada commit:

```bash
git config core.hooksPath .githooks
```

## Riscos considerados

| Risco | Medida |
|-------|--------|
| Vazamento de segredos no repositório | Credenciais só no n8n, IDs no `.env`, sanitização e hook de pre-commit |
| Mensagens de fora da campanha acionando o fluxo | Filtro pelo ID do grupo |
| Prompt injection (mensagem tentando mudar o comportamento do modelo) | O modelo só extrai dados e não executa ações. A saída é validada contra listas fixas no código |
| Resposta malformada do modelo | `JSON.parse` com tratamento de erro; a execução falha sem gravar nada |
| Injeção de fórmulas na planilha (texto começando com `=`, `+`, `-` ou `@`) | Esses caracteres são removidos do início dos campos de texto |
| Campos de texto muito longos | Doador limitado a 80 caracteres e descrição a 300 |
| Instância do n8n exposta | `docker-compose.yml` publica a porta só em `127.0.0.1`; o acesso externo deve passar por HTTPS |

## Limitações conhecidas

- **O webhook não exige autenticação.** Quem souber a URL pode enviar requisições. O filtro de grupo
  reduz o impacto, mas não autentica a origem. O próximo passo é ativar *Header Auth* no nó Webhook
  com um segredo compartilhado com o provedor do WhatsApp, se ele permitir cabeçalhos personalizados.
- **Itens descartados pela validação não geram aviso.** Um *Error Workflow* ou uma resposta no grupo
  ajudaria a identificar mensagens que não foram registradas.

## Se um segredo for exposto

Apagar o arquivo não basta, porque o valor continua no histórico do git. O procedimento é:
revogar e gerar uma nova chave no serviço correspondente, atualizar a credencial no n8n e,
se necessário, reescrever o histórico.
