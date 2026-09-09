# JoaKinDeX

<p align="center">
  <a href="https://github.com/joasource/JoaKinDeX/actions/workflows/ci.yml"><img src="https://github.com/joasource/JoaKinDeX/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=flat&logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="https://www.sqlite.org/"><img src="https://img.shields.io/badge/Database-SQLite%20WAL-003B57.svg?style=flat&logo=sqlite&logoColor=white" alt="SQLite WAL"></a>
  <a href="https://dublincore.org/"><img src="https://img.shields.io/badge/Standard-Dublin%20Core%20%26%20XMP-6366F1.svg?style=flat" alt="Dublin Core"></a>
  <a href="https://ollama.com/"><img src="https://img.shields.io/badge/LLM-Ollama%20%7C%20OpenAI-FF6F00.svg?style=flat" alt="Ollama / OpenAI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-10B981.svg?style=flat" alt="MIT License"></a>
  <a href="https://github.com/joasource/JoaKinDeX"><img src="https://img.shields.io/badge/GitHub-joasource-181717?style=flat&logo=github" alt="GitHub"></a>
</p>

<p align="center">
  <b>Central Universal de Indexação, Extração Multidomínio, Metadados Forenses e Conferência Documental em Massa</b>
</p>

<p align="center">
  <img src="docs/assets/interface_preview.png" alt="JoaKinDeX - Central Web de Conferência Humana e Indexação Documental" width="900" style="border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.3);">
</p>

> **Criado e desenvolvido por:** **Joaquim Ferreira Silva Neto** ([joaquimfsneto@gmail.com](mailto:joaquimfsneto@gmail.com)).

**JoaKinDeX** é uma suíte completa em Python composta por uma CLI de alto rendimento (`./joakindex`) e uma Central Web interativa (`./joakindex server`). Projetada para auditar, classificar e extrair dados de grandes acervos documentais multiformato (**PDF, Word DOCX/DOC, ODT, RTF e Imagens**), integrando modelos locais via **Ollama** ou em nuvem via **OpenAI API**, banco relacional embutido com **SQLite WAL mode** e metadados forenses padronizados pelo consórcio **Dublin Core & Adobe XMP**.

---

## ✨ Principais Funcionalidades

- **Classificação Multidomínio Inteligente**:
  - **Acadêmico**: Diplomas, Certificados, Históricos, Declarações, TCCs, Monografias, Conteúdos Programáticos.
  - **Financeiro & Bancário**: Comprovantes de Transferência PIX (chave, E2E ID, autenticação, bancos de origem/destino), boletos e recibos.
  - **Empresarial & Profissional**: Comprovantes de Situação Cadastral (CNPJ), Contratos Sociais, certidões da Receita Federal, CNAE e razão social.
  - **Dossiês Multipáginas**: Detecção automática de múltiplos documentos agregados em um único arquivo, com navegação por páginas independentes.
- **Metadados Forenses Dublin Core & XMP Padronizados**:
  - Extração profunda de metadados embutidos (`dc:creator`, `dc:title`, `dc:subject`, `creator_tool`, `producer`, `date`, `modified`, `keywords`).
  - Indexação em tempo real para busca inteligente por software gerador (*LibreOffice, Word, Canva, CamScanner*) ou autor original.
  - Card dedicado na Ficha Técnica com exportação JSON em um clique.
- **Mosaico de Miniaturas HD (Paperless-style)**:
  - Visualização em galeria visual de alta resolução (720px) com paginação fluida, ordenação cronológica/alfabética e acesso direto ao card do documento.
  - Gerador assíncrono multithread em segundo plano com cache local para carregamento instantâneo.
- **Banco de Dados Relacional SQLite com WAL Mode**:
  - Alta performance transacional ACID, sem bloqueios de leitura/escrita e tolerante a interrupções forçadas.
  - Espelhamento atômico automático para arquivos estruturados `joakindex.json` e relatórios legíveis `joakindex.txt`.
