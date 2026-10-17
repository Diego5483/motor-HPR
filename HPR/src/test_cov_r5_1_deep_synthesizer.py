"""Cobertura R5.1 (P5.6) — DeepSynthesizer: extracción, narrativa y expansión contextual.

Cierra las brechas de cobertura de ``src/core/deep_synthesizer.py`` (núcleo vivo;
alcance oficial de P5 ratificado en ``docs/alcance-formal-cobertura-p5-nucleo-vivo.md``)
SIN tocar ``src/``.

Rutas cubiertas:
- ``procesar_resultados`` · activación de la expansión contextual (ruta viva desde
  ``main.py:544`` y ``core/verified_reasoning.py:242``).
- Extractores: ``_construir_corpus``, ``_extraer_hallazgos``, ``_extraer_arquitecturas``,
  ``_extraer_tecnologias``, ``_extraer_metricas``, ``_inferir_entidad_metrica``,
  ``_extraer_metricas_agrupadas``.
- Narrativa: ``_generar_analisis``, ``_generar_narrativa_entidad``,
  ``_formatear_metricas_narrativa``, ``_generar_narrativa_metricas_globales``,
  ``_buscar_consenso``, ``_generar_conclusiones``, ``_generar_advertencias``.
- Expansión: ``_es_consulta_altamente_tecnica``, ``_extraer_entidades_hallazgo``,
  ``_generar_expansion_contextual``, ``_generar_contexto_arquitectural``,
  ``_analizar_tradeoffs``, ``_analizar_interacciones``,
  ``_generar_implicaciones_practicas``, ``_identificar_gotchas``,
  ``_generar_referencias_autorizadas``, ``_generar_informe_con_expansion``.

Reglas aplicadas (Constitución HPR):
- P1: cada rama se fija con aserciones sobre el valor devuelto, no con inspección manual.
- P2: ``pytest`` estándar; contenido de entrada literal (sin fixtures externos).
- P3: determinismo estricto — sin red, sin ``time.sleep``, sin azar, sin depender del orden.
- P4: se atacan los casos negativos (sin hallazgos, sin métricas, sin trade-offs, una sola fuente).
- P7: no mutan — el módulo no escribe en la bóveda ni en datos reales.

NOTA DE HONESTIDAD (hallazgos H5, registrados, NO corregidos aquí):
``_extraer_metricas_agrupadas`` y ``_generar_informe_con_expansion`` **no tienen
invocador de producción** (comprobado por grep en todo el repositorio). Sus pruebas
de esta suite son **contratos de unidad de código vivo**, no evidencia de
comportamiento en producción; su retiro o reconexión requiere compuerta aparte.
Además, ``_generar_informe_con_expansion`` (línea 1126) pasa ``corpus`` vacío a
``_generar_expansion_contextual`` porque consulta la clave ``"corpus"``, que no
existe en ``metricas_procesamiento`` (la clave real es ``total_caracteres_procesados``).

RESIDUAL DECLARADO (2 ramas parciales, defensivas e inalcanzables por construcción):
- ``497->491`` (``_formatear_metricas_narrativa``): la rama "sin valores" exige una
  métrica agrupada sin dígitos, pero sólo se agrupan descripciones cuyo match
  ``(\\d+)\\s*(\\w+)`` ya tuvo éxito (línea 483), luego ``valores`` nunca queda vacío.
- ``531->525`` (``_generar_narrativa_metricas_globales``): ``metricas_texto`` no puede
  ser vacío cuando el grupo tiene ≥2 métricas, por la misma razón anterior.
Se miden y se declaran; cubrirlas exigiría un doble del formateador (verde artificial).
"""

import sys
from pathlib import Path

import pytest

