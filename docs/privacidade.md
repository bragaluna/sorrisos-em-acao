# Privacidade e dados pessoais

O sistema trata dados de pessoas reais que doam para a campanha. Este documento descreve
quais dados circulam, onde ficam e quais cuidados foram tomados, considerando a LGPD.

## Dados tratados

| Dado | Origem | Armazenado? |
|------|--------|-------------|
| Texto da mensagem | Grupo de WhatsApp da campanha | Não. É processado e descartado |
| Nome do doador | Extraído do texto pelo modelo | Sim, na coluna `Doador` da planilha |
| Itens, quantidades e valores | Extraídos do texto pelo modelo | Sim, na planilha |
| Número de telefone de quem envia | Corpo do webhook | Não. O workflow usa apenas o ID do grupo, para o filtro |

O nome do doador é guardado porque a campanha precisa saber de quem veio cada doação para
agradecer e prestar contas. Quando o nome não aparece na mensagem, o registro fica como
"Anônimo" ou "Não informado".

## Onde os dados passam

1. **Provedor de API do WhatsApp:** entrega a mensagem ao webhook.
2. **n8n:** executa o fluxo. Com `EXECUTIONS_DATA_SAVE_ON_SUCCESS=none`, as execuções bem-sucedidas
   não ficam salvas no histórico, e as demais são apagadas após 72 horas (`EXECUTIONS_DATA_MAX_AGE`).
3. **Google Gemini:** recebe o texto da mensagem para fazer a extração. É um processamento por
   terceiro, sujeito aos termos de uso da API do Google. Esses termos variam conforme o plano contratado.
4. **Google Sheets:** guarda o resultado.

## Cuidados adotados

- **Minimização:** a planilha guarda só o necessário para a gestão das doações. Telefone e texto
  original não são gravados.
- **Acesso restrito:** a planilha deve ser compartilhada apenas com as organizadoras da campanha.
- **Retenção curta no n8n:** o histórico de execuções não guarda o conteúdo das mensagens.
- **Repositório sem dados reais:** os exemplos em `samples/` são fictícios.

## Recomendações para quem for usar

- Avisar os participantes do grupo de que as mensagens sobre doações são processadas automaticamente.
- Definir por quanto tempo a planilha será mantida após o fim da campanha.
- Atender pedidos de remoção de nome diretamente na planilha.