- **OCR Multimodal Híbrido com LLM**:
  - Renderização vetorial em alta resolução (`pypdfium2`) para documentos digitalizados ou escaneados.
  - Re-análise pontual sob demanda disparada diretamente pela interface web.
- **Interface Web Split-Screen de Conferência Humana**:
  - Tela dividida com documento original (PDF / Imagem / Word) à esquerda e formulário auditável à direita.
  - Aprovação rápida com teclado (`Ctrl + Enter`), busca inteligente sem acentos e filtros cruzados.
- **Exportação Analítica Pronta para Word, BI e Petições**:
  - Cópia instantânea de campos individuais ou Ficha Completa formatada em Rich Text (Visual Law) para petições.
  - Painel de Business Intelligence (BI) com gráficos dinâmicos (`Chart.js`), rankings e métricas de integridade.
  - Exportação completa em planilhas CSV com cabeçalhos normalizados.
- **Acesso Remoto Seguro via Cloudflare Tunnel (Docker)**:
  - Suporte pronto via `docker-compose.yml` para expor o servidor com certificado SSL/HTTPS e acesso remoto protegido.

---

## 📁 Estrutura do Repositório

```text
JoaKinDeX/
├── joakindex               # Executável CLI (Linux/macOS)
├── joakindex.py            # Código-fonte principal em Python
├── db_manager.py           # Gerenciador de Banco de Dados SQLite WAL
├── config_manager.py       # Gerenciador de configurações persistentes
├── normalizador_instituicoes.py # Normalizador inteligente de instituições
├── joakindex_server.py     # Servidor HTTP / Central Web de conferência e lote
├── iniciar_servidor.sh     # Script para iniciar o servidor web
├── visualizador.html       # Interface web com PDF, formulário e BI
├── docker-compose.yml      # Container Cloudflare Tunnel (acesso remoto HTTPS)
├── .env.example            # Exemplo de configuração do token da Cloudflare
├── requirements.txt        # Dependências Python (pip)
├── environment.yml         # Arquivo de especificação do ambiente Conda
└── README.md               # Documentação do projeto
```

---

## 🚀 Instalação e Preparação

### 1. Clonar o Repositório
```bash
git clone https://github.com/joasource/JoaKinDeX.git
cd JoaKinDeX
```

### 2. Criar e Ativar Ambiente Virtual

#### Opção A: Utilizando Conda (Recomendado)

Você pode configurar o ambiente completo com **Python 3.10** e todas as dependências de três formas:

**1. Comando único via arquivo `environment.yml`:**
```bash
conda env create -f environment.yml
conda activate pdf-classifier
```

**2. Passo a passo manual no terminal:**
```bash
# Cria o ambiente com a versão inicial recomendada do Python (3.10)
conda create -n pdf-classifier python=3.10 -y

# Ativa o ambiente
conda activate pdf-classifier

# Instala todas as dependências requeridas ou pacote em modo editável (PEP 517/621):
pip install -e .
# (ou alternativamente: pip install -r requirements.txt)
```

**3. Instalação direta em linha única (sem dependência de arquivos locais):**
```bash
conda create -n pdf-classifier python=3.10 -y && conda run -n pdf-classifier pip install -e .
```

#### Opção B: Utilizando Python venv padrão

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---


## 💻 Como Usar

### 1. Modo Interativo no Console (Recomendado)

Ao executar o comando sem argumentos, o **menu interativo** é aberto no terminal para guiar a configuração:

```bash
./joakindex
```

O menu permite configurar facilmente:
- 📁 **Pasta de PDFs**: sugere a pasta padrão e contabiliza quantos arquivos PDF existem no caminho informado.
- 📄 **Pasta de saída**: onde serão gravados os relatórios consolidados e individuais.
- 🤖 **Provedor de IA**: alterna facilmente entre **Ollama** e **OpenAI**.
- 🧠 **Modelo de IA**: auto-detecta de forma inteligente o ambiente do Ollama ativo (**Nativo sem Docker**, **Container Oficial Ollama Puro** ou **Container Open-WebUI**) e lista todos os modelos baixados com tamanho e parâmetros, ou sugere `gpt-4o-mini` para OpenAI.
- ⚡ **Concorrência**: ajusta o número de threads simultâneas para acelerar o processamento.
- 🔍 **OCR Multimodal**: opção para ativar ou desativar leitura visual em PDFs escaneados ou com erros de CPF/Tipo.
- ⚙️ **Estratégia**: escolher entre modo incremental (apenas novos/pendentes), reprocessar quem precisa de OCR ou reprocessar tudo do zero.
- 📋 **Resumo da Execução**: exibe todas as opções selecionadas para confirmação antes de iniciar.

