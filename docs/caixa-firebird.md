# Caixa Firebird

A consulta de Caixa é somente leitura e permanece desativada até que o servidor receba a configuração privada indicada por `CAIXA_FIREBIRD_CONFIG_PATH`. A ativação é uma operação separada: não copie arquivos de diagnóstico nem coloque credenciais no repositório.

O arquivo privado é JSON com `sources` e as seis chaves: `ni1_clinico`, `ni1_contratos`, `sjm_clinico`, `sjm_contratos`, `vilar_clinico` e `vilar_contratos`. Cada fonte informa somente `dsn`, `user`, `password`, e opcionalmente `charset` e `library_path`.

```json
{
  "sources": {
    "ni1_clinico": {
      "dsn": "host:/caminho/privado/base.fdb",
      "user": "usuario_leitura",
      "password": "<segredo-fora-do-repositorio>",
      "charset": "WIN1252",
      "library_path": "/caminho/privado/fbclient.so"
    },
    "ni1_contratos": {
      "dsn": "host:/caminho/privado/ni1-contratos.fdb",
      "user": "usuario_leitura",
      "password": "<segredo-fora-do-repositorio>"
    },
    "sjm_clinico": {
      "dsn": "host:/caminho/privado/sjm-clinico.fdb",
      "user": "usuario_leitura",
      "password": "<segredo-fora-do-repositorio>"
    },
    "sjm_contratos": {
      "dsn": "host:/caminho/privado/sjm-contratos.fdb",
      "user": "usuario_leitura",
      "password": "<segredo-fora-do-repositorio>"
    },
    "vilar_clinico": {
      "dsn": "host:/caminho/privado/vilar-clinico.fdb",
      "user": "usuario_leitura",
      "password": "<segredo-fora-do-repositorio>"
    },
    "vilar_contratos": {
      "dsn": "host:/caminho/privado/vilar-contratos.fdb",
      "user": "usuario_leitura",
      "password": "<segredo-fora-do-repositorio>"
    }
  }
}
```

É necessário instalar `fdb==2.0.4` e disponibilizar a biblioteca cliente Firebird compatível. A transação é configurada como `READ_ONLY`, read committed/rec version e nowait; o serviço também desabilita triggers e garbage collection na conexão. Falhas, configuração ausente ou prazo excedido retornam indisponibilidade sem expor o erro do driver.

`CAIXA_FIREBIRD_TIMEOUT_SECONDS` aceita de 1 a 30, com padrão 15. Cada consulta usa datas nativas, não texto, e não escreve no banco.

## Regras e limites

- Fonte financeira: `CXD555`, classificada por `TIPO` em `CRD013`, com pagamento via `GRUPO_FORMAS_PAGTO` e `GRUPO_FORMA_PAGTO`. `DATMOV` informa abertura/fechamento, sem multiplicar lançamentos por joins.
- Recebimentos são lançamentos `CALCULO = '+'` com valor positivo. Arredonde cada lançamento para centavos antes da soma. O fechamento de código 36, saídas e ajustes não integram recebimentos. Valores sem categoria permanecem em “Não classificado”.
- Categorias dependem do alias e código; não inferir pela descrição. Boleto e cartão online têm rótulos específicos por código quando o grupo é genérico.
- Os valores de Nova Iguaçu foram reconciliados com os dias legíveis 01, 02, 03 e 05/10/2026 da planilha, incluindo 120 pagamentos de manutenção. São João e Vilar ainda exigem homologação com seus relatórios de origem; a conferência técnica dos totais não substitui essa homologação.
- Contratos, vidas (titular e dependentes) e ortos vendidas retornam `null` até comprovar os vínculos de vendas novas. Média e projeção retornam `null` até validar o calendário de segunda a sábado, excluindo feriados por unidade.
- `master` e `Administrador` consultam as três unidades. `Financeiro` e `Gerente` consultam somente a unidade do token. As outras funções recebem 403 antes de abrir a configuração privada.
- Falhas de fonte preservam os subtotais disponíveis. Cada dia indica consulta parcial quando alguma fonte da sua unidade falhou. Indisponibilidade total retorna valores financeiros `null`, nunca zero.
- Limite por fonte/mês: 50.000 lançamentos e 5.000 registros de fechamento. Exceder esses limites deixa a fonte indisponível. Há até três fontes em paralelo por consulta e quatro processos de consulta por worker da API. O prazo inclui a recepção dos dados; o filho próprio é encerrado ao exceder o prazo. Sem cache ou polling automático no navegador.

### Layout do comparativo diário

O comparativo diário consolida as respostas autorizadas pela data. Cada data com movimento é uma coluna, em ordem cronológica; não são criados dias sem resposta. As linhas mostram cada categoria financeira, o total recebido, as manutenções recebidas e a situação do caixa. A tabela não expõe uma coluna de unidade.

Quando a consulta global está parcial, todos os valores do comparativo são subtotais das fontes disponíveis, inclusive nas datas cujas fontes responderam, e a situação indica consulta parcial. Zero é exibido como zero; indisponibilidade permanece distinta de zero. Em telas estreitas, a tabela oferece rolagem horizontal por teclado e mantém a coluna de indicador visível.

### Indicadores aguardando homologação

Na NI1, `EMD101.DT_CADASTRO` com `CLIENTE = S` retornou 4/2/2/2 em 01/02/03/05 de outubro, o que comprova apenas cadastro; ainda falta o elo entre venda, renovação e dependentes. `CRD111` de parcelas não é usado para contar contratos. `MAN001.INICIO_MANUT` retornou 0/2/2/3, divergente da planilha 0/2/2/2. Já os pagamentos `MAN111` coincidem com as manutenções e mantêm a regra financeira atual. Por isso contratos, vidas e ortos permanecem indisponíveis, sem conversão para zero.

## Ativação operacional separada

A publicação do código não ativa a integração. Configure um cliente Firebird permanente e compatível no ambiente da aplicação, sem depender do ambiente privado do Codex. Guarde a configuração fora do Git, com diretório restrito e arquivo acessível somente à conta do serviço (por exemplo, modo 600). As credenciais precisam permitir conexão com triggers desabilitadas e consulta em transação somente leitura. Uma conta que não atenda a esses requisitos falha fechada; não há troca automática de usuário nem criação de permissões.

A ativação exige aprovação explícita para instalação/configuração operacional e eventual restart. Não modifica dados, usuários, permissões ou schema Firebird. A reversão operacional consiste em retirar a variável de configuração e reiniciar somente o serviço afetado, mediante aprovação; a tela voltará a indicar indisponibilidade.
