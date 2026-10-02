"""Pruebas de los servicios de voz local (src/desktop/voice.py).

Reglas de la Constitución:
- P3: determinismo (la detección solo verifica importaciones).
- S2/E5: nunca se contactan servicios de voz remotos.
- Degradación elegante: sin motor, la respuesta es explícita.
"""

import pytest

from src.desktop.voice import CapacidadesVoz, VozLocal, detectar_capacidades


def test_detectar_capacidades_devuelve_estructura_valida():
    capacidades = detectar_capacidades()
    assert isinstance(capacidades, CapacidadesVoz)
    assert isinstance(capacidades.sintesis, bool)
    assert isinstance(capacidades.reconocimiento, bool)


def test_deteccion_es_coherente():
    capacidades = detectar_capacidades()
    if capacidades.sintesis:
        assert capacidades.motor_sintesis is not None
    if capacidades.reconocimiento:
        assert capacidades.motor_reconocimiento is not None
    if not capacidades.reconocimiento:
        assert capacidades.motivo_reconocimiento is not None


def test_deteccion_es_determinista():
    assert detectar_capacidades() == detectar_capacidades()


def test_habla_se_degrada_sin_motor(monkeypatch):
    voz = VozLocal()
    monkeypatch.setattr(
        voz,
        "capacidades",
        CapacidadesVoz(sintesis=False, reconocimiento=False),
    )
    assert voz.hablar("hola") is False


def test_escuchar_se_degrada_sin_motor(monkeypatch):
    voz = VozLocal()
    monkeypatch.setattr(
        voz,
        "capacidades",
        CapacidadesVoz(sintesis=False, reconocimiento=False),
    )
    assert voz.escuchar() is None


def test_escuchar_explica_el_motivo_al_degradarse():
    voz = VozLocal()
    if not voz.capacidades.reconocimiento:
        assert voz.capacidades.motivo_reconocimiento