---

### 2. Execução Direta por Linha de Comando (CLI)

Se você informar os parâmetros na chamada do comando, ele executa **diretamente**, sem abrir o menu interativo:

#### Com Ollama (Padrão):
```bash
# Execução direta com pasta personalizada:
./joakindex -i ./meus_pdfs -o ./saida

# Especificando outro modelo:
./joakindex -i ./meus_pdfs -o ./saida -m llama3
```

#### Com a API da OpenAI (Paralelismo em Nuvem):

A chave da OpenAI pode ser fornecida de **4 formas simples**:

1. **Direto no Menu Interativo**: Ao escolher a opção `2) OpenAI`, o menu solicita a chave e a máscara com segurança se já existir no ambiente.
2. **Via Linha de Comando (CLI)** usando o parâmetro `-k` ou `--openai-key`:
   ```bash
   ./joakindex -i ./meus_pdfs -o ./saida -p openai -m gpt-4o-mini -k "sk-proj-sua-chave" -w 4
   ```
3. **No arquivo `.env`** (recomendado para persistência):
   Basta criar um arquivo `.env` na raiz do projeto:
   ```env
   OPENAI_API_KEY=sk-proj-sua-chave-aqui
   ```
4. **Via variável de ambiente no terminal**:
   ```bash
   export OPENAI_API_KEY="sk-proj-sua-chave-aqui"
   ./joakindex -i ./meus_pdfs -o ./saida -p openai -m gpt-4o-mini -w 4
   ```

#### Forçar Menu Interativo ou Modo Batch:
```bash
# Força a abertura do menu interativo (usando os parâmetros passados como valor inicial):
./joakindex -i ./meus_pdfs --prompt

# Modo silencioso/batch (executa sem perguntas interativas):
./joakindex -y
```

---

### 3. Parâmetros da Linha de Comando

| Parâmetro | Descrição | Valor Padrão |
|---|---|---|
| `-i`, `--input` | Caminho do diretório de PDFs ou arquivo único | `./pdf` |
| `-o`, `--output-dir` | Diretório onde os relatórios serão salvos | `./saida` |
| `-p`, `--provider` | Provedor de IA (`ollama` ou `openai`) | `ollama` |
| `-m`, `--model` | Nome do modelo (`gemma4:e4b`, `gpt-4o-mini`, etc.) | Auto-detecta / padrão do provedor |
| `-k`, `--key`, `--openai-key` | Chave de API da OpenAI (lê de `OPENAI_API_KEY` ou `.env`) | `None` |
| `--openai-base-url`, `--base-url` | URL base personalizada para OpenAI (Groq, OpenRouter, vLLM) | `None` |
| `--docker` | Nome do container Docker do Ollama | Auto-detecta (`open-webui`) |
| `--ollama-url` | URL da API HTTP do Ollama | `http://localhost:11434` |
| `-w`, `--workers` | Número de threads concorrentes | `1` (Ollama) / `4+` (OpenAI) |
| `--max-pages` | Máximo de páginas a ler por documento | `4` |
| `-f`, `--force` | Força o reprocessamento de todos os PDFs | `False` |
| `--skip-ocr` | Desativa tentativas de OCR via LLM | `False` |
| `--reprocess-ocr` | Reprocessa apenas quem precisa de OCR | `False` |
| `--no-individual` | Não gera arquivos JSON/TXT individuais por MD5 | `False` |
| `--prompt`, `--interativo` | Força o menu interativo no console | `False` |
| `-y`, `--no-prompt`, `--batch`| Desativa o menu interativo (modo batch) | `False` |
| `--reset-config`, `--reset` | Restaura todas as opções para os padrões de fábrica neutros | `False` |

