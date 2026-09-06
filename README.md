# joaclassificador-pdf

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Ollama](https://img.shields.io/badge/LLM-Ollama%20%7C%20OpenAI-orange.svg)](https://ollama.com/)

**joaclassificador-pdf** é uma ferramenta de linha de comando (CLI) e interface web para **classificação e extração estruturada de diplomas, certificados e documentos acadêmicos em massa**, utilizando modelos locais (**Ollama**) ou em nuvem (**OpenAI API**).

O projeto é focado em privacidade, conformidade e auditoria: identifica os arquivos pelo **Hash MD5** e metadados de sistema, extrai o **CPF do beneficiário**, determina a **natureza acadêmica do curso** e inclui uma interface web interativa com tela dividida (*split-screen*) para **conferência humana lado a lado** com o PDF original.

---

## ✨ Principais Funcionalidades

- **Processamento em Lote**: Processa dezenas ou centenas de documentos PDF com barra de progresso em tempo real (`tqdm`).
- **Foco em Privacidade**: Anonimiza a referência do arquivo utilizando o **Hash MD5** do documento e metadados de criação/modificação.
- **Extração Completa de Metadados**:
  - Nome do Beneficiário / Titular
  - CPF do Beneficiário (validado e formatado `000.000.000-00`)
  - Cédula de Identidade / RG / Registro Geral (com órgão emissor e UF)
  - Nome Oficial do Curso
  - **Natureza do Curso**: *Graduação / Curso Superior*, *Pós-Graduação Lato Sensu (Especialização/MBA)*, *Pós-Graduação Stricto Sensu (Mestrado/Doutorado)*, *Curso Técnico / Profissionalizante*, *Extensão*, etc.
  - Carga Horária Total (horas ou h/aulas)
  - Faculdade ou Universidade Emissora
  - Data de Emissão / Conclusão do Documento
  - Tipo do Documento (*Diploma, Certificado, Histórico, Declaração, Currículo*)
- **Múltiplos Provedores de IA**:
  - **Ollama**: Suporta execução local ou via Docker (`open-webui` / `ollama`), com modelos como `gemma4:e4b`, `llama3`, `mistral`, etc.
  - **OpenAI**: Compatível com modelos como `gpt-4o-mini`, `gpt-4o` ou qualquer endpoint compatível.
- **OCR Multimodal Híbrido com LLM**:
  - Leitura automática de PDFs digitalizados (sem camada textual nativa) via renderização visual (`pypdfium2`).
  - Re-análise inteligente quando detectado CPF com tamanho/sintaxe/dígito inválido ou tipo de documento não identificado.
  - Botão no visualizador para disparar OCR visual sob demanda com um clique.
- **Relatórios Duplos (JSON & TXT)**:
  - Arquivo consolidado `classificacao_diplomas.json`.
  - Arquivo consolidado `classificacao_diplomas.txt` para leitura humana.
  - Arquivos individuais por MD5 na pasta `saida/individuais/`.
- **Interface Web de Conferência Humana**:
  - Visualização lado a lado (PDF original vs Formulário JSON).
  - Edição direta de qualquer campo e filtros cruzados por Natureza e Tipo.
  - Re-análise via OCR multimodal diretamente pela interface.
  - Aprovação rápida com atalho de teclado (`Ctrl + Enter`).
  - Atualização do JSON e TXT em tempo real.

---

## 📁 Estrutura do Repositório

```text
joaclassificador-pdf/
├── joaclassificador-pdf        # Executável CLI (Linux/macOS)
├── joaclassificador-pdf.py     # Código-fonte principal em Python
├── servidor_visualizador.py    # Servidor HTTP leve para conferência
├── iniciar_visualizador.sh     # Script para iniciar a interface web
├── visualizador.html           # Interface web com PDF e formulário
├── requirements.txt            # Dependências Python (pip)
├── environment.yml             # Arquivo de especificação do ambiente Conda
└── README.md                   # Documentação do projeto
```

---

## 🚀 Instalação e Preparação

### 1. Clonar o Repositório
```bash
git clone https://github.com/seu-usuario/joaclassificador-pdf.git
cd joaclassificador-pdf
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

# Instala todas as dependências requeridas
pip install -r requirements.txt
```

**3. Instalação direta em linha única (sem dependência de arquivos locais):**
```bash
conda create -n pdf-classifier python=3.10 -y && conda run -n pdf-classifier pip install "pypdf>=4.0.0" "pdfplumber>=0.10.0" "pypdfium2>=4.30.0" "pillow>=10.0.0" "requests>=2.31.0" "tqdm>=4.66.0" "openai>=1.0.0" "fonttools>=4.50.0"
```

#### Opção B: Utilizando Python venv padrão

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 💻 Como Usar

### 1. Execução Básica com Ollama (Padrão)

Se o seu Ollama estiver rodando localmente (na porta `11434`) ou em container Docker (`open-webui`):

```bash
./joaclassificador-pdf -i ./meus_pdfs -o ./saida
```

Para especificar outro modelo do Ollama:
```bash
./joaclassificador-pdf -i ./meus_pdfs -o ./saida -m llama3
```

### 2. Execução com a API da OpenAI

Para processar em alta velocidade utilizando processamento paralelo:

```bash
export OPENAI_API_KEY="sk-sua-chave-aqui"

./joaclassificador-pdf -i ./meus_pdfs -o ./saida -p openai -m gpt-4o-mini -w 4
```

### 3. Parâmetros da Linha de Comando

| Parâmetro | Descrição | Valor Padrão |
|---|---|---|
| `-i`, `--input` | Caminho do diretório de PDFs ou arquivo único | `./pdf` |
| `-o`, `--output-dir` | Diretório onde os resultados serão salvos | `./saida` |
| `-p`, `--provider` | Provedor de IA (`ollama` ou `openai`) | `ollama` |
| `-m`, `--model` | Nome do modelo | `gemma4:e4b` / `gpt-4o-mini` |
| `--docker` | Nome do container Docker do Ollama (se aplicável) | Auto-detecta (`open-webui`) |
| `--ollama-url` | URL da API HTTP do Ollama | `http://localhost:11434` |
| `--openai-key` | Chave de API da OpenAI | Lê de `OPENAI_API_KEY` |
| `-w`, `--workers` | Número de threads concorrentes | `1` (Ollama) / `4+` (OpenAI) |
| `--max-pages` | Máximo de páginas a ler por documento | `4` |
| `--no-individual` | Desativa geração de arquivos individuais por MD5 | `False` |

---

## 📄 Exemplo de Saída JSON (Dados Fictícios)

Salvo em `saida/classificacao_diplomas.json`:

```json
[
  {
    "md5": "e4d909c290d0fb1ca068ffaddf22cbd0",
    "data_criacao": "01/01/2026 10:00:00",
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

Salvo em `saida/classificacao_diplomas.txt`:

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
  • Status             : SUCESSO
  • Data de Criação    : 01/01/2026 10:00:00
  • Data de Modificação: 15/12/2025 14:30:00
  • Tipo Documento     : Diploma
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

## 🖥️ Interface de Conferência Humana Lado a Lado

Para revisar visualmente o PDF original contra os dados extraídos pelo modelo:

```bash
./iniciar_visualizador.sh
```

### 📁 Escolha de Pastas no Ato da Execução:

1. **Modo Interativo (Console)**:
   Ao executar `./iniciar_visualizador.sh` no terminal sem parâmetros, o console solicita interativamente:
   - **Pasta dos PDFs**: pressione `ENTER` para aceitar a pasta padrão sugerida (ex: `/home/joaquim/pdf` ou `./pdf`) ou digite o caminho desejado.
   - **Pasta de saída ou arquivo JSON**: pressione `ENTER` para manter a saída padrão (`./saida/classificacao_diplomas.json`) ou informe outro arquivo/pasta.
   - **Porta HTTP**: pressione `ENTER` para manter a porta padrão (`8088`) ou informe outra porta.

2. **Direto por Linha de Comando (CLI)**:
   Você também pode definir as pastas diretamente por parâmetros:
   ```bash
   # Indicando pasta de PDFs e pasta/arquivo de saída JSON:
   ./iniciar_visualizador.sh -i /caminho/meus_pdfs -o /caminho/minha_saida

   # Ou com os aliases completos:
   ./iniciar_visualizador.sh --pdf-dir /caminho/meus_pdfs --json ./saida/outro_lote.json --port 8089

   # Para forçar o menu interativo mesmo com parâmetros:
   ./iniciar_visualizador.sh --prompt

   # Para execução direta sem perguntas (batch):
   ./iniciar_visualizador.sh -y
   ```

Acesse no seu navegador:
👉 **`http://localhost:8088`** (ou a porta escolhida)

### Atalhos na Interface:
- `Seta Esquerda` (`[`): Documento anterior
- `Seta Direita` (`]`): Próximo documento
- `Ctrl + Enter`: Aprovar conferência e avançar automaticamente
- `Ctrl + S`: Salvar edições manuais
- **Botão Exportar**: Baixa o JSON revisado e auditado

---

## 🛡️ Licença

Distribuído sob a licença MIT. Consulte `LICENSE` para obter mais detalhes.
