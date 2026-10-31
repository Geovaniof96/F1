"""Configuração da aplicação lida de variáveis de ambiente (prefixo ``F1_``)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parâmetros da aplicação.

    Attributes:
        api_base_url: URL base da API OpenF1.
        data_dir: Diretório raiz onde os dados são gravados.
        request_timeout: Timeout de cada requisição HTTP, em segundos.
        max_retries: Número máximo de novas tentativas em erros transitórios.
        min_interval_seconds: Intervalo mínimo entre requisições, em segundos.
        log_level: Nível de log (``DEBUG``, ``INFO``, ...).
    """

    model_config = SettingsConfigDict(env_prefix="F1_", env_file=".env", extra="ignore")

    api_base_url: str = "https://api.openf1.org/v1"
    data_dir: Path = Path("data")
    request_timeout: float = 30
    max_retries: int = 3
    min_interval_seconds: float = 0.5
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Retorna as configurações (instância única, imutável).

    Returns:
        Instância de `Settings` carregada do ambiente.
    """
    return Settings()
