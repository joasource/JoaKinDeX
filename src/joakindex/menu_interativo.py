"""
Menu interativo do CLI do JoaKinDeX (extraído de cli.py).
"""
import os
import sys
import argparse
from pathlib import Path
from typing import List, Optional

try:
    from joakindex.classificacao import SUPPORTED_EXTENSIONS
except ImportError:
    from .classificacao import SUPPORTED_EXTENSIONS

try:
    from joakindex.config import (
        save_classifier_config,
        reset_classifier_config,
        has_custom_config,
        get_factory_defaults,
        clean_path_string,
        resolve_classifier_output_dir,
    )
except ImportError:
    from .config import (
        save_classifier_config,
        reset_classifier_config,
        has_custom_config,
        get_factory_defaults,
        clean_path_string,
        resolve_classifier_output_dir,
    )

try:
    from joakindex.llm_clients import detect_ollama_environments
except ImportError:
    from .llm_clients import detect_ollama_environments


# ---------------------------------------------------------------------------
# Menu Interativo e Auxiliares de Configuração
# ---------------------------------------------------------------------------
def resolve_default_input_path(specified: Optional[str] = None) -> str:
    if not specified:
        return "./pdf"
    clean = clean_path_string(specified)
    if clean in ["./pdf", "pdf", ""]:
        return "./pdf"
    p = Path(clean).expanduser()
    return str(p.resolve())


