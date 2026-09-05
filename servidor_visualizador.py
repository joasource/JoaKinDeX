#!/usr/bin/env python3
"""
Servidor Web Local para Conferência Humana de Diplomas e Certificados.
Permite visualizar o PDF lado a lado com o JSON extraído, editar dados e salvar alterações.
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import urllib.parse
from datetime import datetime


def resolve_pdf_dir(specified_dir: str = None) -> Path:
    if specified_dir:
        p = Path(specified_dir).expanduser().resolve()
        if p.exists() and p.is_dir():
            return p
        elif specified_dir not in ["./pdf", "pdf"]:
            return p

    candidates = [
        Path("./pdf"),
        Path("../pdf"),
        Path.home() / "pdf",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c.resolve()

    return Path("./pdf").resolve()


def resolve_json_path(specified_json: str = None) -> Path:
    """
    Resolve o caminho do arquivo JSON. Se for informado um diretório,
    procura por classificacao_diplomas.json ou outro .json correspondente.
    """
    if not specified_json:
        # Tenta ./saida/classificacao_diplomas.json ou ../saida/classificacao_diplomas.json
        candidates = [
            Path("./saida/classificacao_diplomas.json"),
            Path("../saida/classificacao_diplomas.json"),
            Path("./classificacao_diplomas.json"),
        ]
        for c in candidates:
            if c.exists():
                return c.resolve()
        return Path("./saida/classificacao_diplomas.json").resolve()

    p = Path(specified_json).expanduser().resolve()

    # Se for um diretório existente
    if p.is_dir():
        cand = p / "classificacao_diplomas.json"
        if cand.exists():
            return cand
        # Procura qualquer .json na pasta
        json_files = list(p.glob("*.json"))
        for jf in json_files:
            if "classificacao" in jf.name.lower():
                return jf
        if json_files:
            return json_files[0]
        return cand

    # Se termina com extensão .json
    if p.suffix.lower() == ".json":
        return p

    # Se o nome não tem extensão .json mas o usuário passou algo como 'minha_pasta/saida'
    return p / "classificacao_diplomas.json"


def prompt_interactive_config(default_pdf_dir: Path, default_json_path: Path, default_port: int):
    """
    Exibe menu interativo no console permitindo ao usuário escolher ou alterar
    as pastas de entrada de PDFs e de saída de JSONs antes de iniciar o servidor.
    """
    print("\n" + "=" * 70)
    print("⚙️  CONFIGURAÇÃO DO VISUALIZADOR DE DIPLOMAS E CERTIFICADOS")
    print("=" * 70)
    print("Pressione ENTER para aceitar o valor padrão sugerido entre colchetes.\n")

    # 1. Pasta de PDFs
    chosen_pdf_dir = default_pdf_dir
    while True:
        try:
            resp_pdf = input(f"📁 Pasta dos PDFs [{default_pdf_dir}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if not resp_pdf:
            chosen_pdf_dir = default_pdf_dir
            break
        else:
            p = Path(resp_pdf).expanduser().resolve()
            if not p.exists() or not p.is_dir():
                print(f"   ⚠️  Aviso: Diretório '{p}' não existe ou não é uma pasta.")
                try:
                    conf = input("   Deseja utilizar esse caminho mesmo assim? (s/N): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                if conf in ["s", "sim", "y", "yes"]:
                    chosen_pdf_dir = p
                    break
            else:
                chosen_pdf_dir = p
                break

    # 2. Pasta de saída ou arquivo JSON
    chosen_json_path = default_json_path
    while True:
        try:
            resp_json = input(f"📄 Pasta ou arquivo JSON [{default_json_path}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if not resp_json:
            chosen_json_path = default_json_path
            break
        else:
            p = resolve_json_path(resp_json)
            if not p.exists():
                print(f"   ℹ️  Arquivo '{p}' ainda não existe (será criado ao salvar).")
            chosen_json_path = p
            break

    # 3. Porta
    chosen_port = default_port
    while True:
        try:
            resp_port = input(f"🌐 Porta HTTP [{default_port}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if not resp_port:
            chosen_port = default_port
            break
        try:
            p_val = int(resp_port)
            if 1 <= p_val <= 65535:
                chosen_port = p_val
                break
            else:
                print("   ⚠️  Porta inválida (deve estar entre 1 e 65535).")
        except ValueError:
            print("   ⚠️  Digite um número de porta válido.")

    print("=" * 70 + "\n")
    return chosen_pdf_dir, chosen_json_path, chosen_port

def calculate_md5(file_path: Path) -> str:
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class ConferenciaServer:
    def __init__(self, json_path: str, pdf_dir: str, html_path: str):
        self.json_path = Path(json_path).resolve()
        self.pdf_dir = Path(pdf_dir).resolve()
        self.html_path = Path(html_path).resolve()
        self.md5_to_file = {}
        self.build_pdf_index()

    def build_pdf_index(self):
        """Indexa os arquivos PDFs da pasta mapeando seus MD5."""
        self.md5_to_file.clear()
        if not self.pdf_dir.exists():
            print(f"[Aviso] Pasta de PDFs não encontrada: {self.pdf_dir}")
            return

        pdf_set = set(self.pdf_dir.glob("*.pdf")) | set(self.pdf_dir.glob("*.PDF"))
        if not pdf_set:
            pdf_set = set(self.pdf_dir.rglob("*.pdf")) | set(self.pdf_dir.rglob("*.PDF"))
        pdf_files = sorted(pdf_set)
        print(f"[*] Indexando {len(pdf_files)} PDFs na pasta {self.pdf_dir}...")
        for p in pdf_files:
            try:
                h = calculate_md5(p)
                self.md5_to_file[h] = p
            except Exception as e:
                print(f"[Erro] Falha ao ler {p.name}: {e}")
        print(f"[*] {len(self.md5_to_file)} PDFs indexados com sucesso pelo hash MD5.")

    def load_data(self):
        if not self.json_path.exists():
            return []
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Erro] Falha ao ler JSON: {e}")
            return []

    def save_data(self, data):
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Atualiza também o relatório TXT consolidado correspondente
        self.update_txt_report(data)

    def update_txt_report(self, results):
        txt_path = self.json_path.with_suffix(".txt")
        total = len(results)
        sucesso = sum(1 for r in results if r.get("status") == "sucesso")
        erros = total - sucesso
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        lines = [
            "=" * 80,
            "RELATÓRIO CONSOLIDADO DE CLASSIFICAÇÃO DE DIPLOMAS E CERTIFICADOS (REVISADO)",
            f"Data/Hora de Revisão : {now_str}",
            f"Total de Documentos  : {total}",
            f"Classificados com OK : {sucesso}",
            f"Falhas / Erros       : {erros}",
            "=" * 80,
            ""
        ]

        for idx, item in enumerate(results, 1):
            conf = item.get("status_conferencia", "PENDENTE")
            lines.append(f"[{idx}/{total}] MD5: {item.get('md5')}")
            lines.append(f"  • Conferência        : {conf.upper()}")
            lines.append(f"  • Status             : {item.get('status', '').upper()}")
            lines.append(f"  • Data de Criação    : {item.get('data_criacao')}")
            lines.append(f"  • Data de Modificação: {item.get('data_modificacao')}")
            lines.append(f"  • Tipo Documento     : {item.get('tipo_documento') or 'Não identificado'}")
            lines.append(f"  • Beneficiário       : {item.get('beneficiario') or 'Não informado'}")
            lines.append(f"  • CPF                : {item.get('cpf') or 'Não informado'}")
            lines.append(f"  • RG / Identidade    : {item.get('rg') or 'Não informado'}")
            lines.append(f"  • Curso              : {item.get('curso') or 'Não informado'}")
            lines.append(f"  • Natureza do Curso  : {item.get('natureza_curso') or 'Não identificada'}")
            lines.append(f"  • Carga Horária      : {item.get('carga_horaria') or 'Não informada'}")
            lines.append(f"  • Faculdade          : {item.get('faculdade') or 'Não informada'}")
            lines.append(f"  • Data do Documento  : {item.get('data') or 'Não informada'}")
            if item.get("observacoes_conferencia"):
                lines.append(f"  • Obs. Conferência   : {item.get('observacoes_conferencia')}")
            if item.get("erro"):
                lines.append(f"  • Detalhe do Erro    : {item.get('erro')}")
            lines.append("-" * 80)

        lines.append("")
        lines.append("=" * 80)
        lines.append("FIM DO RELATÓRIO")
        lines.append("=" * 80)

        try:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception:
            pass


def create_handler(server_ctx: ConferenciaServer):
    class RequestHandler(SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            super().end_headers()

        def do_OPTIONS(self):
            self.send_response(200)
            self.end_headers()

        def do_HEAD(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path in ["/", "/index.html", "/visualizador", "/visualizador.html"]:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(server_ctx.html_path.stat().st_size))
                self.end_headers()
                return
            elif path.startswith("/api/pdf/"):
                md5_req = path.split("/api/pdf/")[-1].strip().lower()
                pdf_file = server_ctx.md5_to_file.get(md5_req)
                if pdf_file and pdf_file.exists():
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Length", str(pdf_file.stat().st_size))
                    self.end_headers()
                    return
            super().do_HEAD()

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            # Rota da página principal
            if path in ["/", "/index.html", "/visualizador", "/visualizador.html"]:
                if server_ctx.html_path.exists():
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    content = server_ctx.html_path.read_bytes()
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self.send_error(404, "Arquivo HTML do visualizador não encontrado.")
                return

            # API de informações das pastas e arquivos ativos
            if path == "/api/info":
                info = {
                    "json_path": str(server_ctx.json_path),
                    "json_name": server_ctx.json_path.name,
                    "pdf_dir": str(server_ctx.pdf_dir),
                    "pdf_count": len(server_ctx.md5_to_file),
                    "doc_count": len(server_ctx.load_data())
                }
                body = json.dumps(info, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API para listar todos os documentos
            if path == "/api/documentos":
                dados = server_ctx.load_data()
                for item in dados:
                    if "status_conferencia" not in item:
                        item["status_conferencia"] = "pendente"
                    for k in ["curso", "beneficiario", "faculdade", "natureza_curso", "tipo_documento", "carga_horaria", "cpf", "rg", "data"]:
                        v = item.get(k)
                        if isinstance(v, list):
                            item[k] = ", ".join(str(x) for x in v if x)
                body = json.dumps(dados, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # API para servir o PDF por Hash MD5
            if path.startswith("/api/pdf/"):
                md5_req = path.split("/api/pdf/")[-1].strip().lower()
                pdf_file = server_ctx.md5_to_file.get(md5_req)

                if not pdf_file or not pdf_file.exists():
                    server_ctx.build_pdf_index()
                    pdf_file = server_ctx.md5_to_file.get(md5_req)

                if pdf_file and pdf_file.exists():
                    size = pdf_file.stat().st_size
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Disposition", f'inline; filename="{md5_req}.pdf"')
                    self.send_header("Content-Length", str(size))
                    self.end_headers()
                    with open(pdf_file, "rb") as f:
                        self.wfile.write(f.read())
                    return
                else:
                    self.send_error(404, f"Arquivo PDF com MD5 {md5_req} não encontrado.")
                    return

            super().do_GET()

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(length)

            try:
                payload = json.loads(post_body.decode("utf-8"))
            except Exception as e:
                self.send_error(400, f"Payload JSON inválido: {e}")
                return

            # Salvar edição de um documento
            if path == "/api/salvar":
                dados_atuais = server_ctx.load_data()
                item_editado = payload.get("item")
                if item_editado and "md5" in item_editado:
                    target_md5 = item_editado["md5"]
                    found = False
                    for idx, doc in enumerate(dados_atuais):
                        if doc.get("md5") == target_md5:
                            item_editado["revisado_em"] = datetime.now().isoformat()
                            dados_atuais[idx] = item_editado
                            found = True
                            break
                    if not found:
                        dados_atuais.append(item_editado)

                    server_ctx.save_data(dados_atuais)

                    # Se existir pasta 'individuais' correspondente, atualiza o arquivo individual também
                    indiv_dir = server_ctx.json_path.parent / "individuais"
                    if indiv_dir.exists():
                        indiv_file = indiv_dir / f"{target_md5}.json"
                        try:
                            with open(indiv_file, "w", encoding="utf-8") as fi:
                                json.dump(item_editado, fi, ensure_ascii=False, indent=2)
                        except Exception:
                            pass

                    resp = json.dumps({"status": "sucesso", "mensagem": "Documento salvo com sucesso!"}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                    return

            # Aprovação de conferência
            if path == "/api/aprovar":
                target_md5 = payload.get("md5")
                dados_atuais = server_ctx.load_data()
                found = False
                for doc in dados_atuais:
                    if doc.get("md5") == target_md5:
                        doc["status_conferencia"] = "aprovado"
                        doc["conferido_em"] = datetime.now().isoformat()
                        if "observacoes_conferencia" in payload:
                            doc["observacoes_conferencia"] = payload["observacoes_conferencia"]
                        found = True
                        break

                if found:
                    server_ctx.save_data(dados_atuais)
                    resp = json.dumps({"status": "sucesso", "mensagem": "Conferência aprovada com sucesso!"}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp)))
                    self.end_headers()
                    self.wfile.write(resp)
                else:
                    self.send_error(404, f"Documento MD5 {target_md5} não encontrado.")
                return

            self.send_error(404, "Endpoint não encontrado")

    return RequestHandler


def main():
    parser = argparse.ArgumentParser(
        description="Servidor Web do Visualizador de Conferência Humana de Diplomas e Certificados."
    )
    parser.add_argument(
        "-p", "--pdf-dir", "-i", "--input",
        dest="pdf_dir",
        type=str,
        default=None,
        help="Pasta contendo os arquivos PDFs a serem visualizados (padrão detectado: ~/pdf ou ./pdf)."
    )
    parser.add_argument(
        "-j", "--json", "-o", "--output", "--output-dir", "--saida",
        dest="json_path",
        type=str,
        default=None,
        help="Pasta de saída ou arquivo JSON de classificação (padrão: ./saida/classificacao_diplomas.json)."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8088,
        help="Porta HTTP do servidor (padrão: 8088)."
    )
    parser.add_argument(
        "--html",
        type=str,
        default="./visualizador.html",
        help="Caminho do arquivo HTML da interface (padrão: ./visualizador.html)."
    )
    parser.add_argument(
        "--prompt", "--interativo", "-interactive",
        dest="force_prompt",
        action="store_true",
        help="Força a solicitação interativa de pastas e configurações no console."
    )
    parser.add_argument(
        "--no-prompt", "-y", "--batch",
        dest="no_prompt",
        action="store_true",
        help="Executa diretamente sem perguntas interativas no console."
    )

    args = parser.parse_args()

    default_pdf = resolve_pdf_dir(args.pdf_dir)
    default_json = resolve_json_path(args.json_path)
    default_port = args.port

    is_interactive = sys.stdin.isatty()
    # Solicita interativamente no console se:
    # 1. Flag --prompt/--interativo foi passada, OU
    # 2. Executando em terminal interativo, sem flag --no-prompt e sem argumentos explícitos de diretório
    should_prompt = args.force_prompt or (
        is_interactive
        and not args.no_prompt
        and args.pdf_dir is None
        and args.json_path is None
    )

    if should_prompt:
        pdf_dir_final, json_path_final, port_final = prompt_interactive_config(
            default_pdf_dir=default_pdf,
            default_json_path=default_json,
            default_port=default_port
        )
    else:
        pdf_dir_final = default_pdf
        json_path_final = default_json
        port_final = default_port

    ctx = ConferenciaServer(
        json_path=str(json_path_final),
        pdf_dir=str(pdf_dir_final),
        html_path=args.html
    )
    handler = create_handler(ctx)

    server_address = ("0.0.0.0", port_final)
    httpd = ThreadingHTTPServer(server_address, handler)

    print("\n" + "=" * 70)
    print("🚀 VISUALIZADOR DE CONFERÊNCIA HUMANA INICIADO!")
    print(f"👉 Acesse no seu navegador: http://localhost:{port_final}")
    print(f"   (ou pelo IP da máquina: http://127.0.0.1:{port_final})")
    print(f"📄 Arquivo JSON monitorado : {ctx.json_path}")
    print(f"📁 Pasta de PDFs indexada  : {ctx.pdf_dir} ({len(ctx.md5_to_file)} PDFs)")
    print("=" * 70)
    print("Pressione Ctrl+C a qualquer momento para encerrar o servidor.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Encerrando servidor visualizador.")
        httpd.server_close()


if __name__ == "__main__":
    main()
