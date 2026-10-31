from f1.exceptions import F1Error, InvalidRecordError, OpenF1APIError, WriteError


def test_excecoes_herdam_de_f1error() -> None:
    assert issubclass(OpenF1APIError, F1Error)
    assert issubclass(WriteError, F1Error)
    assert issubclass(InvalidRecordError, F1Error)
    assert issubclass(InvalidRecordError, ValueError)
