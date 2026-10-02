# Motor HPR — Escritorio Local

Motor de seguridad HPR (Arquitectura Híbrida): aplicación nativa de
escritorio en Python con CustomTkinter, conectada directamente al núcleo
determinista HPR. Ejecución 100% local: sin Streamlit, sin navegador web
y sin servicios remotos (Constitución HPR, reglas E1, S2 y E5).

## Ejecución oficial

**Doble clic en `ejecutar.bat`** (o desde la consola):

```bat
ejecutar.bat
```

El lanzador:

1. Fija el directorio de trabajo en la carpeta del proyecto (`%~dp0`),
   independientemente de dónde se invoque.
2. Localiza y activa el entorno virtual (`..\.venv` en la raíz del
   repositorio, con respaldo en `.\.venv` si el proyecto se reubica).
3. Arranca la aplicación con `python -m src.desktop`.
4. En caso de error, muestra el código de salida y mantiene la consola
   abierta (`pause`) para su diagnóstico.

> **Nota de ruta:** el entorno virtual reside en la raíz del repositorio
> (`motor HPR\.venv`), **un nivel por encima** de este script
> (`motor HPR\HPR\`). Por eso el lanzador activa `..\.venv`, no `.venv`.

## Ejecución manual

```powershell
cd "C:\Users\USUARIO\Desktop\motor HPR\HPR"
..\.venv\Scripts\activate
python -m src.desktop
```

## Instalación del entorno (primera vez)

```powershell
cd "C:\Users\USUARIO\Desktop\motor HPR"
python -m venv .venv
.venv\Scripts\python -m pip install -r HPR\requirements.txt
```

## Estructura del proyecto

| Ruta | Función |
| --- | --- |
| `ejecutar.bat` | Lanzador oficial de la aplicación de escritorio |
| `src/desktop/` | Aplicación de escritorio (UI, agente de chat, voz) |
| `src/desktop/assets/hpr.ico` | Escudo oficial: icono de la ventana nativa |
| `src/desktop/assets/hpr_logo.png` | Logotipo de la cabecera de la aplicación |
| `src/core/`, `src/models/` | Núcleo determinista y contratos de dominio |
| `boveda y vitacoras/` | Base de conocimiento local (soberanía S1) |
| `requirements.txt` / `requirements.lock` | Dependencias con pin exacto (D3) |
| `docs/constitution.md` | Constitución del proyecto (reglas S/E/D/P) |

## Voz local

- **Síntesis (TTS):** `pyttsx3` sobre SAPI5 (Windows), 100% offline.
- **Reconocimiento (STT):** CMU Sphinx, offline. Si `pocketsphinx` no
  dispone de rueda para la versión de Python en uso, la entrada de voz
  se degrada con aviso explícito — **nunca** recurre a servicios remotos
  (reglas S2 y E5).

## Pruebas

```powershell
cd "C:\Users\USUARIO\Desktop\motor HPR\HPR"
..\.venv\Scripts\python -m pytest
```