---

## 📄 Exemplo de Saída JSON (Dados Fictícios)

Salvo em `saida/joakindex.json`:

```json
[
  {
    "md5": "e4d909c290d0fb1ca068ffaddf22cbd0",
    "data_modificacao": "15/12/2025 14:30:00",
    "data": "15 de dezembro de 2025",
    "beneficiario": "Nome do Aluno Exemplo",
    "cpf": "123.456.789-00",
    "curso": "Bacharelado em Engenharia de Software",
    "natureza_curso": "Graduação / Curso Superior",
    "carga_horaria": "3600 horas",
    "faculdade": "Universidade Exemplo do Brasil",
    "tipo_documento": "Diploma",
    "status": "sucesso",
    "erro": null,
    "processado_em": "2026-01-01T10:00:05"
  }
]
```

## 📄 Exemplo do Relatório TXT Consolidado

Salvo em `saida/joakindex.txt`:

```text
================================================================================
RELATÓRIO CONSOLIDADO DE CLASSIFICAÇÃO DE DIPLOMAS E CERTIFICADOS
Data/Hora de Geração : 01/01/2026 10:00:00
Provedor LLM         : OLLAMA (Modelo: gemma4:e4b)
Total de Documentos  : 1
Classificados com OK : 1
Falhas / Erros       : 0
================================================================================

[1/1] MD5: e4d909c290d0fb1ca068ffaddf22cbd0
  • Status                  : SUCESSO
  • Data da Última Alteração: 15/12/2025 14:30:00
  • Tipo Documento          : Diploma
  • Beneficiário       : Nome do Aluno Exemplo
  • CPF                : 123.456.789-00
  • Curso              : Bacharelado em Engenharia de Software
  • Natureza do Curso  : Graduação / Curso Superior
  • Carga Horária      : 3600 horas
  • Faculdade          : Universidade Exemplo do Brasil
  • Data do Documento  : 15 de dezembro de 2025
--------------------------------------------------------------------------------

================================================================================
FIM DO RELATÓRIO
================================================================================
```

---

## 🖥️ Central Web de Indexação e Conferência Documental

Para iniciar o servidor web e revisar visualmente os documentos originais contra os dados extraídos:

```bash
# Pelo comando integrado JoaKinDeX:
./joakindex server

# Ou pelo script shell:
./iniciar_servidor.sh

# Ou diretamente via Python:
python3 joakindex_server.py
```

### 📁 Escolha de Pastas no Ato da Execução:

1. **Modo Interativo (Console)**:
   Ao executar `./joakindex server` (ou `./iniciar_servidor.sh`) no terminal sem parâmetros, o console solicita interativamente:
   - **Pasta de Documentos**: pressione `ENTER` para aceitar a pasta padrão sugerida (ex: `./pdf` ou o caminho salvo) ou digite o caminho desejado.
   - **Pasta de saída / Base de Dados**: pressione `ENTER` para manter a saída padrão (`./saida/joakindex.json`) ou informe outro arquivo/pasta.
   - **Porta HTTP**: pressione `ENTER` para manter a porta padrão (`8088`) ou informe outra porta.

2. **Direto por Linha de Comando (CLI)**:
   Você também pode definir as pastas diretamente por parâmetros:
   ```bash
   # Indicando pasta de documentos (-i) e pasta/base de dados (-d):
   ./joakindex server -i /caminho/meus_documentos -d /caminho/minha_saida

   # Com aliases e opções avançadas:
   ./joakindex server --docs-dir /caminho/meus_documentos --db ./saida/joakindex.db --port 8089

   # Para forçar o menu interativo mesmo com parâmetros:
   ./joakindex server --prompt

   # Para execução direta sem perguntas (batch):
   ./joakindex server -y
   ```

Acesse no seu navegador:
👉 **`http://localhost:8088`** (ou a porta escolhida)

### ⚙️ Painel Web de Configuração & Processamento em Lote

