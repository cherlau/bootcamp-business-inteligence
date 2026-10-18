# Entrega 1: Painel de BI para Assistência Técnica de Celulares

Disciplina: Business Intelligence (Desenvolvimento de Sistemas)

## 1. Integrantes do grupo

- Cherlau
- João

## 2. A empresa

| | |
|---|---|
| **Nome** | Opção Telefonia Celular |
| **O que faz** | Assistência técnica (conserto) e venda de celulares |
| **Onde fica** | Bauru (SP) |
| **Responsável** | Felipe Campos, dono da empresa, que também trabalha como técnico nos consertos |

## 3. O problema

A assistência recebe celulares para conserto, e cada aparelho gera uma **ordem de serviço (OS)**.
Hoje o dono não tem uma visão clara de:

- quantos aparelhos entram e saem;
- quanto tempo os reparos levam;
- quais defeitos são mais comuns;
- quais consertos voltam na garantia;
- quais serviços dão mais dinheiro.

**Objetivo:** criar um painel simples que mostre esses números e ajude o dono a decidir onde
melhorar.

## 4. Os dados

A empresa não liberou os dados reais. Com autorização do professor, usamos uma **base simulada**,
gerada por um script Python com números parecidos com os informados pelo dono: volume diário,
marcas atendidas, defeitos mais comuns, preços e prazos.

- Uma linha por OS, com 12 meses de dados (nov/2025 a out/2026), cerca de 2.500 OS.
- Colunas: número da OS, datas de entrada, conclusão e entrega, marca, modelo, defeito,
  tipo de reparo, técnico, status, valor cobrado e se voltou na garantia.
- A base foi gerada **com erros de propósito**: datas em dois formatos, marcas escritas de jeitos
  diferentes, valores em texto, técnico vazio e linhas duplicadas. Assim, a etapa de limpeza
  dos dados também faz parte do trabalho.

## 5. Indicadores planejados

| Indicador | Como calcular |
|---|---|
| Aparelhos recebidos | Quantidade de OS que entraram no período |
| Aparelhos entregues | Quantidade de OS entregues ao cliente no período |
| Serviços em andamento | OS com status "Em andamento" ou "Aguardando peça" |
| Tempo médio de reparo | Média de dias entre a entrada e a conclusão |
| Taxa de conclusão | OS concluídas ÷ OS recebidas (sem contar as em andamento) |
| Defeitos mais frequentes | Quantidade de OS por defeito |
| Taxa de retorno | OS que voltaram na garantia ÷ OS entregues (por defeito e por técnico) |
| Receita por tipo de reparo | Soma dos valores das OS entregues, por tipo de reparo |
| Ticket médio | Receita ÷ aparelhos entregues |

## 6. Ferramentas

- **Python** (pandas e numpy) para gerar, limpar e analisar os dados.
- **Plotly** para os gráficos.
- **Streamlit** para o painel interativo.
- **GitHub** para versionar o código e publicar o projeto.