def count_pdfs_in_path(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_file():
        return 1 if p.suffix.lower() in SUPPORTED_EXTENSIONS else 0
    cnt = 0
    for ext in SUPPORTED_EXTENSIONS:
        cnt += len(list(p.glob(f"*{ext}"))) + len(list(p.glob(f"*{ext.upper()}")))
    return cnt


count_documents_in_path = count_pdfs_in_path


def get_available_ollama_models(
    base_url: str = "http://localhost:11434",
    docker_container: Optional[str] = None
) -> List[str]:
    envs = detect_ollama_environments(base_url=base_url)
    if docker_container:
        for e in envs:
            if e.get("container") == docker_container:
                return e.get("models", [])
    for e in envs:
        if e.get("is_running") and e.get("models"):
            return e.get("models", [])
    return []


def prompt_interactive_menu(args: argparse.Namespace) -> argparse.Namespace:
    print("\n" + "=" * 70)
    print("🎓 JoaKinDeX - MENU INTERATIVO DE CLASSIFICAÇÃO")
    print("   Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>")
    print("=" * 70)
    print("Pressione ENTER para aceitar o valor padrão sugerido entre colchetes [ ].")

    # Opção inicial se houver configurações personalizadas salvas
    if has_custom_config("classificador"):
        print("\n⚙️  Configurações salvas da execução anterior detectadas:")
        print("   1) Continuar e personalizar configurações salvas [Padrão]")
        print("   2) Restaurar todos os padrões de fábrica (limpar configurações salvas)")
        try:
            init_choice = input("Escolha a opção (1 ou 2) [1]: ").strip()
            if init_choice == "2":
                reset_classifier_config()
                factory = get_factory_defaults()["classificador"]
                for k, v in factory.items():
                    setattr(args, k, v)
                print("   [✓] Configurações restauradas com sucesso para os padrões de fábrica neutros!\n")
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

    # 1. Pasta ou arquivo de entrada
    default_input = resolve_default_input_path(args.input)
    while True:
        try:
            resp_input = input(f"\n📁 Pasta ou arquivo PDF de entrada [{default_input}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        clean_input = clean_path_string(resp_input)
        if clean_input.lower() in ["reset", "resetar", "padrao", "fábrica", "fabrica"]:
            reset_classifier_config()
            factory = get_factory_defaults()["classificador"]
            for k, v in factory.items():
                setattr(args, k, v)
            default_input = resolve_default_input_path(args.input)
            print("   [✓] Configurações restauradas para os padrões de fábrica neutros!")
            continue

        raw_chosen = clean_input if clean_input else default_input
        chosen_path = Path(raw_chosen).expanduser().resolve()
        if not chosen_path.exists():
            print(f"   ⚠️  Aviso: Caminho '{chosen_path}' não foi encontrado.")
            try:
                conf = input("   Deseja manter esse caminho mesmo assim? (s/N): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)
            if conf in ["s", "sim", "y", "yes"]:
                args.input = str(chosen_path)
                break
        else:
            pdf_count = count_pdfs_in_path(chosen_path)
            if pdf_count == 0:
                print(f"   ⚠️  Aviso: Nenhum arquivo PDF encontrado em '{chosen_path}'.")
                try:
                    conf = input("   Deseja manter esse caminho mesmo assim? (s/N): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                if conf in ["s", "sim", "y", "yes"]:
                    args.input = str(chosen_path)
                    break
            else:
                print(f"   ↳ {pdf_count} arquivo(s) PDF localizado(s) para processar.")
                args.input = str(chosen_path)
                break

    # 2. Pasta de saída
    default_out = resolve_classifier_output_dir(args.output_dir or "./saida")
    while True:
        try:
            resp_out = input(f"\n📄 Pasta de saída dos relatórios [{default_out}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        clean_out = clean_path_string(resp_out)
        if clean_out.lower() in ["reset", "resetar", "padrao", "fábrica", "fabrica"]:
            factory = get_factory_defaults()["classificador"]
            default_out = resolve_classifier_output_dir(factory.get("output_dir", "./saida"))
            print("   [✓] Pasta de saída restaurada para o padrão de fábrica neutro!")
            continue

        raw_out = clean_out if clean_out else default_out
        args.output_dir = resolve_classifier_output_dir(raw_out)
        break

    # 3. Provedor de IA
    print("\n🤖 Provedor de Inteligência Artificial:")
    print("   1) Ollama (Modelos locais ou Docker open-webui) [Padrão]")
    print("   2) OpenAI (Modelos em nuvem via API)")
    while True:
        try:
            resp_prov = input("Escolha o provedor (1 ou 2) [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if resp_prov in ["", "1", "ollama"]:
            args.provider = "ollama"
            break
        elif resp_prov in ["2", "openai"]:
            args.provider = "openai"
            break
        else:
            print("   ⚠️  Opção inválida. Digite 1 ou 2.")

    # 4. Modelo de IA
    if args.provider == "ollama":
        print("\n🔍 Detectando ambientes Ollama (Nativo no sistema, Docker oficial puro, Open-WebUI)...")
        detected_envs = detect_ollama_environments(base_url=args.ollama_url)
        running_envs = [e for e in detected_envs if e.get("is_running")]

        chosen_env = None
        if len(running_envs) == 1:
            chosen_env = running_envs[0]
            print(f"   [✓] {chosen_env['description']}")
            if chosen_env["container"]:
                args.docker = chosen_env["container"]
        elif len(running_envs) > 1:
            print(f"   [✓] Foram identificados {len(running_envs)} ambientes Ollama ativos:")
            for idx, env_opt in enumerate(running_envs, 1):
                m_prev = f" (Modelos: {', '.join(env_opt['models'][:3])})" if env_opt.get("models") else " (Sem modelos baixados)"
                print(f"      {idx}) {env_opt['description']}{m_prev}")
            try:
                resp_env = input(f"   Selecione o ambiente Ollama desejado (1-{len(running_envs)}) [1]: ").strip()
                sel_idx = int(resp_env) - 1 if (resp_env.isdigit() and 1 <= int(resp_env) <= len(running_envs)) else 0
                chosen_env = running_envs[sel_idx]
                if chosen_env["container"]:
                    args.docker = chosen_env["container"]
                else:
                    args.docker = None
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)
        else:
            stopped_native = next((e for e in detected_envs if e.get("type") == "native_binary_stopped"), None)
            if stopped_native:
                print(f"   ⚠️  {stopped_native['description']}")
            else:
                print("   ⚠️  Nenhum servidor Ollama detectado (nem nativo em localhost:11434, nem em containers Docker).")

        available_models = chosen_env["models"] if chosen_env else []
        models_display = chosen_env.get("models_display", []) if chosen_env else []

        if available_models:
            print(f"   ↳ Modelos baixados encontrados: {', '.join(models_display or available_models)}")
            default_model = args.model or available_models[0]
        else:
            default_model = args.model or "gemma4:e4b"

        while True:
            try:
                resp_mod = input(f"\n🧠 Modelo Ollama [{default_model}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)
            args.model = resp_mod if resp_mod else default_model
            break
    else:
        default_model = args.model or "gpt-4o-mini"
        while True:
            try:
                resp_mod = input(f"\n🧠 Modelo OpenAI [{default_model}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)
            args.model = resp_mod if resp_mod else default_model
            break

        # Chave da OpenAI
        current_key = args.openai_key or os.environ.get("OPENAI_API_KEY", "")
        if current_key:
            masked = (current_key[:7] + "..." + current_key[-4:]) if len(current_key) > 12 else "********"
            prompt_key_str = f"🔑 Chave de API OpenAI [{masked} - ENTER para manter]: "
        else:
            prompt_key_str = "🔑 Chave de API OpenAI (sk-...): "

        while True:
            try:
                resp_key = input(prompt_key_str).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Operação cancelada pelo usuário]")
                sys.exit(0)

            if resp_key:
                args.openai_key = resp_key
                break
            elif current_key:
                args.openai_key = current_key
                break
            else:
                print("   ⚠️  Aviso: O uso da OpenAI requer uma chave de API válida.")
                try:
                    conf_no_key = input("   Deseja continuar sem informar a chave agora? (s/N): ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    sys.exit(0)
                if conf_no_key in ["s", "sim", "y", "yes"]:
                    break

        # Base URL opcional (para compatibilidade com Groq, OpenRouter, vLLM, etc.)
        current_base_url = args.openai_base_url or os.environ.get("OPENAI_BASE_URL", "")
        default_url_desc = current_base_url if current_base_url else "padrão oficial OpenAI"
        try:
            resp_base = input(f"🌐 OpenAI Base URL (opcional para Groq/OpenRouter) [{default_url_desc}]: ").strip()
            if resp_base:
                args.openai_base_url = resp_base
            elif current_base_url:
                args.openai_base_url = current_base_url
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

    # 5. Threads de processamento (Workers)
    default_workers = args.workers if (args.workers and args.workers > 1) else (4 if args.provider == "openai" else 1)
    while True:
        try:
            resp_w = input(f"\n⚡ Concorrência / Threads simultâneas [{default_workers}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if not resp_w:
            args.workers = default_workers
            break
        try:
            w_val = int(resp_w)
            if w_val >= 1:
                args.workers = w_val
                break
            else:
                print("   ⚠️  O número de workers deve ser pelo menos 1.")
        except ValueError:
            print("   ⚠️  Digite um número inteiro válido.")

    # 6. OCR Multimodal via LLM
    print("\n🔍 OCR Multimodal via LLM (para PDFs digitalizados e correções de CPF/Tipo):")
    default_ocr_str = "N" if args.skip_ocr else "S"
    try:
        resp_ocr = input(f"Deseja manter o OCR multimodal ativado? (S/n) [{default_ocr_str}]: ").strip().lower()
        if resp_ocr in ["n", "nao", "não", "no"]:
            args.skip_ocr = True
        elif resp_ocr in ["s", "sim", "y", "yes", ""]:
            args.skip_ocr = False
    except (EOFError, KeyboardInterrupt):
        print("\n[Operação cancelada pelo usuário]")
        sys.exit(0)

    # 7. Estratégia de Processamento
    print("\n⚙️  Estratégia de Processamento:")
    print("   1) Incremental: Processar novos e pendentes (ignora já concluídos com sucesso) [Padrão]")
    print("   2) Reprocessar documentos que necessitam de OCR (erros ou não identificados)")
    print("   3) Forçar reprocessamento de TODOS os documentos do zero")
    while True:
        try:
            resp_mode = input("Escolha o modo de execução (1, 2 ou 3) [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)

        if resp_mode in ["", "1"]:
            args.force = False
            args.reprocess_ocr = False
            break
        elif resp_mode == "2":
            args.force = False
            args.reprocess_ocr = True
            break
        elif resp_mode == "3":
            args.force = True
            args.reprocess_ocr = False
            break
        else:
            print("   ⚠️  Opção inválida. Digite 1, 2 ou 3.")

    # Resumo
    in_p = Path(args.input)
    pdf_qtd = count_pdfs_in_path(in_p)
    mode_desc = (
        "Reprocessar TUDO do zero (--force)" if args.force
        else ("Reprocessar pendentes de OCR (--reprocess-ocr)" if args.reprocess_ocr
        else "Incremental (apenas novos e pendentes)")
    )
    ocr_desc = "Desativado (--skip-ocr)" if args.skip_ocr else "Ativado (Automático para escaneados e erros de CPF/Tipo)"

    print("\n" + "=" * 70)
    print("📋 RESUMO DA CONFIGURAÇÃO DO CLASSIFICADOR")
    print("=" * 70)
    print(f"• Entrada      : {args.input} ({pdf_qtd} arquivo(s) PDF)")
    print(f"• Saída        : {args.output_dir}")
    if args.provider == "openai":
        k_val = args.openai_key or os.environ.get("OPENAI_API_KEY", "")
        masked_k = (k_val[:7] + "..." + k_val[-4:]) if (k_val and len(k_val) > 12) else ("Configurada" if k_val else "Não informada")
        print(f"• Provedor     : OPENAI (Modelo: {args.model} | Chave: {masked_k})")
        if args.openai_base_url:
            print(f"• Base URL     : {args.openai_base_url}")
    else:
        print(f"• Provedor     : OLLAMA (Modelo: {args.model})")
    print(f"• Concorrência : {args.workers} thread(s)")
    print(f"• OCR com LLM  : {ocr_desc}")
    print(f"• Execução     : {mode_desc}")
    print("=" * 70)

    try:
        conf_start = input("Deseja iniciar a classificação agora? (S/n) [S]: ").strip().lower()
        if conf_start in ["n", "nao", "não", "no"]:
            print("\n[Operação cancelada pelo usuário]")
            sys.exit(0)
    except (EOFError, KeyboardInterrupt):
        print("\n[Operação cancelada pelo usuário]")
        sys.exit(0)

    # Salva opções configuradas pelo usuário para persistência
    save_classifier_config({
        "input": str(args.input),
        "output_dir": str(args.output_dir),
        "provider": args.provider,
        "model": args.model,
        "docker": args.docker,
        "ollama_url": args.ollama_url,
        "openai_key": args.openai_key,
        "openai_base_url": args.openai_base_url,
        "workers": args.workers,
        "max_pages": args.max_pages,
        "skip_ocr": args.skip_ocr,
        "no_individual": args.no_individual
    })

    print("\n" + "=" * 70 + "\n")
    return args
