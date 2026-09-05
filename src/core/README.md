# Pipeline de ingesta — Proyecto Expediente

Convierte PDFs de documentos desclasificados en fichas estructuradas (JSON) almacenadas localmente, listas para que los agentes de guion
(vía API cloud) las consumen sin gastar tokens en ruido.

```
PDF crudo -> ¿tiene texto? -> [OCR si no] -> MarkItDown -> Depurador (modelo MLX) -> SQLite + ChromaDB
```

## 1. Instalación (una sola vez)

```bash
# Herramientas de sistema para OCR (solo si vas a necesitar OCR)
brew install tesseract tesseract-lang ocrmypdf

# Entorno Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Descarga el modelo local (una sola vez)

MLX descarga el modelo la primera vez que lo usas y lo cachea localmente.

```bash
# En una terminal aparte, deja esto corriendo mientras usas el pipeline:
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
```

Si tu M3 Pro va lento con 7B, prueba con:
`mlx-community/Llama-3.2-3B-Instruct-4bit`

## 3. Configuración (.env)

El proyecto utiliza `pydantic-settings` para la configuración. Las rutas base (`data/`, `src/`) se detectan automáticamente, pero puedes sobreescribir variables o configuraciones API creando un archivo `.env` en la raíz del proyecto (este archivo está excluido del control de versiones):

```env
# Ejemplo de .env
ANTHROPIC_API_KEY=sk-ant-api03-...
ELEVENLABS_API_KEY=...
# LOCAL_LLM_URL=http://localhost:8080/v1/chat/completions
```

## 4. Uso

```bash
# 1. Coloca tus PDFs en data/docs_raw/
cp ~/Downloads/documentos_foia/*.pdf data/docs_raw/

# 2. Con el servidor MLX corriendo en otra terminal, ejecuta desde la raíz:
python -m src.main
```

## 5. Estructura del proyecto (Clean Architecture)

```
proyecto-expediente/
├── data/                      # Datos generados (ignorado en git)
│     └── knowledge_base/        # SQLite + ChromaDB
│
├── src/                     # Dominio puro — sin dependencias externas
│     ├── core/                  # Dominio puro — sin dependencias externas (incluido en git)
│     │     └── README.md          # This file is updated (as part of unit tests implementation)
│     │         ├── entities.py       # FichaEstructurada (dataclass canónica)
│     │     ├── ports.py            # Interfaces: IPdfInspector, IOcrProcessor, ILLMClient, IDocumentRepository, ISemanticIndex
│     │     └── config/             # Configuración centralizada y validada con pydantic
│     │
│     ├── infrastructure/           # Adaptadores concretos de I/O
│     │     ├── pdf/
│     │     └── llm/
│     │         └── local_llm_client.py
│     │     └── persistence/
│     │         ├── sqlite_repo.py    # SQLite empaquetado para almacenamiento
│     │         └── chroma_repo.py   # ChromaDB base de datos
│     │
│     ├── application/              # Casos de uso
│     │     ├── chunking.py       # Función pura para chunking
│     │     └── ingest_use_case.py # IngestUseCase
│     │
·      prompts/                    # Templates que se pueden expandir
│         └── depurador.md        # Template de depurador
│


├── README.md                # Estructura del proyecto
├── requirements.txt
└── tests/                 # Pruebas automatizadas
```

**Principio clave**: `src/core/` no importa nada de `src/infrastructure/`. Las dependencias apuntan hacia adentro (hacia el dominio).

## 6. Verificar resultados rápido

```bash
sqlite3 data/knowledge_base/expedientes.sqlite "SELECT id, archivo_origen, confiabilidad_extraccion FROM documentos;"
```

## Notas importantes

- **Nada de esto sale a la nube (aún).** El texto crudo, el OCR y la depuración
  corren 100% en tu máquina. Solo cuando conectemos Agentes cloud, se enviará el `resumen_ejecutivo`
   + `fragmentos_clave` ya depurados — no el documento completo.

## 7. Actualizando README.md (implementación de unidades)

```bash
# Crear la actualización de README.md
cat > src/core/README.md << 'EOF'
# Pipeline de ingesta — Proyecto Expediente

Convierte PDFs de documentos desclasificados en fichas estructuradas (JSON) almacenadas localmente, listas para que los agentes de guion
(vía API cloud) las consumen sin gastar tokens en ruido.

```
PDF crudo -> ¿tiene texto? -> [OCR si no] -> MarkItDown -> Depurador (modelo MLX) -> SQLite + ChromaDB
```

## 1. Instalación (una sola vez)

```bash
# Herramientas de sistema para OCR (solo si vas a necesitar OCR)
brew install tesseract tesseract-lang ocrmypdf

# Entorno Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Descarga el modelo localmente (una sola vez)

MLX descarga el modelo la primera vez que lo usas y lo cachea localmente.

```bash
# En una terminal aparte, deja esto corriendo mientras el pipeline se usa:
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
```

## 3. Configuración (.env...)

El proyecto utiliza `pydantic-settings` para la configuración. Las rutas base (`data/`, `src/`) se detectan automáticamente, pero puedes sobreescribir variables o configuraciones API creando un archivo `.env` en la raíz del proyecto (este archivo está excluido del control de versiones).

```env
# Ejemplo de .env
ANTHROPIC_API_KEY=sk-ant-api03-...
ELEVENLABS_API_KEY=...
# LOCAL_LLM_URL=http://localhost:8080/v1/chat/completions
```

## 4. Uso

```bash
# 1. Coloca tus PDFs en data/docs_raw/
cp ~/Downloads/documentos_foia/*.pdf data/docs_raw/

# 2. Con el servidor MLX corriendo en otra terminal, ejecuta desde la raíz:
python -m src.main
```

## 5. Estructura del proyecto (Clean Architecture)

```
proyecto-expediente/
├── data/                      # Datos generados (ignorado en git)
│     └── knowledge_base/        # SQLite + ChromaDB
│
├── src/                     # Dominio puro — sin dependencias externas
│     ├── core/                  # Dominio puro — sin dependencias externas (incluido en git)
│     │     └── README.md          # Esta actualización es parte de las pruebas de unidades
│     │         ├── entities.py        # FichaEstructurada (dataclass canónica)
│     │     ├── ports.py           # Interfaces: IPdfInspector, IOcrProcessor, ILLMClient, IDocumentRepository, ISemanticIndex
│     │     └── config/            # Configuración centralizada y validada con pydantic
│     │
│     ├── infrastructure/        # Adaptadores concretos de I/O
│     │     ├── pdf/
│     │     │     └── pdf_reader.py # Detección de texto y OCR
│     │     └── llm/
│     │         └── local_llm_client.py
│     │     └── persistence/
│     │         ├── sqlite_repo.py    # SQLite empaquetado para almacenamiento
│     │         └── chroma_repo.py   # ChromaDB base de datos
│     │
│     ├── application/              # Casos de uso
│     │     ├── chunking.py       # Función pura para chunking
│     │     └── ingest_use_case.py # IngestUseCase
│     │
│     └── prompts/               # Templates que se pueden expandir
│         └── depurador.md        # Template de depurador
│


├── README.md                # Estructura del proyecto
├── requirements.txt
└── tests/                 # Pruebas automatizadas
```

**Principio clave**: `src/core/` no importa nada de `src/infrastructure/`. Las dependencias apuntan hacia adentro (hacia el dominio).

## 6. Verificar resultados rápido

```bash
sqlite3 data/knowledge_base/expedientes.sqlite "SELECT id, archivo_origen, confiabilidad_extraccion FROM documentos;"
```

## Notas importantes

- **Nada de esto sale a la nube (aún).** El texto crudo, el OCR y la depuración
  corren 100% en tu máquina. Solo cuando conectemos Agentes cloud, se enviará el `resumen_ejecutivo`
   + `fragmentos_clave` ya depurados — no el documento completo.

## 7. Actualizando README.md (implementación de unidades)

```bash
# Crear la actualización de README.md
cat > src/core/README.md << 'EOF'
# Pipeline de ingesta — Proyecto Expediente

Convierte PDFs de documentos desclasificados en fichas estructuradas (JSON) almacenadas localmente, listas para que los agentes de guion
(vía API cloud) las consumen sin gastar tokens en ruido.

```
PDF crudo -> ¿tiene texto? -> [OCR si no] -> MarkItDown -> Depurador (modelo MLX) -> SQLite + ChromaDB
```

## 1. Instalación (una sola vez)

```bash
# Herramientas de sistema para OCR (solo si vas a necesitar OCR)
brew install tesseract tesseract-lang ocrmypdf

# Entorno Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Descarga el modelolocalmente (una sola vez)

MLX descarga el modelo la primera vez que lo usas y lo cachea localmente.

```bash
# En una terminal aparte, deja esto corriendo mientras el pipeline se usa:
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
```

## 3. Configuración (.env...)

El proyecto utiliza `pydantic-settings` para la configuración. Las rutas base (`data/`, `src/`) se detectan automáticamente, pero puedes sobreescribir variables o configuraciones API creando un archivo `.env` en la raíz del proyecto (este archivo está excluido del control de versiones).

```env
# Ejemplo de .env
ANTHROPIC_API_KEY=sk-ant-api03-...
ELEVENLABS_API_KEY=...
# LOCAL_LLM_URL=http://localhost:8080/v1/chat/completions
```

## 4. Uso

```bash
# 1. Coloca tus PDFs en data/docs_raw/
cp ~/Downloads/documentos_foia/*.pdf data/docs_raw/

# 2. Con el servidor MLX corriendo en otra terminal, ejecuta desde la raíz:
python -m src.main
```

## 5. Estructura del proyecto (Clean Architecture)

```
proyecto-expediente/
├── data/                      # Datos generados (ignorado en git)
│     └── knowledge_base/        # SQLite + ChromaDB
│


├── src/                     # Dominio puro — sin dependencias externas
│     ├── core/                  # Dominio puro — sin dependencias externas (incluido en git)
│     │     └── README.md          # This file is updated (as part of unit tests implementation)
│     │         ├── entities.py        # FichaEstructurada (dataclass canónica)
│     │     ├── ports.py           # Interfaces: IPdfInspector, IOcrProcessor, ILLMClient, IDocumentRepository, ISemanticIndex
│     │     └── config/            # Configuración centralizada y validada con pydantic
│     │
│     ├── infrastructure/        # Adaptadores concretos de I/O
│     │     ├── pdf/
│     │     └── llm/
│     │         └── local_llm_client.py
│     │     └── persistence/
│     │         ├── sqlite_repo.py    # SQLite empaquetado para almacenamiento
│     │         └── chroma_repo.py   # ChromaDB base de datos
│     │
│     ├── application/              # Casos de uso
│     │     ├── chunking.py       # Función pura para chunking
│     │     └── ingest_use_case.py # IngestUseCase
│     │


├── README.md                # Estructura del proyecto
├── requirements.txt
└── tests/                 # Pruebas automatizadas
```

**Principio clave**: `src/core/` no importa nada de `src/infrastructure/`. Las dependencias apuntan hacia adentro (hacia el dominio).

## 6. Verificar resultados rápido

```bash
sqlite3 data/knowledge_base/expedientes.sqlite "SELECT id, archivo_origen, confiabilidad_extraccion FROM documentos;"
```

## Notas importantes

- **Nada de esto sale a la nube (aún).** El texto crudo, el OCR y la depuración
  corren 100% en tu máquina. Solo quando conectemos Agentes cloud, se enviará el `resumen_ejecutivo`
   + `fragmentos_clave' ya depurados — no el documento completo.

## 7. Actualizando README.md (implementación de unidades)

```bash
# Crear la actualización de README.md
cat > src/core/README.md << 'EOF'
# Pipeline de ingesta — Proyecto Expediente

Convierte PDFs de documentos desclasificados en fichas estructuradas (JSON) almacenadas localmente, listas para que los agents de guion
(vía API cloud) las consumen sin gastar tokens en ruido.

```
PDF crudo -> ¿tiene texto? -> [OCR si no] -> MarkItDown -> Depurador (modelo MLX) -> SQLite + ChromaDB
```

## 1. Instalación una sola vez

```bash
# Herramientas de sistema para OCR
brew install tesseract
brew install ocrmypdf

# Entorno Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Descargar el modelolocalmente

MLX descarga el modelo la primera vez que lo usas y lo cachea localmente.

```bash
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
```

## 3. Configuración (.env)

El proyecto utiliza `pydantic-settings` para la configuración. Las rutas base (`data/`, `src/`) se detectan automáticamente, pero puedes sobreescribir variables o configuraciones API creando un archivo `.env` en la raíz del proyecto (esta línea está excluida del control de versiones).

```env
# Ejemplo de .env
ANTHROPIC_API_KEY=sk-ant-api03-...
ELEVENLABS_API_KEY=...
# LOCAL_LLM_URL=http://localhost:8080/v1/chat/completions
```

## 4. Uso

```bash
# 1. Coloca tus PDFs en data/docs_raw/
cp ~/Downloads/documentos_foia/*.pdf data/docs_raw/

# 2. Con el servidor MLX corriendo en otra terminal, ejecuta desde la raíz:
python -m src.main
```

## 5. Estructura del proyecto (Clean Architecture)

```
proyecto-expediente/
├── data/                      # Datos generados (ignorado en git)
│     └── knowledge_base/        # SQLite + ChromaDB
│


├── src/                     # Dominio puro — sin dependencias externas
│     ├── core/                  # Dominio puro — sin dependencias externas (incluido en git)
│     │     └── README.md          # This file is updated (as part of unit tests implementation)
│     │         ├── entities.py        # FichaEstructurada (dataclass canónica)
│     │     └── ports.py           # Interfaces: IPdfInspector, IOcrProcessor, ILLMClient, IDocumentRepository, ISemanticIndex
│     │     └── config/            # Configuración centralizada y validada con pydantic
│     │


├── README.md                # Estructura del proyecto
├── requirements.txt
└── tests/                 # Pruebas automatizadas
```

**Principio clave**: `src/core/` no importa nada de `src/infrastructure/`. Las dependencias apuntan hacia adentro (hacia el dominio).

## 6. Verificar resultados rápido

```bash
sqlite3 data/knowledge_base/expedientes.sqlite "SELECT id, archivo_origen, confiabilidad_extraccion FROM documentos;"
```

## Notas importantes

- **Nada de esto sale a la nube (aún).** El texto crudo, el OCR y la depuración
  corren 100% en tu máquina. Solo cuando conectamos Agentes cloud, se enviará el `resumen_ejecutivo`
   + `fragmentos_clAVE' ya depurados — no el documento completo.

## 7. Actualizando README.md (implementación de unidades)

```bash
# Crear la actualización de README.md
cat > src/core/README.md << 'EOF'
# Pipeline de ingesta — Proyecto Expediente

Convierte PDFs de documentos desclasificados en fichas estructuradas (JSON) almacenadas localmente, listas para que los agents de guion
(vía API cloud) las consumen sin gastar tokens en ruido.

```
PDF crudo -> ¿tiene texto? -> [OCR si no] -> MarkItDown -> Depurador (modelo MLX) -> SQLite + ChromaDB
```

## 1. Instalación una sola vez

```bash
# Herramientas de sistema para OCR
brew install tesseract tesseract-lang ocrmypdf

# Entorno Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Descargar el modelolocalmente (una sola vez)

MLX descarga el modelo la primera vez que lo usas y lo cachea localmente.

```bash
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
```

## 3. Configuración (.env...)

El proyecto utiliza `pydantic-settings` para la configuración. Las rutas base (`data/`, `src/`) se detectan automáticamente, pero puedes sobreescribir variables o configuraciones API creando un archivo `.env` en la raíz del proyecto (este línea está excluyente del control de versiones).

```env
# Ejemplo de .env
ANTHROPIC_API_KEY=sk-ant-api03-...
ELEVENLABS_API_KEY=...
# LOCAL_LLM_URL=http://localhost:8080/v1/chat/completions
```

## 4. Uso

```bash
# 1. Coloca tus PDFs en data/docs_raw/
cp ~/Downloads/documentos_foia/*.pdf data/docs_raw/

# 2. Con el servidor MLX corriendo en otra terminal, ejecuta desde la raíz:
python -m src.main
```

## 5. Estructura del proyecto (Clean Architecture)

```
proyecto-expediente/
├── data/                      # Datos generados (ignorado en git)
│     └── knowledge_base/        # SQLite + ChromaDB
│


├── src/                     # Dominio puro — sin dependencias externas
│     ├── core/                  # Dominio puro — sin dependencias externas (incluido en git)
│     │     └── README.md          # This file is updated (as part of unit tests implementation)
│     │         ├── entities.py        # FichaEstructurada (dataclass canónica)
│     │     └── ports.py           # Interfaces: IPdfInspector, IOcrProcessor, ILLMClient, IDocumentRepository, ISemanticIndex
│     │     └── config/            # Configuración centralizada y validada con pydantic
│     │


├── README.md                # Estructura del proyecto
├── requirements.txt
└── tests/                 # Pruebas automatizadas
```

**Principio clave**: `src/core/` no importa nada de `src/infrastructure/`. Las dependencias apuntan hacia adentro (hacia el dominio).

## 6. Verificar resultados rápido

```bash
sqlite3 data/knowledge_base/expedientes.sqlite "SELECT id, archivo_origen, confiabilidad_extraccion FROM documentos;"
```

## Notas importantes

- **Nada de esto sale a la nube (aún).** El texto crudo, el OCR y la depuración
  corren 100% en tu máquina. Solo cuando conectemos Agentes cloud, se enviará el `resumen_ejecutivo`  
   + `fragmentos_clAVE' ya depurados — no el documento completo.

## 7. Actualizando README.md (implementación de unidades)

```bash
# Crear la actualización de README.md
cat > src/core/README.md << 'EOF'
# Pipeline de ingesta — Proyecto Expediente

Convierte PDFs de documentos desclasificados en fichas estructuradas (JSON) almacenadas localmente, listas para que los agents de guion
(vía API cloud) las consumen sin gastar tokens en ruido.

```
PDF crudo -> ¿tiene texto? -> [OCR si no] -> MarkItDown -> Depurador (modelo MLX) -> SQLite + ChromaDB
```

## 1. Instalación una sola vez

```bash
# Herramientas de sistema para OCR
brew install tesseract
brew install ocrmypdf


# Entorno Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Descargar el modelolocalmente (una sola vez)

MLX descarga el modelo la primera vez que lo use y lo cachea localmente.

```bash
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
```

## 3. Configuración (.env...)

El proyecto utiliza `pydantic-settings` para la configuración. Las rutas base (`data/`, `src/`) se detectan automáticamente, pero puedes sobreescribir variables o configuraciones API creando un archivo `.env` en la raíz del proyecto (este line está excluyente del control de versiones).

```env
# Ejemplo de .env
ANTHROPIC_API_KEY=sk-ant-api03-...
ELEVENLABS_API_KEY=...
# LOCAL_LLM_URL=http://localhost:8080/v1/chat/completions
```

## 4. Uso

```bash
# 1. Coloca tus PDFs en data/docs_raw/
cp ~/Downloads/documentos_foia/*.pdf data/docs_raw/

# 2. Con el servidor MLX corriendo en otra terminal, ejecuta desde la raíz:
python -m src.main
```

## 5. Estructura del proyecto (Clean Architecture)

```
proyecto-expediente/
├── data/                      # Datos generados (ignorado en git)
│     └── knowledge_base/        # SQLite + ChromaDB
│


├── src/                     # Dominio puro — sin dependencias externas
│     ├── core/                  # Dominio puro — sin dependencias externas (incluido en git)
│     │     └── README.md          # This file is updated (as part of unit tests implementation)
│     │         ├── entities.py        # FichaEstructurada (dataclass canónica)
│     │     └── ports.py           # Interfaces: IPdfInspector, IOcrProcessor, ILLMClient, IDocumentRepository, ISemanticIndex


├── README.md                # Estructura del proyecto
├── requirements.txt
└── tests/                 # Pruebas automatizadas
```

**Principio clave**: `src/core/` no importa nada de `src/infrastructure/`. Las dependencias apuntan hacia adentro (hacia el dominio).

## 6. Verificar resultados rápido

```bash
sqlite3 data/knowledge_base/expedientes.sqlite "SELECT id, archivo_origen, confiabilidad_extraccion FROM documentos;"
```

## Notas importantes

- **Nada de esto sale a la nube (aún).** El texto crudo, el OCR y la depuración
  corren 100% en tu máquina. Solo cuando conectamos Agentes cloud, se enviará el `resumen_ejecutivo`  
   + `fragmentos_CLAVE' ya depurados — no el documento completo.*

## 7. Actualizando README.md (implementación de unidades)

```bash
# Crear la actualización de README.md
cat > src/core/README.md << 'EOF'
# Pipeline de ingesta — Proyecto Expediente

Convierte PDFs de documentos desclasificados en fichas estructuradas (JSON) almacenadas localmente, listas para que los agents de guion
(vía API cloud) las consumen sin gastar tokens en ruido.

```
PDF crudo -> ¿tiene texto? -> [OCR si no] -> MarkItDown -> Depurador (modelo MLX) -> SQLite + ChromaDB
```

## 1. Instalación una sola vez

```bash
# Herramientas de sistema para OCR
brew install tesseract tesseract-lang ocrmypdf

# Entorno Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Descargar el modelolocalmente (una sola vez)

MLX descarga el modelo la primera vez que lo use y lo cachea localmente.

```bash
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
```

## 3. Configuración (.env...)

El proyecto utiliza `pydantic-settings` para la configuración. Las rutas base (`data/`, `src/`) se detectan automáticamente, pero puedes sobreescribir variables o configuraciones API creando un archivo `.env` en la raíz del proyecto (este línea está excluyente del control de versiones).

```env
# Ejemplo de .env
ANTHROPIC_API_KEY=sk-ant-api03-...
ELEVENLABS_API_KEY=...
# LOCAL_LLM_URL=http://localhost:8080/v1/chat/completions
```

## 4. Uso

```bash
# 1. Coloca tus PDFs en data/docs_raw/
cp ~/Downloads/documentos_foia/*.pdf data/docs_raw/

# 2. Con el servidor MLX corriendo en otra terminal, ejecuta desde la raíz:
python -m src.main
```

## 5. Estructura del proyecto (Clean Architecture)

```
proyecto-expediente/
├── data/                      # Datos generados (ignorado en git)
│     └── knowledge_base/        # SQLite + ChromaDB
│


├── src/                     # Dominio puro — sin dependencias externas
│     ├── core/                  # Dominio puro — sin dependencias externas (incluido en git)
│     │     └── README.md          # This file is updated (as part of unit tests implementation)
│     │         ├── entities.py        # FichaEstructurada (dataclass canónica)
│     │     └── ports.py           # Interfaces: IPdfInspector, IOcrProcessor, ILLMClient, IDocumentRepository, ISemanticIndex
│     │     └── config/            # Configuración centralizada y validada con pydantic
│     │


├── README.md                # Estructura del proyecto
├── requirements.txt
└── tests/                 # Pruebas automatizadas
```

**Principio clave**: `src/core/` no importa nada de `src/infrastructure/`. Las dependencias apuntan hacia adentro (hacia el dominio).

## 6. Verificar resultados rápido

```bash
sqlite3 data/knowledge_base/expedientes.sqlite "SELECT id, archivo_origen, confiabilidad_extraccion FROM documentos;"
```

## Notas importantes

- **Nada de esto sale a la nube (aún).** El texto crudo, el OCR y la depuración
  corren 100% en tu máquina. Solo cuando conectamos Agentes cloud, se enviará el `resumen_ejecutivo`  
   + `fragmentos_CLAVE' ya depurados — no el documento completo.*

## 7. Actualizando README.md (implementación de unidades)

```bash
# Crear la actualización de README.md
cat > src/core/README.md << 'EOF'
# Pipeline de ingesta — Proyecto Expediente

Convierte PDFs de documentos desclasificados en fichas estructurados (JSON) almacenadas localmente, listas para que los agents de guion
(vía API cloud) las consumen sin gastar tokens en ruido.

```
PDF crudo -> ¿tiene texto? -> [OCR si no] -> MarkItDown -> Depurador (modelo MLX) -> SQLite + ChromaDB
```

## 1. Instalación una sola vez

```bash
# Herramientas de sistema para OCR
brew install tesseract
brew install ocrmypdf


# Entorno Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Descargar el modelolocalmente (una sola vez)

MLX descarga el modelo la primera vez que lo use y lo cachea localmente.

```bash
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
```

## 3. Configuración (.env...)

El proyecto utiliza `pydantic-settings` para la configuración. Las rutas base (`data/`, `src/`) se detectan automáticamente, pero puedes sobreescribir variables o configuraciones API creando un archivo `.env` en la raíz del proyecto (este línea está excluyente del control de versiones).

```env
# Ejemplo de .env
ANTHROPIC_API_KEY=sk-ant-api03-...
ELEVENLABS_API_KEY=...
# LOCAL_LLM_URL=http://localhost:8080/v1/chat/completions
```

## 4. Uso

```bash
# 1. Coloca tus PDFs en data/docs_raw/
cp ~/Downloads/documentos_foia/*.pdf data/docs_raw/

# 2. Con el servidor MLX corriendo en otra terminal, ejecuta desde la raíz:
python -m src.main
```

## 5. Estructura del proyecto (Clean Architecture)

```
proyecto-expediente/
├── data/                      # Datos generados (ignorado en git)
│     └── knowledge_base/        # SQLite + ChromaDB


├── src/                     # Dominio puro — sin dependencias externas
│     ├── core/                  # Dominio puro — sin dependencias externas (incluido en git)
│     │     └── README.md          # This file is updated (as part of unit tests implementation)
│     │         ├── entities.py        # FichaEstructurada (dataclass canónica)
│     │     └── ports.py           # Interfaces: IPdfInspector, IOcrProcessor, ILLMClient, IDocumentRepository, ISemanticIndex
│     │     └── config/            # Configuración centralizada y validada con pydantic
│     │


├── README.md                # Estructura del proyecto
├── requirements.txt
└── tests/                 # Pruebas automatizadas
```

**Principio clave**: `src/core/` no importa nada de `src/infrastructure/`. Las dependencias apuntan hacia adentro (hacia el dominio).

## 6. Verificar resultados rápido

```bash
sqlite3 data/knowledge_base/expedientes sqlite "SELECT id, archivo_origen, confiabilidad_extraccion FROM documentos;"