# Convención del proyecto (ver run.py y test_etapa_r2.py): HPR/ y HPR/src/ en path.
_HPR_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _HPR_DIR / "src"
for _path in (str(_HPR_DIR), str(_SRC_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src.core.deep_synthesizer import (  # noqa: E402
    DeepSynthesizer,
    HallazgoTecnico,
    crear_deep_synthesizer,
)


# ===========================================================================
# Utilidades deterministas
# ===========================================================================

def _synth(min_confianza: float = 0.2) -> DeepSynthesizer:
    """Sintetizador nuevo por prueba (sin estado compartido entre casos)."""
    return DeepSynthesizer(min_confianza=min_confianza)


def h(
    tipo: str,
    descripcion: str,
    fuente: str = "hpr_corpus",
    confianza: float = 0.7,
    evidencia: str = "evidencia literal del corpus",
) -> HallazgoTecnico:
    """Construye un hallazgo tipado (doble de datos, no de comportamiento)."""
    return HallazgoTecnico(
        tipo=tipo,
        descripcion=descripcion,
        fuente=fuente,
        confianza=confianza,
        evidencia=evidencia,
    )


#: Corpus técnico real del dominio HPR (ARM/seguridad) — tres fuentes distintas.
_FUENTE_A = (
    "La arquitectura ARMv9 implementa MTE (Memory Tagging Extension) para seguridad de memoria "
    "y CCA (Confidential Compute Architecture) para aislamiento de cargas confidenciales. "
    "El procesador Cortex-X2 soporta 2.5 GHz de frecuencia sostenida y 64 GB de ancho de banda. "
    "La MMU y el TLB gestionan la jerarquía de memoria con cache L2 y L3 compartida. "
    "El consumo del SoC es: 15 W con litografía de 5 nm y latencia de 30 ms. "
    "SVE2 permite procesamiento vectorial escalable y mejora el rendimiento del throughput."
)
_FUENTE_B = (
    "ARMv9.2 incluye PAC, BTI y GCS para integridad de flujo de control y aislamiento de punteros. "
    "La arquitectura aarch64 mantiene compatibilidad con ARMv8 en el procesador Neoverse V2. "
    "El escalado vectorial SVE2 ofrece 8 GB de ancho de banda por núcleo y 2.0 GHz base. "
    "RISC-V RVV 1.0 aporta capacidad vectorial con 4096 MB de memoria vectorial y 3.0 GHz."
)
_FUENTE_C = (
    "El rendimiento del sistema depende de la jerarquía de memoria y de la seguridad por aislamiento. "
    "MTE añade overhead de marcas y el rendimiento depende del modo síncrono frente al asíncrono. "
    "CCA necesita complejidad de firmware para realm management y el área del núcleo con SVE2 aumenta. "
    "La frecuencia de 3.0 GHz con 5 nm y 12 % de mejora térmica definen el perfil de consumo. "
    "El procesador Neoverse V2 ofrece capacidades de servidor con ancho de banda de memoria ampliado."
)

#: Consulta altamente técnica (activa la expansión contextual: score ≥ 8).
_QUERY_TECNICA = "análisis de arquitectura ARMv9: MTE, CCA y SVE2 con métricas de rendimiento"


def _resultados_tecnicos() -> list:
    """Tres resultados con contenido real y fuentes distintas."""
    return [
        {"titulo": "ARMv9", "url": "local://a", "fuente": "arm_docs",
         "contenido_completo": _FUENTE_A, "relevancia": 0.9},
        {"titulo": "ARMv9.2", "url": "local://b", "fuente": "vendor_spec",
         "contenido_completo": _FUENTE_B, "relevancia": 0.8},
        {"titulo": "Análisis", "url": "local://c", "fuente": "analisis_tecnico",
         "contenido_completo": _FUENTE_C, "relevancia": 0.7},
    ]


# ===========================================================================
# A · procesar_resultados sobre contenido real (ruta viva)
# ===========================================================================

def test_procesar_resultados_activa_expansion_contextual() -> None:
    """Consulta técnica con entidades y métricas -> expansión profunda activada."""
    informe = _synth().procesar_resultados(_QUERY_TECNICA, _resultados_tecnicos())

    assert informe.metricas_procesamiento["expansion_contextual_activada"] is True
    assert "Expansión Contextual Profunda" in informe.analisis_detallado
    assert informe.metricas_procesamiento["total_resultados"] == 3
    assert informe.metricas_procesamiento["hallazgos_extraidos"] >= 10
    assert informe.metricas_procesamiento["fuentes_unicas"] == 3


def test_procesar_resultados_con_solo_snippet_no_falla() -> None:
    """Resultado sin contenido_completo -> se usa el snippet como corpus."""
    resultados = [
        {"fuente": "solo_snippet",
         "snippet": "La arquitectura ARMv9 soporta MTE para seguridad de memoria y aislamiento."},
        {"fuente": "muy_corto", "contenido_completo": "corto"},
    ]
    informe = _synth().procesar_resultados("resumen", resultados)

    assert informe.metricas_procesamiento["total_caracteres_procesados"] > 0
    assert informe.metricas_procesamiento["total_resultados"] == 2


def test_procesar_resultados_sin_hallazgos_no_inventa_informe() -> None:
    """Sin hallazgos no se emite encabezado forense (G.1) ni análisis fabricado."""
    informe = _synth().procesar_resultados(
        "consulta", [{"fuente": "x", "contenido_completo": "texto insuficiente"}]
    )

    assert informe.introduccion == ""
    assert informe.hallazgos_tecnicos == []
    assert informe.metricas_procesamiento["expansion_contextual_activada"] is False
    assert "No se pudo generar análisis técnico" in informe.analisis_detallado


def test_procesar_resultados_advertencia_por_auditoria_baja() -> None:
    """Evaluación global CONFIANZA_BAJA -> advertencia de auditoría HPR."""
    informe = _synth().procesar_resultados(
        "resumen ARMv9",
        _resultados_tecnicos(),
        evaluacion_global={"nivel_confianza": "CONFIANZA_BAJA"},
    )

    assert any("Auditoría HPR: CONFIANZA_BAJA" in a for a in informe.advertencias)


# ===========================================================================
# B · Extracción (unidades directas)
# ===========================================================================

def test_construir_corpus_prioriza_contenido_y_cae_a_snippet() -> None:
    """contenido_completo tiene prioridad; snippet es el respaldo; sin campos no entra."""
    corpus = _synth()._construir_corpus([
        {"fuente": "a", "contenido_completo": "completo A"},
        {"fuente": "b", "snippet": "snippet B"},
        {"fuente": "c"},
    ])

    assert "[FUENTE: a]" in corpus and "completo A" in corpus
    assert "[FUENTE: b]" in corpus and "snippet B" in corpus
    assert "FUENTE: c" not in corpus


def test_extraer_hallazgos_ignora_texto_corto() -> None:
    """Texto por debajo del umbral (50 chars) se descarta sin extraer nada."""
    hallazgos = _synth()._extraer_hallazgos("x", [{"fuente": "f", "contenido_completo": "corto"}])

    assert hallazgos == []


def test_extraer_arquitecturas_reconoce_armv9() -> None:
    """Patrón de arquitectura -> hallazgo tipo 'arquitectura' con evidencia."""
    hallazgos = _synth()._extraer_arquitecturas(
        "La arquitectura ARMv9 amplía el conjunto de instrucciones aarch64.", "f"
    )

    assert {x.tipo for x in hallazgos} == {"arquitectura"}
    assert "Arquitectura mencionada: ARMv9" in [x.descripcion for x in hallazgos]
    assert all(x.confianza == 0.8 for x in hallazgos)
    assert all(x.evidencia for x in hallazgos)


def test_extraer_tecnologias_reconoce_mte() -> None:
    """Patrón de tecnología -> hallazgo tipo 'caracteristica'."""
    hallazgos = _synth()._extraer_tecnologias(
        "MTE y CCA son extensiones de seguridad de ARMv9 con soporte de hardware.", "f"
    )

    tipos = {x.tipo for x in hallazgos}
    assert tipos == {"caracteristica"}
    assert any("MTE" in x.descripcion for x in hallazgos)


def test_extraer_metricas_con_entidad_conocida() -> None:
    """Métrica con entidad conocida en contexto -> descripción con la entidad."""
    hallazgos = _synth()._extraer_metricas("El MTE alcanza 2.5 GHz en modo sostenido.", "f")

    assert len(hallazgos) == 1
    assert hallazgos[0].tipo == "metrica"
    assert hallazgos[0].descripcion == "MTE presenta 2.5 GHz"
    assert hallazgos[0].confianza == 0.65


def test_extraer_metricas_sin_entidad_usa_descripcion_generica() -> None:
    """Métrica sin entidad asociada -> descripción genérica y confianza menor."""
    hallazgos = _synth()._extraer_metricas("El consumo es: 15 W del presupuesto.", "f")

    assert len(hallazgos) == 1
    assert hallazgos[0].descripcion == "Métrica: 15 W"
    assert hallazgos[0].confianza == 0.55


@pytest.mark.parametrize(
    "contexto, valor, unidad, esperado",
    [
        ("El rendimiento de MTE es notable", "2.5", "GHz", "MTE"),
        ("memoria de 24 GB", "24", "GB", "memoria"),
        ("sin entidades reconocibles", "7", "nm", None),
    ],
)
def test_inferir_entidad_metrica(contexto: str, valor: str, unidad: str, esperado) -> None:
    """Entidad conocida > patrón 'X de Y' > None (sin inventar entidad)."""
    assert _synth()._inferir_entidad_metrica(contexto, valor, unidad) == esperado


def test_extraer_metricas_agrupadas_por_entidad() -> None:
    """Agrupa métricas por entidad inferida usando la clave 'General' como respaldo.

    Contrato de unidad: ``_extraer_metricas_agrupadas`` no tiene invocador de
    producción (hallazgo H5); se fija su contrato, no su uso.
    """
    agrupadas = _synth()._extraer_metricas_agrupadas(
        "El MTE alcanza 2.5 GHz y el consumo es: 15 W.", "f"
    )

    assert set(agrupadas) <= {"MTE", "General"}
    assert "MTE" in agrupadas
    assert agrupadas["MTE"][0]["valor"] == "2.5"
    assert agrupadas["MTE"][0]["unidad"] == "GHz"
    assert "contexto" in agrupadas["MTE"][0]


# ===========================================================================
# C · _generar_analisis y consenso
# ===========================================================================

def test_generar_analisis_incluye_metricas_globales_por_entidad() -> None:
    """Entidad con ≥2 métricas -> sección de especificaciones cuantitativas."""
    hallazgos = [
        h("metrica", "MTE presenta 2.5 GHz"),
        h("metrica", "MTE presenta 64 GB"),
    ]
    analisis = _synth()._generar_analisis("armv9", hallazgos, "corpus")

    assert "### MTE" in analisis
    assert "### Especificaciones Cuantitativas Integradas" in analisis
    assert "MTE: mte presenta 2.5 ghz y mte presenta 64 gb" in analisis


def test_generar_analisis_con_consenso_entre_fuentes() -> None:
    """Misma descripción en ≥2 fuentes -> sección de consenso con el número de fuentes."""
    hallazgos = [
        h("caracteristica", "Tecnología/Característica: MTE", "fuente_1"),
        h("caracteristica", "Tecnología/Característica: MTE", "fuente_2"),
    ]
    analisis = _synth()._generar_analisis("armv9", hallazgos, "corpus")

    assert "### Consenso entre Fuentes" in analisis
    assert "Confirmado en 2 fuentes" in analisis


# ===========================================================================
# D · _generar_narrativa_entidad
# ===========================================================================

def test_narrativa_entidad_sin_hallazgos() -> None:
    """Entidad sin especificaciones -> se declara la mención, sin inventar detalle."""
    texto = _synth()._generar_narrativa_entidad("MTE", [])

    assert texto == "La entidad MTE fue mencionada pero sin especificaciones técnicas detalladas."


def test_narrativa_entidad_abre_con_caracteristicas() -> None:
    """Con características -> apertura 'incorpora ...'."""
    texto = _synth()._generar_narrativa_entidad(
        "MTE", [h("caracteristica", "Tecnología/Característica: MTE")]
    )

    assert texto.startswith("MTE incorpora MTE")


def test_narrativa_entidad_abre_con_arquitectura_si_no_hay_caracteristicas() -> None:
    """Sin características pero con arquitectura -> apertura 'se basa en la arquitectura'."""
    texto = _synth()._generar_narrativa_entidad(
        "ARMv9", [h("arquitectura", "Arquitectura mencionada: ARMv9")]
    )

    assert texto.startswith("ARMv9 se basa en la arquitectura ARMv9")


def test_narrativa_entidad_solo_descripcion_base() -> None:
    """Sin características ni arquitecturas -> se usa el nombre de la entidad a secas."""
    texto = _synth()._generar_narrativa_entidad("MTE", [h("metrica", "métrica sin números")])

    assert texto == "MTE"


def test_narrativa_entidad_integra_specs_metricas_y_versiones() -> None:
    """Con especificación, métricas y versión -> los tres fragmentos en orden."""
    texto = _synth()._generar_narrativa_entidad("MTE", [
        h("especificacion", "El MTE soporta etiquetas de memoria"),
        h("metrica", "MTE presenta 2.5 GHz"),
        h("version", "Versión detectada: 9.2"),
    ])

    assert "implementando el mte soporta etiquetas de memoria." in texto
    assert "Sus especificaciones clave incluyen mte presenta 2.5 ghz." in texto
    assert "Se identifican versiones: 9.2." in texto


# ===========================================================================
# E · _formatear_metricas_narrativa
# ===========================================================================

def test_formatear_metricas_vacio() -> None:
    """Sin métricas -> cadena vacía."""
    assert _synth()._formatear_metricas_narrativa([]) == ""


def test_formatear_metricas_sin_numeros() -> None:
    """Métricas sin dígitos -> no se genera texto (no se inventa unidad)."""
    assert _synth()._formatear_metricas_narrativa([h("metrica", "sin números aquí")]) == ""


def test_formatear_metricas_una_unidad() -> None:
    """Una sola unidad -> se devuelve tal cual, en minúsculas."""
    texto = _synth()._formatear_metricas_narrativa([h("metrica", "MTE presenta 2.5 GHz")])

    assert texto == "mte presenta 2.5 ghz"


def test_formatear_metricas_dos_unidades() -> None:
    """Dos unidades distintas -> unidas con 'y'."""
    texto = _synth()._formatear_metricas_narrativa([
        h("metrica", "MTE presenta 2.5 GHz"),
        h("metrica", "MTE presenta 64 GB"),
    ])

    assert texto == "mte presenta 2.5 ghz y mte presenta 64 gb"


def test_formatear_metricas_tres_unidades() -> None:
    """Tres o más unidades -> coma entre todas menos la última."""
    texto = _synth()._formatear_metricas_narrativa([
        h("metrica", "MTE presenta 2.5 GHz"),
        h("metrica", "MTE presenta 64 GB"),
        h("metrica", "MTE presenta 15 W"),
    ])

    assert texto == "mte presenta 2.5 ghz, mte presenta 64 gb y mte presenta 15 w"


def test_formatear_metricas_misma_unidad_multiples() -> None:
    """Varias métricas de la misma unidad -> lista de valores + '(múltiples configuraciones)'."""
    texto = _synth()._formatear_metricas_narrativa([
        h("metrica", "MTE presenta 2.5 GHz"),
        h("metrica", "MTE presenta 3.0 GHz"),
    ])

    assert texto == "2.5, 3.0 GHz (múltiples configuraciones)"


# ===========================================================================
# F · _generar_narrativa_metricas_globales
# ===========================================================================

def test_narrativa_metricas_globales_sin_metricas() -> None:
    """Sin hallazgos de tipo métrica -> cadena vacía."""
    assert _synth()._generar_narrativa_metricas_globales([h("version", "Versión detectada: 1.0")]) == ""


def test_narrativa_metricas_globales_solo_general() -> None:
    """Métricas sin entidad (clave 'General') -> se omiten, sin inventar agrupación."""
    hallazgos = [h("metrica", "Métrica: 2.5 GHz"), h("metrica", "Métrica: 64 GB")]

    assert _synth()._generar_narrativa_metricas_globales(hallazgos) == ""


def test_narrativa_metricas_globales_por_entidad() -> None:
    """Entidad con ≥2 métricas -> frase 'Las configuraciones técnicas destacadas son: ...'."""
    hallazgos = [
        h("metrica", "MTE presenta 2.5 GHz"),
        h("metrica", "MTE presenta 64 GB"),
        h("metrica", "CCA presenta 3.0 GHz"),
        h("metrica", "CCA presenta 128 GB"),
    ]
    texto = _synth()._generar_narrativa_metricas_globales(hallazgos)

    assert texto.startswith("Las configuraciones técnicas destacadas son: ")
    assert "MTE: " in texto and "CCA: " in texto
    assert texto.endswith(".")


# ===========================================================================
# G · _generar_conclusiones
# ===========================================================================

def test_conclusiones_con_arquitectura_y_perfil_cuantitativo() -> None:
    """Arquitectura + métricas -> conclusiones de arquitectura y unidad dominante."""
    hallazgos = [
        h("arquitectura", "Arquitectura mencionada: ARMv9", confianza=0.8),
        h("metrica", "MTE presenta 2.5 GHz"),
        h("metrica", "MTE presenta 3.0 GHz"),
    ]
    conclusiones = _synth()._generar_conclusiones("armv9", hallazgos)

    assert any("La arquitectura principal identificada es ARMv9" in c for c in conclusiones)
    assert any("dominado por métricas de GHz (2 referencias)" in c for c in conclusiones)
    assert any("centrado en rendimiento" in c for c in conclusiones)


def test_conclusiones_caracteristica_sin_prefijo_dos_puntos() -> None:
    """Característica sin ': ' -> el nombre completo entra en las capacidades."""
    hallazgos = [h("caracteristica", "Característica de seguridad MTE")]

    conclusiones = _synth()._generar_conclusiones("armv9", hallazgos)

    assert any("Característica de seguridad MTE" in c for c in conclusiones)


def test_conclusiones_con_tres_fuentes_destaca_diversidad() -> None:
    """Hallazgos de ≥3 fuentes -> conclusión de diversidad y validación cruzada."""
    hallazgos = [
        h("caracteristica", "Tecnología/Característica: MTE", "f1"),
        h("caracteristica", "Tecnología/Característica: CCA", "f2"),
        h("caracteristica", "Tecnología/Característica: SVE2", "f3"),
    ]

    conclusiones = _synth()._generar_conclusiones("armv9", hallazgos)

    assert any("La diversidad de fuentes (3)" in c for c in conclusiones)


# ===========================================================================
# H · _es_consulta_altamente_tecnica / _extraer_entidades_hallazgo
# ===========================================================================

def test_consulta_altamente_tecnica_por_terminos_y_hallazgos() -> None:
    """Query con términos de profundidad y hallazgos ricos -> activa expansión."""
    hallazgos = [
        h("caracteristica", "Tecnología/Característica: MTE"),
        h("caracteristica", "Tecnología/Característica: CCA"),
        h("metrica", "MTE presenta 2.5 GHz"),
        h("especificacion", "El MTE soporta etiquetas de memoria con aislamiento"),
    ]

    assert _synth()._es_consulta_altamente_tecnica(_QUERY_TECNICA, hallazgos) is True


def test_consulta_no_tecnica_no_activa_expansion() -> None:
    """Query coloquial sin hallazgos -> score 0, sin expansión."""
    assert _synth()._es_consulta_altamente_tecnica("saludos cordiales", []) is False


def test_extraer_entidades_hallazgo_reconoce_entidad_conocida() -> None:
    """Descripción con entidad conocida -> se devuelve en minúsculas."""
    entidades = _synth()._extraer_entidades_hallazgo(h("caracteristica", "Tecnología: MTE"))

    assert entidades == ["mte"]


# ===========================================================================
# I · _generar_expansion_contextual y sus analizadores
# ===========================================================================

def _hallazgos_expansion() -> list:
    """Hallazgos ricos (ARMv9 + MTE + CCA + SVE2) para la expansión contextual."""
    return [
        h("arquitectura", "Arquitectura mencionada: ARMv9", "arm_docs", 0.8,
          "ARMv9 incorpora MTE, CCA y SVE2 para seguridad y vectorización"),
        h("caracteristica", "Tecnología/Característica: MTE", "arm_docs"),
        h("caracteristica", "Tecnología/Característica: CCA", "arm_docs"),
        h("caracteristica", "Tecnología/Característica: SVE2", "arm_docs"),
        h("especificacion",
          "El procesador Cortex-X2 soporta 2.5 GHz de frecuencia y 64 GB de ancho de banda",
          "arm_docs"),
        h("especificacion",
          "La arquitectura ARMv9 ofrece 3.0 GHz en modo turbo sostenido",
          "arm_docs"),
        h("metrica", "MTE presenta 2.5 GHz", "arm_docs"),
        h("metrica", "MTE presenta 3.0 GHz", "arm_docs"),
        h("metrica", "MTE presenta 64 GB", "arm_docs"),
        h("version", "Versión detectada: 9.2", "arm_docs"),
    ]


#: Corpus con las palabras clave de los analizadores (trade-offs e interacciones).
_CORPUS_EXPANSION = (
    "MTE CCA SVE2 ARMv9 memoria cache MMU TLB seguridad aislamiento rendimiento "
    "área complejidad consumo potencia compatibilidad"
)


def test_expansion_contextual_sin_hallazgos() -> None:
    """Sin hallazgos -> expansión vacía (no se fabrica sección)."""
    assert _synth()._generar_expansion_contextual("x", [], "corpus") == ""


def test_expansion_contextual_completa() -> None:
    """Expansión completa: arquitectura, trade-offs, interacciones, implicaciones, gotchas y refs."""
    hallazgos = _hallazgos_expansion()
    texto = _synth()._generar_expansion_contextual(_QUERY_TECNICA, hallazgos, _CORPUS_EXPANSION)

    assert texto.startswith("## Expansión Contextual Profunda")
    assert "### 1. Contexto Arquitectural y Evolutivo" in texto
    assert "**ARMv9**:" in texto
    assert "### 2. Trade-offs de Diseño y Decisiones Técnicas" in texto
    assert "MTE añade overhead de 2-5%" in texto
    assert "### 3. Interacción entre Componentes del Sistema" in texto
    assert "MTE y CCA son complementarias" in texto
    assert "### 4. Implicaciones Prácticas para Desarrolladores e Ingenieros" in texto
    assert "**MTE**: Habilitar MTE en allocadores" in texto
    assert "### 5. Puntos de Atención y Consideraciones Críticas" in texto
    assert "MTE requiere TBI (Top Byte Ignored) habilitado" in texto
    assert "### 6. Referencias Autoritativas y Profundización" in texto
    assert "ARM Architecture Reference Manual ARMv9-A" in texto


def test_expansion_contextual_sin_pares_de_tradeoff_usa_frase_generica() -> None:
    """Specs sin pares reconocidos -> sección 2 con la frase genérica de compromiso."""
    hallazgos = [
        h("caracteristica", "Tecnología/Característica: ZZZ", "f_uno"),
        h("metrica", "Métrica: 0.5 GB", "f_dos"),
    ]
    texto = _synth()._generar_expansion_contextual("consulta", hallazgos, "contenido neutro")

    assert "### 1. Contexto Arquitectural" not in texto
    assert "### 2. Trade-offs de Diseño y Decisiones Técnicas" in texto
    assert "equilibrar rendimiento, seguridad y eficiencia" in texto
    assert "### 5. Puntos de Atención" not in texto
    assert "### 6. Referencias Autoritativas" in texto


def test_contexto_arquitectural_desconocido_sin_evidencia() -> None:
    """Entidad fuera del mapa y sin evidencia -> frase genérica sin cita."""
    texto = _synth()._generar_contexto_arquitectural(
        "EntidadX", h("arquitectura", "x", evidencia=""), "corpus"
    )

    assert texto == "**EntidadX**: EntidadX es una arquitectura tecnológica relevante en el dominio consultado."
    assert "Según la fuente" not in texto


def test_analizar_tradeoffs_incluye_generico_por_metricas() -> None:
    """Specs con unidades cuantitativas (≥2) -> trade-off genérico de rendimiento."""
    specs = [
        h("especificacion", "El procesador soporta 2.5 GHz y 64 GB de ancho de banda"),
        h("especificacion", "La arquitectura ofrece 3.0 GHz de frecuencia turbo"),
    ]
    tradeoffs = _synth()._analizar_tradeoffs(specs, {}, "corpus neutro")

    assert any("coexistencia de alta frecuencia" in t for t in tradeoffs)


def test_analizar_interacciones_jerarquia_de_memoria() -> None:
    """Corpus con 'memoria' + 'cache' -> interacción de jerarquía de memoria."""
    interacciones = _synth()._analizar_interacciones(
        {"MTE": [h("caracteristica", "x")]}, [], "memoria cache y MMU"
    )

    assert any("Jerarquía de memoria" in i for i in interacciones)


def test_identificar_gotchas_sin_version_ni_fuente_unica() -> None:
    """Sin hallazgos de versión y con ≥2 fuentes -> no se añaden gotchas genéricos."""
    hallazgos = [
        h("caracteristica", "Tecnología/Característica: MTE", "f1"),
        h("caracteristica", "Tecnología/Característica: CCA", "f2"),
    ]
    gotchas = _synth()._identificar_gotchas({"MTE": [hallazgos[0]]}, hallazgos, "corpus")

    assert gotchas
    assert all("Versiones reportadas" not in g for g in gotchas)
    assert all("marketing vs silicon real" not in g for g in gotchas)


def test_identificar_gotchas_por_version_y_fuente_unica() -> None:
    """Hallazgo de versión + una sola fuente -> ambos gotchas genéricos presentes."""
    hallazgos = [h("version", "Versión detectada: 9.2", "f_unica")]
    gotchas = _synth()._identificar_gotchas({}, hallazgos, "corpus")

    assert any("Versiones reportadas pueden ser de pre-lanzamiento" in g for g in gotchas)
    assert any("marketing vs silicon real" in g for g in gotchas)


def test_referencias_autorizadas_omite_fuente_desconocida() -> None:
    """Fuentes 'desconocida'/'duckduckgo_mock' no generan referencia de fuente."""
    referencias = _synth()._generar_referencias_autorizadas(
        {"MTE": [h("caracteristica", "x")]},
        [h("caracteristica", "Tecnología/Característica: MTE", "desconocida"),
         h("caracteristica", "Tecnología/Característica: CCA", "duckduckgo_mock")],
    )

    assert referencias
    assert all("Fuente consultada: desconocida" not in r for r in referencias)
    assert all("duckduckgo_mock" not in r for r in referencias)


# ===========================================================================
# J · _generar_informe_con_expansion y factoría
# ===========================================================================

def test_generar_informe_con_expansion_en_query_tecnica() -> None:
    """Versión extendida: añade la expansión al análisis e informa su longitud.

    Contrato de unidad: ``_generar_informe_con_expansion`` no tiene invocador de
    producción (hallazgo H5). Se comprueba además su comportamiento real tal cual
    está (el corpus llega vacío por la clave inexistente 'corpus' — hallazgo H5b,
    no corregido aquí).
    """
    informe = _synth()._generar_informe_con_expansion(_QUERY_TECNICA, _resultados_tecnicos())

    assert informe.metricas_procesamiento["expansion_contextual_activada"] is True
    assert informe.metricas_procesamiento["longitud_expansion"] > 0
    assert "Expansión Contextual Profunda" in informe.analisis_detallado
    assert informe.conclusiones


def test_generar_informe_con_expansion_en_query_simple() -> None:
    """Consulta simple sin hallazgos -> devuelve el informe base sin expansión."""
    informe = _synth()._generar_informe_con_expansion(
        "saludos", [{"fuente": "x", "contenido_completo": "texto insuficiente"}]
    )

    assert informe.metricas_procesamiento["expansion_contextual_activada"] is False
    assert "longitud_expansion" not in informe.metricas_procesamiento
    assert "Expansión Contextual Profunda" not in informe.analisis_detallado


def test_crear_deep_synthesizer_propaga_umbral() -> None:
    """La factoría devuelve una instancia con el umbral solicitado."""
    sintetizador = crear_deep_synthesizer(min_confianza=0.5)

    assert isinstance(sintetizador, DeepSynthesizer)
    assert sintetizador.min_confianza == 0.5


# ===========================================================================
# K · Ramas límite (verbos sin contenido, métricas sin dígitos, dos fuentes)
# ===========================================================================

def test_extraer_especificaciones_exige_contenido_tecnico() -> None:
    """Verbo de especificación sin término técnico en la oración -> no se extrae."""
    hallazgos = _synth()._extraer_especificaciones(
        "El sistema ofrece resultados rapidos de forma general para el usuario final.", "f"
    )

    assert hallazgos == []


def test_narrativa_metricas_globales_omite_entidad_con_una_sola_metrica() -> None:
    """Entidad con una única métrica no entra en la frase global (exige ≥2)."""
    hallazgos = [
        h("metrica", "MTE presenta 2.5 GHz"),
        h("metrica", "MTE presenta 64 GB"),
        h("metrica", "CCA presenta 3.0 GHz"),
    ]
    texto = _synth()._generar_narrativa_metricas_globales(hallazgos)

    assert "MTE: " in texto
    assert "CCA" not in texto


def test_conclusiones_sin_verbo_reconocible_ni_digitos() -> None:
    """Spec sin verbo y métrica sin dígitos -> sin conclusiones de capacidad ni cuantitativas."""
    hallazgos = [
        h("especificacion", "Analisis tecnico sin verbo reconocible"),
        h("metrica", "metrica sin numeros"),
    ]
    conclusiones = _synth()._generar_conclusiones("x", hallazgos)

    assert not any("capacidades funcionales" in c for c in conclusiones)
    assert not any("perfil cuantitativo" in c for c in conclusiones)
    assert conclusiones


def test_conclusiones_con_dos_fuentes_no_afirma_diversidad_ni_sesgo() -> None:
    """Exactamente 2 fuentes -> ni diversidad (≥3) ni aviso de fuente única (=1)."""
    hallazgos = [
        h("caracteristica", "Tecnología/Característica: MTE", "f1"),
        h("caracteristica", "Tecnología/Característica: CCA", "f2"),
    ]
    conclusiones = _synth()._generar_conclusiones("armv9", hallazgos)

    assert not any("diversidad de fuentes" in c for c in conclusiones)
    assert not any("una sola fuente única" in c for c in conclusiones)


def test_expansion_solo_con_arquitectura_omite_tradeoffs() -> None:
    """Sin especificaciones ni características -> no hay sección de trade-offs."""
    hallazgos = [h("arquitectura", "Arquitectura mencionada: ARMv9", "f", 0.8, "ARMv9")]
    texto = _synth()._generar_expansion_contextual("armv9", hallazgos, "corpus")

    assert "### 1. Contexto Arquitectural" in texto
    assert "### 2. Trade-offs" not in texto