Você pode gerenciar todas as configurações e disparar classificações em lote diretamente pela interface web, sem precisar abrir o terminal:

- Clique no botão **⚙️ Configuração & Lote** no canto superior direito.
- **Pastas & Arquivos**: Alterne a pasta de entrada de PDFs e a pasta/arquivo de saída com verificação e contadores automáticos.
- **Inteligência Artificial (IA)**:
  - Alternância instantânea entre **Ollama** e **OpenAI**.
  - Detecção automática de containers (**Docker Open-WebUI**, **Docker Oficial**, **Ollama Nativo**) e listagem dinâmica dos modelos baixados (ex: `gemma4:e4b`).
  - Configuração de chave de API da OpenAI (com máscara de segurança e detecção de variáveis de ambiente).
- **Processamento em Lote em Segundo Plano**:
  - Escolha entre Modo **Incremental** (pula os já concluídos), **Reprocessar OCR** ou **Forçar Tudo** (preserva conferências manuais aprovadas).
  - Ajuste de **Workers concorrentes** (threads) e limite de páginas por PDF.
  - **Acompanhamento ao Vivo**: Barra de progresso com porcentagem, cartões de métricas (A Fazer, Concluídos, Sucessos, Falhas), indicação do arquivo atual e terminal de eventos.
  - **Interrupção Segura**: Botão para interromper o lote a qualquer momento gravando o progresso consolidado.
  - **Atualização Automática**: Assim que novos documentos são classificados, a lista lateral é atualizada sem reiniciar o servidor.
  - **Restauração de Fábrica**: Botão para redefinir todas as pastas e parâmetros para os padrões neutros (`./pdf` e `./saida`).

### 📋 Exportação Rápida e Visual Law (Word / Documentação Jurídica)

- **Cópia por Campo**: Ao lado de cada campo extraído (Beneficiário, CPF, RG, Curso, Instituição, etc.), há um botão de cópia rápida para transferir o dado isolado para a área de transferência.
- **Copiar Ficha Completa (Visual Law)**:
  - Localizado no canto inferior direito do painel de dados.
  - Formata os dados em um **card institucional elegante** com callout lateral azul, tipografia executiva (Segoe UI/Calibri) e tabela estruturada.
  - Compatível com colagem direta no **Microsoft Word**, **Google Docs** e **LibreOffice Writer** (preservando estilo, cores e alinhamento).
  - Inclui fallback automático para texto puro limpo caso seja colado no Bloco de Notas ou terminal.

### 🌐 Acesso Remoto Seguro via Cloudflare Tunnel (Docker)

Para acessar o visualizador de outros dispositivos (ou máquinas Windows na rede) com certificado HTTPS e suporte nativo às APIs de área de transferência:

1. Configure o token do seu túnel no arquivo `.env`:
   ```bash
   cp .env.example .env
   # Edite o .env e insira o TUNNEL_TOKEN obtido no Cloudflare Zero Trust
   ```
2. Suba o container do Cloudflare Tunnel:
   ```bash
   docker compose up -d
   ```
3. No painel da Cloudflare (Zero Trust ➔ Networks ➔ Tunnels), aponte o subdomínio desejado (ex: `documentos.seu-dominio.com.br`) para `http://localhost:8088`.

---

## ⌨️ Atalhos na Interface:
- `Seta Esquerda` (`[`): Documento anterior
- `Seta Direita` (`]`): Próximo documento
- `Ctrl + Enter`: Aprovar conferência e avançar automaticamente
- `Ctrl + S`: Salvar edições manuais
- **Botão Exportar**: Baixa o JSON revisado e auditado

---

## 🛡️ Licença e Autor

Desenvolvido por **Joaquim Ferreira Silva Neto** ([@joasource](https://github.com/joasource) | [joaquimfsneto@gmail.com](mailto:joaquimfsneto@gmail.com)).

Projeto: **JoaKinDeX** (`joakindex`).

Distribuído sob a licença MIT. Consulte o arquivo [`LICENSE`](LICENSE) para obter mais detalhes.
