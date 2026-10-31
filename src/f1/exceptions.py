"""Exceções de domínio do projeto."""


class F1Error(Exception):
    """Erro base do pacote `f1`."""


class OpenF1APIError(F1Error):
    """Falha ao consultar a API OpenF1 após esgotar as tentativas."""


class InvalidRecordError(F1Error, ValueError):
    """Registro sem os campos obrigatórios (ex.: chave primária)."""


class WriteError(F1Error):
    """Falha ao gravar uma partição no destino."""
