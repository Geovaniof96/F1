# f1

Dashboard interativo de dados históricos da Fórmula 1, alimentado pela API pública
[OpenF1](https://openf1.org).

O projeto tem duas partes:

1. **Extrator** (`f1-extract`): baixa os dados da OpenF1 e grava um cache local em
   `data/raw/` (JSON bruto) e `data/processed/` (Parquet tratado).
2. **Dashboard** (`f1-dashboard`): app Streamlit que lê o cache e mostra, por sessão:
    - **Resultado**: classificação, tempo, gap, pontos e status (DNF/DNS/DSQ);
    - **Ritmo**: tempo de volta por piloto, na cor da equipe;
    - **Pneus**: estratégia de stints por composto, com os pit stops;
    - **Clima**: temperatura do ar e da pista, umidade e períodos de chuva.

Sessões que ainda não estão no cache podem ser baixadas por um botão no próprio dashboard.

- [Guia de uso](guia.md): instalação, comandos e configuração.
- [Arquitetura](arquitetura.md): módulos, fluxo de dados e partições.
- [Referência da API](api.md): gerada a partir das docstrings.

!!! note
    A OpenF1 é um projeto comunitário, sem vínculo com a Fórmula 1. Os dados históricos
    (a partir de 2023) são abertos e não exigem autenticação.
