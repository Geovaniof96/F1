# OpenF1 API — Resumo

Documentação resumida da API pública [OpenF1](https://openf1.org/docs/#api-endpoints), que fornece dados em tempo real e históricos da Fórmula 1 (não é um projeto oficial, sem associação com a Formula 1 ou empresas relacionadas).

## Visão geral

- **URL base:** `https://api.openf1.org/v1/`
- **Formato de resposta:** JSON por padrão; CSV adicionando `?csv=true` na query string
- **Autenticação:**
  - Dados históricos (a partir de 2023) são livres e não exigem autenticação
  - Dados em tempo real exigem assinatura paga
- **Datas:** aceita múltiplos formatos (ISO 8601, formatos US/EU, linguagem natural), compatíveis com o parser `dateutil.parser.parse` do Python

## Filtros e recursos de consulta

- **Filtragem por atributo:** qualquer campo não-array pode ser filtrado via query string usando operadores `=`, `>`, `<`, `>=`, `<=`
  - Ex: `?session_key=9222&speed>=300`
- **Filtragem por data:** suporte a intervalos usando parâmetros como `date_start` e `date_end`
- **Palavra-chave `latest`:** muitos parâmetros aceitam o valor `latest` para retornar o dado mais recente disponível

## Endpoints

| Endpoint | Descrição | Principais parâmetros |
|---|---|---|
| `/car_data` | Telemetria do carro (~3.7 Hz) | `driver_number`, `session_key`, `speed`, `brake`, `throttle`, `rpm`, `n_gear`, `drs` |
| `/championship_drivers` | Classificação de pilotos no campeonato (apenas sessões de corrida) | `session_key`, `driver_number`, pontos/posição |
| `/championship_teams` | Classificação de equipes no campeonato (apenas sessões de corrida) | `session_key`, `team_name`, pontos/posição |
| `/drivers` | Informações dos pilotos em uma sessão | `driver_number`, `session_key`, equipe/nome |
| `/intervals` | Diferença de tempo entre pilotos (~4s, apenas corridas) | `session_key`, `interval`, `gap_to_leader` |
| `/laps` | Dados de voltas individuais | `session_key`, `driver_number`, `lap_number`, tempos de setor |
| `/location` | Posição do carro na pista (~3.7 Hz) | `session_key`, `driver_number`, `date`, coordenadas x/y/z |
| `/meetings` | Informações de fim de semana de GP/teste (atualização diária) | `year`, `country_name`, circuito/data |
| `/overtakes` | Eventos de ultrapassagem em corridas (pode estar incompleto) | `session_key`, `overtaking_driver_number`, `overtaken_driver_number` |
| `/pit` | Dados de pit stop | `session_key`, `stop_duration`, `lane_duration` |
| `/position` | Mudanças de posição do piloto durante a sessão | `meeting_key`, `driver_number`, `position` |
| `/race_control` | Status da sessão, incidentes, bandeiras, safety car | `flag`, `driver_number`, `date`, `category` |
| `/sessions` | Informações de treinos, qualifying, sprint e corrida (atualização diária) | `country_name`, `session_name`, `year`, datas |
| `/session_result` | Classificação final após uma sessão | `session_key`, `position`, resultados de corrida/qualifying |
| `/starting_grid` | Posições do grid de largada | `session_key`, `position` |
| `/stints` | Stints individuais de pilotagem | `session_key`, `tyre_age_at_start`, `compound` |
| `/team_radio` | Comunicações de rádio (disponibilidade limitada, reduzida a partir de 2026) | `session_key`, `driver_number`, `recording_url` |
| `/weather` | Condições da pista (~1 min) | `meeting_key`, `track_temperature`, `wind_direction` |

## Notas finais

- Frequências de atualização variam bastante por endpoint: dados de telemetria/posição são quase em tempo real (~3.7 Hz), clima atualiza a cada ~1 min, e `meetings`/`sessions` atualizam diariamente.
- `/overtakes` pode conter dados incompletos.
- `/team_radio` tem disponibilidade limitada e tende a diminuir a partir de 2026.
- Projeto não-oficial, mantido pela comunidade — não possui vínculo com a Formula 1 ou suas empresas.
