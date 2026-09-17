    function loadPdfInFrame(md5, force = false) {
      if (!md5) return;
      const pdfFrame = document.getElementById('pdfFrame');
      const pdfLoading = document.getElementById('pdfLoadingState');
      const pdfEmpty = document.getElementById('pdfEmptyState');

      if (pdfEmpty) pdfEmpty.classList.add('hidden');

      // Se já está exibindo esse mesmo documento e não é force, não recarrega o iframe
      if (!force && currentLoadedPdfMd5 === md5) {
        if (pdfLoading) pdfLoading.classList.add('hidden');
        return;
      }

      currentLoadedPdfMd5 = md5;

      if (pdfLoadTimeout) {
        clearTimeout(pdfLoadTimeout);
        pdfLoadTimeout = null;
      }

      if (pdfLoading) {
        pdfLoading.classList.remove('hidden');
        pdfLoading.style.opacity = '1';
      }

      const hideLoading = () => {
        if (pdfLoading) {
          pdfLoading.style.opacity = '0';
          setTimeout(() => {
            if (pdfLoading) pdfLoading.classList.add('hidden');
          }, 200);
        }
        if (pdfLoadTimeout) {
          clearTimeout(pdfLoadTimeout);
          pdfLoadTimeout = null;
        }
      };

      // 1. Escuta eventos normais de carregamento do iframe
      pdfFrame.onload = hideLoading;
      pdfFrame.onerror = hideLoading;

      // 2. Timeout de segurança: no Chrome/Chromium, o visualizador de PDF interno
      // frequentemente não dispara o evento DOM iframe.onload.
      // O timeout garante que o indicador nunca fique travado na tela!
      pdfLoadTimeout = setTimeout(hideLoading, 500);

      // 3. Atualiza o src do iframe
      pdfFrame.src = `/api/pdf/${md5}#toolbar=1&navpanes=0`;
    }

    function loadMediaForDocument(doc, force = false) {
      if (!doc || !doc.md5) return;
      const isImg = isImageDoc(doc);
      const pdfFrame = document.getElementById('pdfFrame');
      const imgViewer = document.getElementById('imageViewerContainer');
      const imgEl = document.getElementById('docImageEl');
      const imgControls = document.getElementById('imageControls');
      const docTypeHeaderIcon = document.getElementById('docTypeHeaderIcon');
      const docTypeHeaderLabel = document.getElementById('docTypeHeaderLabel');
      const pdfEmpty = document.getElementById('pdfEmptyState');
      const pdfLoading = document.getElementById('pdfLoadingState');

      if (pdfEmpty) pdfEmpty.classList.add('hidden');

      if (isImg) {
        // Modo visualização de Imagem
        if (pdfFrame) {
          pdfFrame.classList.add('hidden');
          pdfFrame.src = 'about:blank';
        }
        if (imgViewer) imgViewer.classList.remove('hidden');
        if (imgControls) {
          imgControls.classList.remove('hidden');
          imgControls.classList.add('flex');
        }

        const extLabel = safeString(doc.extensao || 'IMG').replace('.', '').toUpperCase();
        if (docTypeHeaderIcon) docTypeHeaderIcon.className = "fa-regular fa-image text-emerald-400";
        if (docTypeHeaderLabel) docTypeHeaderLabel.innerText = `Visualização da Imagem (${extLabel}):`;

        resetImageTransform();
        if (imgEl) {
          const cacheBuster = force ? `?t=${Date.now()}` : '';
          imgEl.src = `/api/arquivo/${doc.md5}${cacheBuster}`;
        }
        if (pdfLoading) pdfLoading.classList.add('hidden');
        currentLoadedPdfMd5 = doc.md5;
      } else {
        // Modo visualização de PDF ou Documento Word / Texto
        if (imgViewer) imgViewer.classList.add('hidden');
        if (imgControls) {
          imgControls.classList.add('hidden');
          imgControls.classList.remove('flex');
        }
        if (pdfFrame) pdfFrame.classList.remove('hidden');

        const fmt = getDocFormatMeta(doc);
        if (docTypeHeaderIcon) docTypeHeaderIcon.className = `${fmt.icon} ${fmt.color}`;
        if (docTypeHeaderLabel) {
          if (fmt.type === 'word') {
            docTypeHeaderLabel.innerText = `Visualização do Documento Word (${fmt.label}):`;
          } else if (fmt.type === 'text') {
            docTypeHeaderLabel.innerText = `Visualização de Arquivo de Texto (${fmt.label}):`;
          } else {
            docTypeHeaderLabel.innerText = "Visualização do PDF:";
          }
        }

        loadPdfInFrame(force ? `${doc.md5}?t=${Date.now()}` : doc.md5, force);
      }
    }

    function clearSelectionView() {
      currentIndex = -1;
      currentSelectedMd5 = null;
      currentLoadedPdfMd5 = null;
      if (pdfLoadTimeout) {
        clearTimeout(pdfLoadTimeout);
        pdfLoadTimeout = null;
      }
      document.getElementById('navCounter').innerText = '0 de 0';

      const pdfFrame = document.getElementById('pdfFrame');
      const pdfLoading = document.getElementById('pdfLoadingState');
      const pdfEmpty = document.getElementById('pdfEmptyState');
      const imgViewer = document.getElementById('imageViewerContainer');
      const imgEl = document.getElementById('docImageEl');
      const imgControls = document.getElementById('imageControls');

      if (pdfLoading) pdfLoading.classList.add('hidden');
      if (pdfEmpty) pdfEmpty.classList.remove('hidden');
      if (pdfFrame) {
        pdfFrame.classList.remove('hidden');
        pdfFrame.src = 'about:blank';
      }
      if (imgViewer) imgViewer.classList.add('hidden');
      if (imgControls) {
        imgControls.classList.add('hidden');
        imgControls.classList.remove('flex');
      }
      if (imgEl) imgEl.src = '';
      resetImageTransform();

      document.getElementById('pdfMd5Title').innerText = 'Nenhum documento selecionado';
      document.getElementById('openPdfNewTab').href = '#';

      document.getElementById('field_md5').innerText = '-';
      document.getElementById('field_data_modificacao').innerText = '-';
      const fAutorClean = document.getElementById('field_autor');
      if (fAutorClean) { fAutorClean.innerText = '-'; fAutorClean.title = '-'; }
      const fMetodoClean = document.getElementById('field_metodo_leitura');
      if (fMetodoClean) fMetodoClean.innerText = '-';
      const fTentativaClean = document.getElementById('field_tentativa_ocr');
      if (fTentativaClean) fTentativaClean.innerText = '-';

      const selectDom = document.getElementById('select_dominio');
      if (selectDom) selectDom.value = 'academico';

      const clearEl = (id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      };
      ['input_valor_monetario', 'input_beneficiario', 'input_cpf', 'input_rg',
       'input_doc_cnpj', 'input_cnpj', 'input_cnpj_razao_social', 'input_cnpj_nome_fantasia',
       'input_cnpj_situacao', 'input_cnpj_data_abertura', 'input_cnpj_cnae',
       'input_cnpj_natureza_juridica', 'input_cnpj_endereco', 'input_doc_endereco',
       'input_cnpj_telefone', 'input_cnpj_email', 'select_natureza_curso',
       'input_curso', 'input_carga_horaria', 'input_data', 'input_faculdade', 'input_obs'].forEach(clearEl);

      const selectTipo = document.getElementById('select_tipo_documento');
      if (selectTipo) selectTipo.value = 'Certificado';

      const secContainer = document.getElementById('dynamicSectionsContainer');
      if (secContainer) secContainer.innerHTML = '';
      const heroBadges = document.getElementById('dynamicHeroBadges');
      if (heroBadges) heroBadges.innerHTML = '';
      const emptyState = document.getElementById('dynamicEmptyState');
      if (emptyState) emptyState.classList.add('hidden');

      onDominioChange();

      document.getElementById('jsonViewer').innerText = '{}';
      if (typeof updateClassificationButtonsState === 'function') updateClassificationButtonsState();
      isDirty = false;
    }

    function selectDocument(index, skipSidebarUpdate = false) {
      if (!filteredDocs || filteredDocs.length === 0 || index < 0 || index >= filteredDocs.length) {
        clearSelectionView();
        return;
      }
      currentIndex = index;
      const doc = filteredDocs[currentIndex];
      currentSelectedMd5 = doc.md5;

      if (window.innerWidth < 768 && currentMobileConfView === 'lista') {
        setMobileConferenceView('doc');
      }

      document.getElementById('navCounter').innerText = `${currentIndex + 1} de ${filteredDocs.length}`;

      // Atualiza visualizador do documento (PDF ou Imagem)
      loadMediaForDocument(doc);

      document.getElementById('pdfMd5Title').innerText = safeString(doc.md5);
      const openBtn = document.getElementById('openPdfNewTab');
      if (openBtn) {
        openBtn.href = `/api/arquivo/${doc.md5}`;
        const fmt = getDocFormatMeta(doc);
        if (fmt.type === 'word') {
          openBtn.title = `Baixar arquivo Word original editável (${fmt.label})`;
          openBtn.setAttribute('download', `${doc.nome_arquivo || (doc.md5 + '.' + fmt.label.toLowerCase())}`);
          openBtn.innerHTML = `<i class="fa-solid fa-file-word text-sky-400"></i><span class="hidden sm:inline">Baixar Word</span>`;
        } else if (fmt.type === 'image') {
          openBtn.title = 'Abrir imagem original em nova aba';
          openBtn.removeAttribute('download');
          openBtn.innerHTML = `<i class="fa-solid fa-up-right-from-square"></i><span class="hidden sm:inline">Abrir Imagem</span>`;
        } else {
          openBtn.title = 'Abrir documento em nova aba';
          openBtn.removeAttribute('download');
          openBtn.innerHTML = `<i class="fa-solid fa-up-right-from-square"></i><span class="hidden sm:inline">Nova Aba</span>`;
        }
      }

      // Preenche campos do formulário de forma segura
      document.getElementById('field_md5').innerText = safeString(doc.md5);
      document.getElementById('field_data_modificacao').innerText = safeString(doc.data_modificacao) || '-';
      const fAutor = document.getElementById('field_autor');
      if (fAutor) {
        const autVal = safeString(doc.autor) || '-';
        fAutor.innerText = autVal;
        fAutor.title = autVal;
      }
      const fMetodo = document.getElementById('field_metodo_leitura');
      if (fMetodo) {
        if (doc.metodo_leitura === 'hibrido_fallback_openai') {
          fMetodo.innerHTML = '<span class="text-amber-300 font-semibold inline-flex items-center gap-1" title="Fallback Híbrido ativado: Ollama ➔ OpenAI"><i class="fa-solid fa-bolt text-amber-400"></i> Híbrido (Ollama ➔ Nuvem)</span>';
        } else {
          fMetodo.innerText = safeString(doc.metodo_leitura) || (doc.status === 'nao_processado' ? 'não processado' : 'texto_digital');
        }
      }
      const fTentativa = document.getElementById('field_tentativa_ocr');
      if (fTentativa) fTentativa.innerText = doc.tentativa_ocr_llm ? 'Sim' : 'Não';

      // Domínio e Tipo de Documento
      const docDominio = safeString(doc.dominio || 'academico').toLowerCase() || 'academico';
      const selectDom = document.getElementById('select_dominio');
      if (selectDom) selectDom.value = docDominio;

      // Tipo de Documento: seleciona ou insere opção se for novo
      const selectTipo = document.getElementById('select_tipo_documento');
      const docTipo = safeString(doc.tipo_documento).trim();
      if (docTipo && selectTipo) {
        let exists = false;
        for (let i = 0; i < selectTipo.options.length; i++) {
          if (selectTipo.options[i].value === docTipo) {
            exists = true;
            break;
          }
        }
        if (!exists) {
          const opt = document.createElement('option');
          opt.value = docTipo;
          opt.innerText = docTipo;
          selectTipo.appendChild(opt);
        }
        selectTipo.value = docTipo;
      } else if (selectTipo) {
        selectTipo.value = 'Certificado';
      }

      const inputObs = document.getElementById('input_obs');
      if (inputObs) inputObs.value = safeString(doc.observacoes_conferencia);

      onDominioChange();

      // Renderiza o Inspetor Dinâmico de Entidades (Zero Noise)
      renderDynamicInspector(doc);

      // Atualiza badge de status
      const isUnproc = isDocumentUnprocessed(doc);
      const isApproved = !isUnproc && safeString(doc.status_conferencia || 'pendente').toLowerCase() === 'aprovado';
      const badge = document.getElementById('currentStatusBadge');
      if (isUnproc) {
        badge.className = "text-[11px] px-2.5 py-0.5 rounded-full font-medium border bg-rose-500/10 text-rose-400 border-rose-500/20";
        if (doc.status === 'erro') {
          badge.innerText = "Não Classificado (Falha na Leitura)";
        } else {
          badge.innerText = "Não Classificado / Não Lido";
        }
      } else if (isApproved) {
        badge.className = "text-[11px] px-2.5 py-0.5 rounded-full font-medium border bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
        badge.innerText = "Aprovado / Conferido";
      } else {
        badge.className = "text-[11px] px-2.5 py-0.5 rounded-full font-medium border bg-amber-500/10 text-amber-400 border-amber-500/20";
        badge.innerText = "Pendente de Conferência";
      }

      const hybridBadgeEl = document.getElementById('currentHybridBadge');
      if (hybridBadgeEl) {
        if (doc.metodo_leitura === 'hibrido_fallback_openai') {
          hybridBadgeEl.classList.remove('hidden');
        } else {
          hybridBadgeEl.classList.add('hidden');
        }
      }

      updateJsonView();
      if (!skipSidebarUpdate) {
        updateSidebarSelection();
      }
      if (typeof updateClassificationButtonsState === 'function') {
        updateClassificationButtonsState();
      }
      currentDossieActivePage = 1;
      renderMultiTags(doc);
      renderDossierPageShortcuts(doc);
      renderDossierPagesGrid(doc);
      renderDynamicInspector(doc);
      updateFichaTecnica(doc);
      if (currentInspectorTab === 'texto') {
        loadDocumentText(doc.md5);
      } else {
        clearDocTextSearch();
      }
      isDirty = false;
    }

    // -----------------------------------------------------------------------
    // MOTOR DO INSPETOR DINÂMICO DE ENTIDADES (ZERO NOISE / ADAPTATIVO)
    // -----------------------------------------------------------------------

    const CANONICAL_FIELD_MAP = {
      // Finanças
      valor_monetario: { label: 'Valor da Operação (R$)', icon: 'fa-solid fa-coins', category: 'financas', type: 'currency', isCore: true },
      valor: { label: 'Valor (R$)', icon: 'fa-solid fa-coins', category: 'financas', type: 'currency', isCore: false },
      valor_pago: { label: 'Valor Pago (R$)', icon: 'fa-solid fa-coins', category: 'financas', type: 'currency', isCore: false },
      banco: { label: 'Instituição Bancária', icon: 'fa-solid fa-building-columns', category: 'financas', type: 'text', isCore: false },
      instituicao_financeira: { label: 'Instituição Financeira', icon: 'fa-solid fa-building-columns', category: 'financas', type: 'text', isCore: false },
      agencia: { label: 'Agência', icon: 'fa-solid fa-code-branch', category: 'financas', type: 'text', isCore: false },
      conta: { label: 'Conta Bancária', icon: 'fa-solid fa-wallet', category: 'financas', type: 'text', isCore: false },
      forma_pagamento: { label: 'Forma de Pagamento', icon: 'fa-regular fa-credit-card', category: 'financas', type: 'text', isCore: false },
      linha_digitavel: { label: 'Linha Digitável (Boleto)', icon: 'fa-solid fa-barcode', category: 'financas', type: 'mono', isCore: false },
      codigo_barras: { label: 'Código de Barras', icon: 'fa-solid fa-barcode', category: 'financas', type: 'mono', isCore: false },
      vencimento: { label: 'Data de Vencimento', icon: 'fa-regular fa-calendar-xmark', category: 'financas', type: 'text', isCore: false },
      data_pagamento: { label: 'Data do Pagamento', icon: 'fa-regular fa-calendar-check', category: 'financas', type: 'text', isCore: false },
      
      // Cheques & Talonários
      numero_cheque: { label: 'Número do Cheque', icon: 'fa-solid fa-money-check-dollar', category: 'financas', type: 'mono', isCore: false },
      banco_cheque: { label: 'Banco do Cheque', icon: 'fa-solid fa-building-columns', category: 'financas', type: 'text', isCore: false },
      serie_cheque: { label: 'Série do Cheque', icon: 'fa-solid fa-tag', category: 'financas', type: 'mono', isCore: false },
      agencia_cheque: { label: 'Agência do Cheque', icon: 'fa-solid fa-code-branch', category: 'financas', type: 'mono', isCore: false },
      conta_corrente: { label: 'Conta Corrente', icon: 'fa-solid fa-wallet', category: 'financas', type: 'mono', isCore: false },
      numeros_cheque: { label: 'Cheques no Talão', icon: 'fa-solid fa-layer-group', category: 'financas', type: 'chips', isCore: false },

      // Notas Promissórias
      numero_nota: { label: 'Número da Nota Promissória', icon: 'fa-solid fa-hashtag', category: 'financas', type: 'mono', isCore: false },
      numero_promissoria: { label: 'Número da Nota Promissória', icon: 'fa-solid fa-hashtag', category: 'financas', type: 'mono', isCore: false },

      // PIX (Exibido se e somente se houver dados de PIX no documento)
      pix_chave: { label: 'Chave PIX Utilizada', icon: 'fa-solid fa-key', category: 'financas', type: 'mono', isCore: false },
      pix_e2e_id: { label: 'ID Transação Fim-a-Fim (E2E)', icon: 'fa-solid fa-fingerprint', category: 'financas', type: 'mono', isCore: false },
      pix_autenticacao: { label: 'Autenticação Bancária', icon: 'fa-solid fa-shield-halved', category: 'financas', type: 'mono', isCore: false },
      pix_pagador_nome: { label: 'Nome do Pagador (Origem)', icon: 'fa-solid fa-arrow-up-right-from-square', category: 'financas', type: 'text', isCore: false },
      pix_pagador_cpf_cnpj: { label: 'CPF/CNPJ Pagador', icon: 'fa-regular fa-id-badge', category: 'financas', type: 'mono', isCore: false },
      pix_pagador_banco: { label: 'Banco do Pagador', icon: 'fa-solid fa-building-columns', category: 'financas', type: 'text', isCore: false },
      pix_recebedor_nome: { label: 'Favorecido (Destino)', icon: 'fa-solid fa-arrow-down-left-and-up-right-to-center', category: 'financas', type: 'text', isCore: false },
      pix_recebedor_cpf_cnpj: { label: 'CPF/CNPJ Favorecido', icon: 'fa-regular fa-id-badge', category: 'financas', type: 'mono', isCore: false },
      pix_recebedor_banco: { label: 'Banco do Favorecido', icon: 'fa-solid fa-building-columns', category: 'financas', type: 'text', isCore: false },

      // Imposto de Renda & Informes Financeiros
      numero_recibo: { label: 'Número do Recibo (IRPF)', icon: 'fa-solid fa-receipt', category: 'financas', type: 'mono', isCore: false },
      exercicio: { label: 'Exercício (IRPF)', icon: 'fa-regular fa-calendar-check', category: 'financas', type: 'text', isCore: false },
      exercicio_irpf: { label: 'Exercício (IRPF)', icon: 'fa-regular fa-calendar-check', category: 'financas', type: 'text', isCore: false },
      ano_calendario: { label: 'Ano-Calendário', icon: 'fa-regular fa-calendar', category: 'financas', type: 'text', isCore: false },
      fonte_pagadora: { label: 'Fonte Pagadora', icon: 'fa-solid fa-building-columns', category: 'financas', type: 'text', isCore: false },
      cnpj_fonte_pagadora: { label: 'CNPJ Fonte Pagadora', icon: 'fa-solid fa-landmark', category: 'financas', type: 'mono', isCore: false },
      total_rendimentos_tributaveis: { label: 'Rendimentos Tributáveis (R$)', icon: 'fa-solid fa-coins', category: 'financas', type: 'currency', isCore: false },

      // Identificação & Pessoas
      beneficiario: { label: 'Nome do Titular / Beneficiário', icon: 'fa-solid fa-user', category: 'identificacao', type: 'text', isCore: true },
      nomes_detectados: { label: 'Titulares / Nomes Detectados', icon: 'fa-solid fa-users', category: 'identificacao', type: 'chips', isCore: false },
      nome: { label: 'Nome Completo', icon: 'fa-solid fa-user', category: 'identificacao', type: 'text', isCore: false },
      titular: { label: 'Nome do Titular', icon: 'fa-solid fa-user-check', category: 'identificacao', type: 'text', isCore: false },
      cpf: { label: 'CPF', icon: 'fa-solid fa-id-card', category: 'identificacao', type: 'mono', isCore: true },
      rg: { label: 'RG / Identidade', icon: 'fa-solid fa-address-card', category: 'identificacao', type: 'text', isCore: true },
      cnpj: { label: 'CNPJ', icon: 'fa-solid fa-landmark', category: 'identificacao', type: 'mono', isCore: true },
      razao_social: { label: 'Nome Empresarial (Razão Social)', icon: 'fa-solid fa-building', category: 'identificacao', type: 'text', isCore: false },
      nome_fantasia: { label: 'Nome Fantasia', icon: 'fa-solid fa-tag', category: 'identificacao', type: 'text', isCore: false },
      data_nascimento: { label: 'Data de Nascimento', icon: 'fa-regular fa-calendar', category: 'identificacao', type: 'text', isCore: false },
      filiacao: { label: 'Filiação', icon: 'fa-solid fa-people-arrows', category: 'identificacao', type: 'text', isCore: false },
      nome_mae: { label: 'Nome da Mãe', icon: 'fa-solid fa-person-dress', category: 'identificacao', type: 'text', isCore: false },
      nome_pai: { label: 'Nome do Pai', icon: 'fa-solid fa-person', category: 'identificacao', type: 'text', isCore: false },
      orgao_emissor: { label: 'Órgão Emissor / Expedidor', icon: 'fa-solid fa-building-shield', category: 'identificacao', type: 'text', isCore: false },
      naturalidade: { label: 'Naturalidade', icon: 'fa-solid fa-map-pin', category: 'identificacao', type: 'text', isCore: false },
      nacionalidade: { label: 'Nacionalidade', icon: 'fa-solid fa-globe', category: 'identificacao', type: 'text', isCore: false },
      estado_civil: { label: 'Estado Civil', icon: 'fa-solid fa-ring', category: 'identificacao', type: 'text', isCore: false },
      situacao_cadastral: { label: 'Situação Cadastral', icon: 'fa-solid fa-check-circle', category: 'identificacao', type: 'badge', isCore: false },
      data_abertura: { label: 'Data de Abertura', icon: 'fa-regular fa-calendar-days', category: 'identificacao', type: 'text', isCore: false },
      cnae_principal: { label: 'Atividade Principal (CNAE)', icon: 'fa-solid fa-briefcase', category: 'identificacao', type: 'text', isCore: false },
      natureza_juridica: { label: 'Natureza Jurídica', icon: 'fa-solid fa-scale-balanced', category: 'identificacao', type: 'text', isCore: false },

      // Acadêmico
      curso: { label: 'Nome do Curso / Habilitação', icon: 'fa-solid fa-graduation-cap', category: 'academico', type: 'textarea', isCore: true },
      natureza_curso: { label: 'Nível / Natureza do Curso', icon: 'fa-solid fa-award', category: 'academico', type: 'text', isCore: true },
      carga_horaria: { label: 'Carga Horária', icon: 'fa-solid fa-clock', category: 'academico', type: 'text', isCore: true },
      faculdade: { label: 'Instituição de Ensino / Emissora', icon: 'fa-solid fa-university', category: 'academico', type: 'text', isCore: true },
      instituicao: { label: 'Instituição', icon: 'fa-solid fa-university', category: 'academico', type: 'text', isCore: false },
      conclusao: { label: 'Data de Conclusão', icon: 'fa-regular fa-calendar-check', category: 'academico', type: 'text', isCore: false },
      registro_diploma: { label: 'Nº do Registro do Diploma', icon: 'fa-solid fa-certificate', category: 'academico', type: 'mono', isCore: false },

      // Dados do Documento & Registros Específicos
      data: { label: 'Data do Documento', icon: 'fa-regular fa-calendar-days', category: 'documento', type: 'text', isCore: true },
      placa: { label: 'Placa do Veículo', icon: 'fa-solid fa-car-side', category: 'documento', type: 'mono', isCore: false },
      placa_veiculo: { label: 'Placa do Veículo', icon: 'fa-solid fa-car-side', category: 'documento', type: 'mono', isCore: false },
      renavam: { label: 'Código RENAVAM', icon: 'fa-solid fa-file-invoice', category: 'documento', type: 'mono', isCore: false },
      chassi: { label: 'Número do Chassi', icon: 'fa-solid fa-shield-halved', category: 'documento', type: 'mono', isCore: false },
      ano_fabricacao: { label: 'Ano de Fabricação', icon: 'fa-solid fa-calendar', category: 'documento', type: 'text', isCore: false },
      ano_modelo: { label: 'Ano / Modelo', icon: 'fa-solid fa-car', category: 'documento', type: 'text', isCore: false },
      combustivel: { label: 'Combustível', icon: 'fa-solid fa-gas-pump', category: 'documento', type: 'text', isCore: false },
      cor_veiculo: { label: 'Cor do Veículo', icon: 'fa-solid fa-palette', category: 'documento', type: 'text', isCore: false },
      numero_processo: { label: 'Número do Processo', icon: 'fa-solid fa-gavel', category: 'documento', type: 'mono', isCore: false },
      vara: { label: 'Vara / Juizado', icon: 'fa-solid fa-landmark', category: 'documento', type: 'text', isCore: false },
      comarca: { label: 'Comarca / Foro', icon: 'fa-solid fa-map-marked-alt', category: 'documento', type: 'text', isCore: false },
      tribunal: { label: 'Tribunal', icon: 'fa-solid fa-balance-scale', category: 'documento', type: 'text', isCore: false },
      outorgante: { label: 'Outorgante', icon: 'fa-solid fa-file-signature', category: 'documento', type: 'text', isCore: false },
      outorgado: { label: 'Outorgado', icon: 'fa-solid fa-user-check', category: 'documento', type: 'text', isCore: false },
      vigencia: { label: 'Prazo de Vigência', icon: 'fa-regular fa-clock', category: 'documento', type: 'text', isCore: false },

      // Escrita Manual & Manuscritos
      manuscrito: { label: 'Documento Manuscrito', icon: 'fa-solid fa-pen-nib', category: 'documento', type: 'badge', isCore: false },
      preenchido_a_mao: { label: 'Preenchido à Mão', icon: 'fa-solid fa-pen-fancy', category: 'documento', type: 'badge', isCore: false },
      emitente: { label: 'Emitente / Responsável', icon: 'fa-solid fa-user-pen', category: 'identificacao', type: 'text', isCore: false },
      referente_a: { label: 'Referente a / Finalidade', icon: 'fa-solid fa-file-signature', category: 'documento', type: 'textarea', isCore: false },
      conteudo_manuscrito: { label: 'Conteúdo Manuscrito (Transcrição)', icon: 'fa-solid fa-pen-nib', category: 'documento', type: 'textarea', isCore: false },
      observacoes_manuscritas: { label: 'Observações Manuscritas', icon: 'fa-solid fa-note-sticky', category: 'documento', type: 'textarea', isCore: false },

      // Contato & Localidade
      endereco_completo: { label: 'Endereço Completo', icon: 'fa-solid fa-location-dot', category: 'contato', type: 'textarea', isCore: false },
      endereco: { label: 'Endereço', icon: 'fa-solid fa-location-dot', category: 'contato', type: 'textarea', isCore: false },
      cidade: { label: 'Município / Cidade', icon: 'fa-solid fa-city', category: 'contato', type: 'text', isCore: false },
      uf: { label: 'UF / Estado', icon: 'fa-solid fa-flag', category: 'contato', type: 'text', isCore: false },
      cep: { label: 'CEP', icon: 'fa-solid fa-mail-bulk', category: 'contato', type: 'mono', isCore: false },
      telefone: { label: 'Telefone', icon: 'fa-solid fa-phone', category: 'contato', type: 'text', isCore: false },
      email: { label: 'E-mail', icon: 'fa-solid fa-envelope', category: 'contato', type: 'text', isCore: false }
    };

    const CATEGORY_CONFIG = {
      financas: {
        title: 'Valores & Dados Financeiros',
        icon: 'fa-solid fa-coins',
        color: 'emerald',
        badgeBg: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
      },
      identificacao: {
        title: 'Pessoas & Identificação',
        icon: 'fa-solid fa-id-card',
        color: 'cyan',
        badgeBg: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30'
      },
      academico: {
        title: 'Qualificação & Metadados Acadêmicos',
        icon: 'fa-solid fa-graduation-cap',
        color: 'indigo',
        badgeBg: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
      },
      documento: {
        title: 'Dados Específicos do Documento',
        icon: 'fa-solid fa-file-lines',
        color: 'amber',
        badgeBg: 'bg-amber-500/20 text-amber-400 border-amber-500/30'
      },
      contato: {
        title: 'Endereço & Contatos',
        icon: 'fa-solid fa-location-dot',
        color: 'rose',
        badgeBg: 'bg-rose-500/20 text-rose-400 border-rose-500/30'
      },
      outros: {
        title: 'Atributos & Informações Complementares',
        icon: 'fa-solid fa-sliders',
        color: 'slate',
        badgeBg: 'bg-slate-800 text-slate-300 border-slate-700'
      }
    };

    function getCanonicalFieldMeta(key) {
      if (CANONICAL_FIELD_MAP[key]) {
        return CANONICAL_FIELD_MAP[key];
      }
      const friendlyLabel = key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase());
      return {
        label: friendlyLabel,
        icon: 'fa-solid fa-tag',
        category: 'outros',
        type: 'text',
        isCore: false
      };
    }

    function extractActiveDocumentFields(doc) {
      if (!doc) return [];
      const fields = [];
      const seen = new Set();
      const de = (doc.dados_extras && typeof doc.dados_extras === 'object') ? doc.dados_extras : {};
      const internalKeys = new Set([
        'dossie_paginas', 'todos_dominios', 'todos_tipos', 'data_criacao',
        'texto_transcrito', 'texto_ocr', 'texto_digital', 'transcricao_completa'
      ]);

      const candidateEntries = [
        { key: 'valor_monetario', val: doc.valor_monetario },
        { key: 'beneficiario', val: doc.beneficiario },
        { key: 'cpf', val: doc.cpf },
        { key: 'rg', val: doc.rg },
        { key: 'cnpj', val: doc.cnpj || de.cnpj },
        { key: 'curso', val: doc.curso },
        { key: 'natureza_curso', val: doc.natureza_curso },
        { key: 'carga_horaria', val: doc.carga_horaria },
        { key: 'faculdade', val: doc.faculdade },
        { key: 'data', val: doc.data },
        { key: 'pix_chave', val: doc.pix_chave || de.pix_chave },
        { key: 'pix_e2e_id', val: doc.pix_e2e_id || de.pix_e2e_id },
        { key: 'pix_autenticacao', val: doc.pix_autenticacao || de.pix_autenticacao },
        { key: 'pix_pagador_nome', val: doc.pix_pagador_nome || de.pix_pagador_nome },
        { key: 'pix_pagador_cpf_cnpj', val: doc.pix_pagador_cpf_cnpj || de.pix_pagador_cpf_cnpj },
        { key: 'pix_pagador_banco', val: doc.pix_pagador_banco || de.pix_pagador_banco },
        { key: 'pix_recebedor_nome', val: doc.pix_recebedor_nome || de.pix_recebedor_nome },
        { key: 'pix_recebedor_cpf_cnpj', val: doc.pix_recebedor_cpf_cnpj || de.pix_recebedor_cpf_cnpj },
        { key: 'pix_recebedor_banco', val: doc.pix_recebedor_banco || de.pix_recebedor_banco }
      ];

      Object.keys(de).forEach(k => {
        if (!internalKeys.has(k)) {
          candidateEntries.push({ key: k, val: de[k] });
        }
      });

      candidateEntries.forEach(item => {
        if (seen.has(item.key)) return;
        seen.add(item.key);

        if (item.val === null || item.val === undefined) return;
        if (typeof item.val === 'object') return;
        const strVal = String(item.val).trim();
        
        // REGRA ZERO NOISE: descarta brancos, vazios ou marcadores nulos
        if (!strVal || strVal === '-' || strVal === '--' || strVal === 'N/A' || strVal.toLowerCase() === 'null' || strVal.toLowerCase() === 'none' || strVal.toLowerCase() === 'não informado' || strVal.toLowerCase() === 'nao informado') {
          return;
        }

        const meta = getCanonicalFieldMeta(item.key);
        fields.push({
          key: item.key,
          val: strVal,
          meta: meta
        });
      });

      return fields;
    }

    function renderHeroBadges(doc, activeFields) {
      const container = document.getElementById('dynamicHeroBadges');
      if (!container) return;
      container.innerHTML = '';

      const pills = [];

      // Valor Monetário
      const valField = activeFields.find(f => f.key === 'valor_monetario' || f.key === 'valor');
      if (valField) {
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-mono text-xs font-semibold shadow-sm">
            <i class="fa-solid fa-coins text-emerald-400 text-[11px]"></i>
            <span>${escapeHtml(valField.val)}</span>
            <button type="button" onclick="navigator.clipboard.writeText('${escapeHtml(valField.val)}'); showToast('Valor copiado!', 'success');" title="Copiar Valor" class="hover:text-white ml-0.5 text-[10px]">
              <i class="fa-regular fa-copy"></i>
            </button>
          </div>
        `);
      }

      // PIX (somente e estritamente se houver chave pix ou id e2e)
      const hasPix = activeFields.some(f => f.key === 'pix_chave' || f.key === 'pix_e2e_id');
      if (hasPix) {
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-teal-500/15 border border-teal-500/30 text-teal-300 font-mono text-[11px] font-semibold">
            <i class="fa-brands fa-pix text-teal-400"></i>
            <span>PIX</span>
          </div>
        `);
      }

      // Boleto Bancário
      const hasBoleto = activeFields.some(f => f.key === 'linha_digitavel' || f.key === 'codigo_barras') || (doc.tipo_documento || '').toLowerCase().includes('boleto');
      if (hasBoleto) {
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-300 font-mono text-[11px] font-semibold">
            <i class="fa-solid fa-barcode text-amber-400"></i>
            <span>Boleto</span>
          </div>
        `);
      }

      // Cheque / Talão de Cheques
      const hasCheque = activeFields.some(f => f.key === 'numero_cheque' || f.key === 'numeros_cheque') || (doc.tipo_documento || '').toLowerCase().includes('cheque') || (doc.tipo_documento || '').toLowerCase().includes('talao');
      if (hasCheque) {
        const isTalao = (doc.tipo_documento || '').toLowerCase().includes('talao') || (doc.dados_extras?.numeros_cheque && doc.dados_extras.numeros_cheque.length > 1);
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-mono text-[11px] font-semibold shadow-sm">
            <i class="fa-solid fa-money-check-dollar text-emerald-400"></i>
            <span>${isTalao ? 'Talão de Cheques' : 'Cheque'}</span>
          </div>
        `);
      }

      // Imposto de Renda / Recibo de Entrega
      const hasIrpf = activeFields.some(f => f.key === 'numero_recibo' || f.key === 'exercicio' || f.key === 'exercicio_irpf') || (doc.tipo_documento || '').toLowerCase().includes('ajuste anual') || (doc.tipo_documento || '').toLowerCase().includes('imposto de renda') || (Array.isArray(doc.todos_tipos) && doc.todos_tipos.some(t => safeString(t).toLowerCase().includes('imposto de renda') || safeString(t).toLowerCase().includes('ajuste anual')));
      if (hasIrpf) {
        const exVal = activeFields.find(f => f.key === 'exercicio' || f.key === 'exercicio_irpf')?.val || doc.dados_extras?.exercicio || doc.dados_extras?.exercicio_irpf || '';
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-sans text-[11px] font-semibold shadow-sm">
            <i class="fa-solid fa-file-invoice-dollar text-emerald-400"></i>
            <span>IRPF ${exVal ? `(${escapeHtml(exVal)})` : ''}</span>
          </div>
        `);
      }

      // Documento Manuscrito / Preenchido à Mão
      const isHandwritten = (
        doc.manuscrito === true ||
        doc.dados_extras?.manuscrito === true ||
        doc.dados_extras?.manuscrito === 'true' ||
        activeFields.some(f => f.key === 'manuscrito' && (f.val === true || f.val === 'true' || String(f.val).toLowerCase() === 'sim')) ||
        (Array.isArray(doc.todos_tipos) && doc.todos_tipos.some(t => {
          const tl = safeString(t).toLowerCase();
          return tl.includes('manuscrito') || tl.includes('preenchido a mão') || tl.includes('preenchido à mão') || tl.includes('próprio punho') || tl.includes('proprio punho');
        }))
      );
      if (isHandwritten) {
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-300 font-sans text-[11px] font-semibold shadow-sm" title="Documento com escrita manual ou preenchido à mão com caneta">
            <i class="fa-solid fa-pen-nib text-amber-400"></i>
            <span>Preenchido à Mão</span>
          </div>
        `);
      }

      // Placa de Veículo
      const placaField = activeFields.find(f => f.key === 'placa' || f.key === 'placa_veiculo');
      if (placaField) {
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-sky-500/15 border border-sky-500/30 text-sky-300 font-mono text-[11px] font-semibold uppercase">
            <i class="fa-solid fa-car text-sky-400"></i>
            <span>${escapeHtml(placaField.val)}</span>
          </div>
        `);
      }

      // Data do Documento
      const dataField = activeFields.find(f => f.key === 'data');
      if (dataField) {
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 font-mono text-[11px]">
            <i class="fa-regular fa-calendar-days text-slate-400"></i>
            <span>${escapeHtml(dataField.val)}</span>
          </div>
        `);
      }

      // CPF / CNPJ
      const cpfField = activeFields.find(f => f.key === 'cpf');
      if (cpfField) {
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-800/80 border border-slate-700/80 text-slate-300 font-mono text-[11px]">
            <i class="fa-solid fa-id-card text-cyan-400"></i>
            <span>CPF: ${escapeHtml(cpfField.val)}</span>
          </div>
        `);
      }
      const cnpjField = activeFields.find(f => f.key === 'cnpj');
      if (cnpjField) {
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-800/80 border border-slate-700/80 text-sky-300 font-mono text-[11px]">
            <i class="fa-solid fa-landmark text-sky-400"></i>
            <span>CNPJ: ${escapeHtml(cnpjField.val)}</span>
          </div>
        `);
      }

      // Micro-Badge: Assinatura Digital Criptográfica (PAdES / ICP-Brasil)
      if (doc.tem_assinatura_digital) {
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 font-sans text-[11px] font-semibold" title="Assinatura Digital Criptográfica (PAdES / ICP-Brasil)">
            <i class="fa-solid fa-certificate text-emerald-400"></i>
            <span>Assinado Digitalmente</span>
          </div>
        `);
      }

      // Micro-Badge: Duplicata Detectada
      if (doc.duplicata_de) {
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-300 font-sans text-[11px] font-semibold" title="Duplicata detectada de ${escapeHtml(doc.duplicata_de)}">
            <i class="fa-solid fa-copy text-amber-400"></i>
            <span>Duplicata (${Math.round((doc.similaridade_duplicata || 1) * 100)}%)</span>
          </div>
        `);
      }

      // Micro-Badge: Dossiê Integrado
      if (doc.dossie_id) {
        pills.push(`
          <div class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-indigo-500/20 border border-indigo-500/40 text-indigo-300 font-sans text-[11px] font-semibold" title="Vinculado ao Dossiê ${escapeHtml(doc.dossie_id)}">
            <i class="fa-solid fa-folder-tree text-indigo-400"></i>
            <span>Dossiê ${escapeHtml(doc.dossie_id)}</span>
          </div>
        `);
      }

      container.innerHTML = pills.join('');
    }

    function renderDynamicInspector(doc) {
      const container = document.getElementById('dynamicSectionsContainer');
      const emptyState = document.getElementById('dynamicEmptyState');
      if (!container || !doc) return;

      const activeFields = extractActiveDocumentFields(doc);

      // Renderiza Hero Badges no topo
      renderHeroBadges(doc, activeFields);

      const de_doc = (doc.dados_extras && typeof doc.dados_extras === 'object') ? doc.dados_extras : {};
      const rawNomesAll = (Array.isArray(doc.nomes_detectados) && doc.nomes_detectados.length > 0)
        ? doc.nomes_detectados
        : ((Array.isArray(de_doc.nomes_detectados) && de_doc.nomes_detectados.length > 0) ? de_doc.nomes_detectados : []);

      if (activeFields.length === 0 && rawNomesAll.length === 0) {
        container.innerHTML = '';
        if (emptyState) emptyState.classList.remove('hidden');
        return;
      }

      if (emptyState) emptyState.classList.add('hidden');

      // Agrupamento por Categoria
      const groups = {
        financas: [],
        identificacao: [],
        academico: [],
        documento: [],
        contato: [],
        outros: []
      };

      activeFields.forEach(f => {
        const cat = f.meta.category || 'outros';
        if (groups[cat]) {
          groups[cat].push(f);
        } else {
          groups.outros.push(f);
        }
      });

      const categoryOrder = ['financas', 'identificacao', 'academico', 'documento', 'contato', 'outros'];
      let html = '';

      categoryOrder.forEach(catKey => {
        const fields = groups[catKey] || [];
        const isIdent = catKey === 'identificacao';
        const hasNomes = isIdent && rawNomesAll.length > 0;

        if (fields.length === 0 && !hasNomes) return; // ZERO NOISE: Categoria vazia não é renderizada!

        const catConf = CATEGORY_CONFIG[catKey] || CATEGORY_CONFIG.outros;
        const isFinancas = catKey === 'financas';
        const hasPix = isFinancas && activeFields.some(f => f.key === 'pix_chave' || f.key === 'pix_e2e_id');

        const totalItemsCount = fields.length + (hasNomes ? 1 : 0);

        html += `
          <div class="bg-slate-900/85 border border-slate-800 rounded-xl p-3.5 space-y-3 shadow-sm transition-all">
            <!-- Cabeçalho da Seção -->
            <div class="flex items-center justify-between pb-2 border-b border-slate-800/80">
              <div class="flex items-center gap-2">
                <div class="w-6 h-6 rounded-lg bg-slate-800 flex items-center justify-center text-${catConf.color}-400 text-xs">
                  <i class="${catConf.icon}"></i>
                </div>
                <h4 class="text-xs font-bold text-slate-200 uppercase tracking-wide">${catConf.title}</h4>
              </div>
              <div class="flex items-center gap-1.5">
                ${hasPix ? `
                  <button type="button" onclick="removePixFromCurrentDoc()"
                          class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/40 text-[10px] font-medium flex items-center gap-1 transition"
                          title="Remover chaves de PIX e desvincular deste documento">
                    <i class="fa-solid fa-ban text-[9px] text-rose-400"></i> Desvincular PIX
                  </button>
                  <span class="bg-teal-500/20 text-teal-300 text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold border border-teal-500/30">PIX OFICIAL</span>
                ` : `
                  <span class="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full border ${catConf.badgeBg}">
                    ${totalItemsCount} ${totalItemsCount === 1 ? 'campo' : 'campos'}
                  </span>
                `}
              </div>
            </div>

            <!-- Grade de Campos da Seção -->
            <div class="space-y-2.5">
        `;

        // Seção Identificação: Renderiza primeiro o Beneficiário Principal se existir
        const benefField = fields.find(f => f.key === 'beneficiario');
        if (benefField) {
          const inputId = `input_${benefField.key}`;
          html += `
            <div class="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/90 hover:border-slate-700 transition space-y-1">
              <div class="flex items-center justify-between">
                <label for="${inputId}" class="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                  <i class="${benefField.meta.icon} text-[11px] text-${catConf.color}-400"></i>
                  <span>${escapeHtml(benefField.meta.label)}</span>
                </label>
                <div class="flex items-center gap-1.5">
                  <span class="text-[10px] text-slate-500 font-mono">${escapeHtml(benefField.key)}</span>
                  <button type="button" onclick="copyFieldValue('${inputId}', '${escapeHtml(benefField.meta.label)}', this)"
                          class="text-[10px] text-slate-400 hover:text-emerald-400 flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-slate-800 transition" title="Copiar valor">
                    <i class="fa-regular fa-copy"></i>
                  </button>
                  <button type="button" onclick="removeDynamicField('${escapeHtml(benefField.key)}')"
                          class="text-[10px] text-slate-500 hover:text-rose-400 px-1 py-0.5 rounded hover:bg-slate-800 transition" title="Remover este campo do documento">
                    <i class="fa-solid fa-xmark"></i>
                  </button>
                </div>
              </div>
              <input type="text" id="${inputId}" data-dynamic-key="${escapeHtml(benefField.key)}" value="${escapeHtml(benefField.val)}" oninput="onDynamicFieldInput('${escapeHtml(benefField.key)}', this.value)"
                     class="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-${catConf.color}-500 font-medium">
            </div>
          `;
        }

        // Bloco Especial: Múltiplos Nomes / Titulares Detectados (Pilar 3)
        if (hasNomes) {
          const totalNomes = rawNomesAll.length;
          const initialLimit = 5;
          const hasMore = totalNomes > initialLimit;
          const moreClass = `nomes_more_${doc.md5 || 'curr'}`;
          const btnId = `nomes_btn_${doc.md5 || 'curr'}`;

          html += `
            <div class="bg-indigo-950/40 border border-indigo-500/30 rounded-lg p-2.5 space-y-2">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-1.5 text-xs font-semibold text-indigo-300">
                  <i class="fa-solid fa-users text-indigo-400"></i>
                  <span>Titulares / Nomes Detectados</span>
                  <span class="text-[10px] bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-1.5 py-0.2 rounded-full font-mono font-bold">${totalNomes}</span>
                </div>
                <div class="flex items-center gap-1">
                  <button type="button" onclick="copyAllDetectedNames('${doc.md5}')"
                          class="px-2 py-0.5 rounded bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-200 border border-indigo-500/30 text-[10px] font-medium flex items-center gap-1 transition"
                          title="Copiar todos os nomes detectados para a área de transferência">
                    <i class="fa-regular fa-copy text-[10px]"></i> Copiar Todos
                  </button>
                </div>
              </div>

              <!-- Chips interativos -->
              <div class="flex flex-wrap gap-1.5">
          `;

          rawNomesAll.forEach((nome, idx) => {
            const isHidden = hasMore && idx >= initialLimit;
            html += `
              <div class="group inline-flex items-center gap-1 px-2 py-1 rounded-md bg-slate-900 border border-indigo-500/30 text-indigo-200 text-xs hover:border-indigo-400 hover:bg-indigo-900/30 transition ${isHidden ? `${moreClass} hidden` : ''}"
                   title="Clique no nome para copiar ou na lupa para localizar na aba de Texto">
                <button type="button" onclick="copyIndividualName('${escapeHtml(nome)}')" class="font-medium hover:text-white text-left select-text">
                  ${escapeHtml(nome)}
                </button>
                <button type="button" onclick="searchNameInDocText('${escapeHtml(nome)}')" class="text-[10px] text-indigo-400/60 hover:text-cyan-300 ml-0.5" title="Localizar '${escapeHtml(nome)}' na aba de Texto">
                  <i class="fa-solid fa-magnifying-glass"></i>
                </button>
              </div>
            `;
          });

          html += `
              </div>
          `;

          if (hasMore) {
            html += `
              <div class="pt-1">
                <button type="button" id="${btnId}" onclick="toggleNomesExpand('${moreClass}', '${btnId}', ${totalNomes})"
                        class="text-[11px] text-indigo-400 hover:text-indigo-200 flex items-center gap-1 font-medium transition">
                  <i class="fa-solid fa-chevron-down text-[9px]"></i>
                  <span>Ver todos os ${totalNomes} nomes (+${totalNomes - initialLimit} adicionais)</span>
                </button>
              </div>
            `;
          }

          html += `
            </div>
          `;
        }

        // Renderiza os demais campos da categoria (exceto beneficiario que já foi renderizado acima)
        fields.forEach(f => {
          if (isIdent && f.key === 'beneficiario') return;
          const isTextarea = f.meta.type === 'textarea' || f.val.length > 70;
          const isCurrency = f.meta.type === 'currency' || f.key === 'valor_monetario';
          const inputId = `input_${f.key}`;

          html += `
            <div class="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/90 hover:border-slate-700 transition space-y-1">
              <div class="flex items-center justify-between">
                <label for="${inputId}" class="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                  <i class="${f.meta.icon} text-[11px] text-${catConf.color}-400"></i>
                  <span>${escapeHtml(f.meta.label)}</span>
                </label>
                <div class="flex items-center gap-1.5">
                  <span class="text-[10px] text-slate-500 font-mono">${escapeHtml(f.key)}</span>
                  <button type="button" onclick="copyFieldValue('${inputId}', '${escapeHtml(f.meta.label)}', this)"
                          class="text-[10px] text-slate-400 hover:text-emerald-400 flex items-center gap-1 px-1.5 py-0.5 rounded hover:bg-slate-800 transition" title="Copiar valor">
                    <i class="fa-regular fa-copy"></i>
                  </button>
                  <button type="button" onclick="removeDynamicField('${escapeHtml(f.key)}')"
                          class="text-[10px] text-slate-500 hover:text-rose-400 px-1 py-0.5 rounded hover:bg-slate-800 transition" title="Remover este campo do documento">
                    <i class="fa-solid fa-xmark"></i>
                  </button>
                </div>
              </div>

              ${isTextarea ? `
                <textarea id="${inputId}" data-dynamic-key="${escapeHtml(f.key)}" oninput="onDynamicFieldInput('${escapeHtml(f.key)}', this.value)" rows="2"
                          class="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-${catConf.color}-500 resize-none font-sans">${escapeHtml(f.val)}</textarea>
              ` : `
                <input type="text" id="${inputId}" data-dynamic-key="${escapeHtml(f.key)}" value="${escapeHtml(f.val)}" oninput="onDynamicFieldInput('${escapeHtml(f.key)}', this.value)"
                       class="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-${catConf.color}-500 ${isCurrency ? 'text-sm font-bold font-mono text-emerald-300' : (f.meta.type === 'mono' ? 'font-mono' : '')}">
              `}
            </div>
          `;
        });

        html += `
            </div>
          </div>
        `;
      });

      container.innerHTML = html;
    }

    function copyIndividualName(nome) {
      if (!nome) return;
      navigator.clipboard.writeText(nome);
      showToast(`Nome "${nome}" copiado!`, 'success');
    }

    function copyAllDetectedNames(md5) {
      let doc = null;
      if (currentIndex >= 0 && filteredDocs && filteredDocs[currentIndex]) {
        doc = filteredDocs[currentIndex];
      }
      if (!doc && md5) {
        doc = documents.find(d => d.md5 === md5);
      }
      if (!doc) return;
      const de = doc.dados_extras || {};
      const nomes = Array.isArray(doc.nomes_detectados) ? doc.nomes_detectados : (Array.isArray(de.nomes_detectados) ? de.nomes_detectados : []);
      if (!nomes || nomes.length === 0) {
        showToast('Nenhum nome para copiar.', 'info');
        return;
      }
      navigator.clipboard.writeText(nomes.join('\\n'));
      showToast(`${nomes.length} nomes copiados para a área de transferência!`, 'success');
    }

    function searchNameInDocText(nome) {
      if (!nome) return;
      switchInspectorTab('texto');
      const searchInput = document.getElementById('searchDocTextInput');
      if (searchInput) {
        searchInput.value = nome;
        onSearchDocTextInput(nome);
      }
      showToast(`Localizando "${nome}" no texto...`, 'info');
    }

    function toggleNomesExpand(moreClass, btnId, totalNomes) {
      const elements = document.querySelectorAll(`.${moreClass}`);
      const btn = document.getElementById(btnId);
      if (!elements || elements.length === 0 || !btn) return;
      const isCurrentlyHidden = elements[0].classList.contains('hidden');
      elements.forEach(el => {
        if (isCurrentlyHidden) {
          el.classList.remove('hidden');
        } else {
          el.classList.add('hidden');
        }
      });
      if (isCurrentlyHidden) {
        btn.innerHTML = `
          <i class="fa-solid fa-chevron-up text-[9px]"></i>
          <span>Recolher lista de nomes</span>
        `;
      } else {
        btn.innerHTML = `
          <i class="fa-solid fa-chevron-down text-[9px]"></i>
          <span>Ver todos os ${totalNomes} nomes (+${totalNomes - 5} adicionais)</span>
        `;
      }
    }

    function onDynamicFieldInput(key, val) {
      markDirty();
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      const meta = getCanonicalFieldMeta(key);

      if (meta.isCore) {
        doc[key] = val;
      }
      if (!doc.dados_extras || typeof doc.dados_extras !== 'object') {
        doc.dados_extras = {};
      }
      doc.dados_extras[key] = val;

      updateJsonView();
    }

    function removeDynamicField(key) {
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      const meta = getCanonicalFieldMeta(key);

      if (meta.isCore) {
        doc[key] = null;
      }
      if (doc.dados_extras && typeof doc.dados_extras === 'object') {
        delete doc.dados_extras[key];
      }
      delete doc[key];

      markDirty();
      renderDynamicInspector(doc);
      updateJsonView();
      showToast(`Campo "${meta.label}" removido.`, 'info');
    }

    function openAddDynamicFieldModal() {
      const modal = document.getElementById('modalAddDynamicField');
      if (modal) {
        document.getElementById('quickSelectDynamicField').value = '';
        document.getElementById('dynamicFieldKeyInput').value = '';
        document.getElementById('dynamicFieldValueInput').value = '';
        modal.classList.remove('hidden');
        document.getElementById('dynamicFieldKeyInput').focus();
      }
    }

    function closeAddDynamicFieldModal() {
      const modal = document.getElementById('modalAddDynamicField');
      if (modal) modal.classList.add('hidden');
    }

    function onQuickSelectDynamicFieldChange() {
      const val = document.getElementById('quickSelectDynamicField').value;
      if (val) {
        const parts = val.split('|');
        const key = parts[0];
        document.getElementById('dynamicFieldKeyInput').value = key;
        document.getElementById('dynamicFieldValueInput').focus();
      }
    }

    function confirmAddDynamicField() {
      const rawKey = (document.getElementById('dynamicFieldKeyInput').value || '').trim();
      const val = (document.getElementById('dynamicFieldValueInput').value || '').trim();

      if (!rawKey) {
        showToast('Informe o nome do atributo.', 'warning');
        return;
      }
      if (!val) {
        showToast('Informe o valor do atributo.', 'warning');
        return;
      }

      const cleanKey = rawKey.toLowerCase().replace(/[^a-z0-9_]/g, '_');
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) {
        closeAddDynamicFieldModal();
        return;
      }

      const doc = filteredDocs[currentIndex];
      const meta = getCanonicalFieldMeta(cleanKey);

      if (meta.isCore) {
        doc[cleanKey] = val;
      }
      if (!doc.dados_extras || typeof doc.dados_extras !== 'object') {
        doc.dados_extras = {};
      }
      doc.dados_extras[cleanKey] = val;

      closeAddDynamicFieldModal();
      markDirty();
      renderDynamicInspector(doc);
      updateJsonView();
      showToast(`Atributo "${meta.label}" adicionado!`, 'success');
    }

    // Aliases para retrocompatibilidade
    function renderCustomMetaFields(doc) {
      renderDynamicInspector(doc);
    }

    function addCustomMetaKey() {
      openAddDynamicFieldModal();
    }

    function updateCustomMetaVal(key, val) {
      onDynamicFieldInput(key, val);
    }

    function removeCustomMetaKey(key) {
      removeDynamicField(key);
    }

    // -----------------------------------------------------------------------
    // Funções do Dossiê Multi-Documento e Tags Interativas
    // -----------------------------------------------------------------------
    function renderMultiTags(doc) {
      const container = document.getElementById('multiTagsContainer');
      if (!container) return;
      container.innerHTML = '';

      if (!doc) return;
      let tipos = Array.isArray(doc.todos_tipos) ? [...doc.todos_tipos] : [];
      if (tipos.length === 0 && doc.tipo_documento) {
        tipos = [doc.tipo_documento];
        doc.todos_tipos = tipos;
      }

      const primaryTipo = safeString(doc.tipo_documento || (tipos.length > 0 ? tipos[0] : '')).trim();

      if (tipos.length === 0) {
        container.innerHTML = '<span class="text-[11px] text-slate-500 italic p-1">Nenhum documento listado. Clique em "+ Adicionar".</span>';
        return;
      }

      tipos.forEach(tipo => {
        const cleanTipo = safeString(tipo).trim();
        if (!cleanTipo) return;
        const isPrimary = cleanTipo.toLowerCase() === primaryTipo.toLowerCase();
        const tLower = cleanTipo.toLowerCase();
        const isHandwritingTag = tLower.includes('manuscrito') || tLower.includes('mão') || tLower.includes('mao') || tLower.includes('punho');

        const tagStyle = isPrimary
          ? 'bg-emerald-500/20 text-emerald-200 border border-emerald-500/50 shadow-sm ring-1 ring-emerald-500/30'
          : (isHandwritingTag
              ? 'bg-amber-500/15 text-amber-300 border border-amber-500/40 hover:bg-amber-500/25 shadow-sm'
              : 'bg-slate-800/90 text-slate-300 border border-slate-700 hover:border-slate-600 hover:bg-slate-800');

        const tagEl = document.createElement('div');
        tagEl.className = `inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium transition-all ${tagStyle}`;

        // Ícone temático
        let iconClass = 'fa-regular fa-file text-slate-400';
        if (tLower.includes('diploma') || tLower.includes('certificado')) iconClass = 'fa-solid fa-graduation-cap text-purple-400';
        else if (tLower.includes('histórico') || tLower.includes('historico')) iconClass = 'fa-solid fa-book-bookmark text-indigo-400';
        else if (tLower.includes('cnh') || tLower.includes('rg') || tLower.includes('cpf') || tLower.includes('identidade') || tLower.includes('passaporte') || tLower.includes('eleitor')) iconClass = 'fa-regular fa-id-card text-cyan-400';
        else if (tLower.includes('certidão') || tLower.includes('certidao')) iconClass = 'fa-solid fa-scroll text-amber-400';
        else if (isHandwritingTag) iconClass = 'fa-solid fa-pen-nib text-amber-400';
        else if (tLower.includes('pix') || tLower.includes('pagamento') || tLower.includes('recibo') || tLower.includes('boleto')) iconClass = 'fa-solid fa-money-bill-wave text-emerald-400';
        else if (tLower.includes('procuração') || tLower.includes('procuracao') || tLower.includes('contrato') || tLower.includes('posse')) iconClass = 'fa-solid fa-gavel text-amber-400';

        // Estrela de Principal
        const starBtn = document.createElement('button');
        starBtn.type = 'button';
        starBtn.title = isPrimary ? 'Documento Principal deste arquivo' : 'Clique para eleger como Documento Principal';
        starBtn.className = isPrimary ? 'text-amber-400 hover:text-amber-300 ml-0.5' : 'text-slate-500 hover:text-amber-400 ml-0.5';
        starBtn.innerHTML = `<i class="fa-${isPrimary ? 'solid' : 'regular'} fa-star text-[10px]"></i>`;
        starBtn.onclick = (e) => {
          e.stopPropagation();
          setPrimaryTag(cleanTipo);
        };

        // Texto do Tipo
        const textSpan = document.createElement('span');
        textSpan.className = 'select-none truncate max-w-[150px]';
        textSpan.innerText = cleanTipo;
        textSpan.title = cleanTipo;

        // Botão Remover (×)
        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.title = `Remover "${cleanTipo}" deste arquivo`;
        delBtn.className = 'text-slate-500 hover:text-rose-400 hover:bg-slate-700/50 rounded p-0.5 transition-colors ml-0.5';
        delBtn.innerHTML = '<i class="fa-solid fa-xmark text-[10px]"></i>';
        delBtn.onclick = (e) => {
          e.stopPropagation();
          removeTag(cleanTipo);
        };

        tagEl.innerHTML = `<i class="${iconClass} text-[10px]"></i>`;
        tagEl.appendChild(textSpan);
        tagEl.appendChild(starBtn);
        tagEl.appendChild(delBtn);

        container.appendChild(tagEl);
      });
    }

    function renderDossierPageShortcuts(doc) {
      const container = document.getElementById('dossierPageShortcuts');
      const list = document.getElementById('dossierPageList');
      if (!container || !list) return;

      if (!doc || !Array.isArray(doc.dossie_paginas) || doc.dossie_paginas.length <= 1) {
        container.classList.add('hidden');
        list.innerHTML = '';
        return;
      }

      container.classList.remove('hidden');
      list.innerHTML = '';

      doc.dossie_paginas.forEach(p => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.id = `dossierShortcutPage_${p.pagina}`;
        const isActive = (currentDossieActivePage === p.pagina);
        btn.className = isActive
          ? 'px-1.5 py-0.5 rounded bg-emerald-600 text-white font-semibold border border-emerald-500 text-[10px] flex items-center gap-1 transition-colors shadow-sm'
          : 'px-1.5 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/70 text-[10px] flex items-center gap-1 transition-colors';
        btn.title = `Pular para a página ${p.pagina} (${p.tipo})`;
        btn.innerHTML = `<span class="font-mono ${isActive ? 'text-white font-bold' : 'text-cyan-400 font-semibold'}">P.${p.pagina}</span> <span class="truncate max-w-[100px]">${escapeHtml(p.tipo)}</span>`;
        btn.onclick = () => jumpToPdfPage(p.pagina);
        list.appendChild(btn);
      });
    }

    function updateDossieActivePageHighlight(activePage) {
      currentDossieActivePage = activePage;
      const totalPages = (currentIndex >= 0 && filteredDocs && filteredDocs[currentIndex])
        ? Math.max(1, parseInt(filteredDocs[currentIndex].paginas) || (Array.isArray(filteredDocs[currentIndex].dossie_paginas) ? filteredDocs[currentIndex].dossie_paginas.length : 1))
        : 100;

      for (let p = 1; p <= totalPages; p++) {
        const card = document.getElementById(`dossieCardPage_${p}`);
        const btn = document.getElementById(`dossieBtnPage_${p}`);
        const pill = document.getElementById(`dossiePillPage_${p}`);
        const shortcut = document.getElementById(`dossierShortcutPage_${p}`);

        const isActive = (p === activePage);

        if (card) {
          if (isActive) {
            card.classList.add('ring-2', 'ring-emerald-500', 'border-emerald-500', 'bg-slate-800/90');
            card.classList.remove('border-slate-800');
          } else {
            card.classList.remove('ring-2', 'ring-emerald-500', 'border-emerald-500', 'bg-slate-800/90');
            card.classList.add('border-slate-800');
          }
        }

        if (btn) {
          if (isActive) {
            btn.className = 'w-full py-1.5 px-2 bg-emerald-600 text-white font-semibold rounded text-[10px] shadow transition flex items-center justify-center gap-1.5';
            btn.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-200 text-[10px]"></i> <span>Exibindo no Leitor</span>';
          } else {
            btn.className = 'w-full py-1.5 px-2 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-emerald-300 rounded text-[10px] font-medium transition flex items-center justify-center gap-1.5';
            btn.innerHTML = '<i class="fa-solid fa-eye text-slate-400 text-[9px]"></i> <span>Exibir no Leitor</span>';
          }
        }

        if (pill) {
          if (isActive) {
            pill.className = 'px-2 py-0.5 rounded bg-emerald-600 text-white font-semibold border border-emerald-500 text-[10px] flex items-center gap-1 transition shadow-sm';
          } else {
            pill.className = 'px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-cyan-300 border border-slate-700/80 text-[10px] flex items-center gap-1 transition';
          }
        }

        if (shortcut) {
          if (isActive) {
            shortcut.className = 'px-1.5 py-0.5 rounded bg-emerald-600 text-white font-semibold border border-emerald-500 text-[10px] flex items-center gap-1 transition-colors shadow-sm';
          } else {
            shortcut.className = 'px-1.5 py-0.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/70 text-[10px] flex items-center gap-1 transition-colors';
          }
        }
      }
    }

    function jumpToPdfPage(pageNum) {
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      if (isImageDoc(doc)) {
        showToast('Documento em formato de imagem (página única).', 'info');
        return;
      }
      const p = parseInt(pageNum) || 1;
      currentDossieActivePage = p;

      const pdfFrame = document.getElementById('pdfFrame');
      const pdfEmpty = document.getElementById('pdfEmptyState');
      const pdfLoading = document.getElementById('pdfLoadingState');
      const imgViewer = document.getElementById('imageViewerContainer');
      const imgControls = document.getElementById('imageControls');

      if (pdfEmpty) pdfEmpty.classList.add('hidden');
      if (imgViewer) imgViewer.classList.add('hidden');
      if (imgControls) {
        imgControls.classList.add('hidden');
        imgControls.classList.remove('flex');
      }

      if (pdfFrame) {
        pdfFrame.classList.remove('hidden');

        if (pdfLoading) {
          pdfLoading.classList.remove('hidden');
          pdfLoading.style.opacity = '1';
          setTimeout(() => {
            if (pdfLoading) {
              pdfLoading.style.opacity = '0';
              setTimeout(() => {
                if (pdfLoading) pdfLoading.classList.add('hidden');
              }, 150);
            }
          }, 350);
        }

        const ts = Date.now();
        // A chave com query string (?p=N&_t=TS) força o Chromium a reconhecer a navegação
        // e passar o fragmento #page=N para o visualizador de PDF interno
        pdfFrame.src = `/api/pdf/${doc.md5}?p=${p}&_t=${ts}#page=${p}&toolbar=1&navpanes=0`;

        updateDossieActivePageHighlight(p);

        const dossie = Array.isArray(doc.dossie_paginas) ? doc.dossie_paginas : [];
        const pageItem = dossie.find(item => item.pagina === p);
        const pType = pageItem ? pageItem.tipo : `Página ${p}`;

        showToast(`Exibindo página ${p} (${pType}) no Leitor`, 'info');
      }
    }

    function setPrimaryTag(tipo) {
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      doc.tipo_documento = tipo;

      // Atualiza domínio correspondente
      const tLower = tipo.toLowerCase();
      let newDom = 'academico';
      if (tLower.includes('crv') || tLower.includes('crlv') || tLower.includes('atpv') || tLower.includes('veicular') || tLower.includes('veiculo') || tLower.includes('vistoria') || tLower.includes('remocao') || tLower.includes('arrematacao')) {
        newDom = 'veicular';
      } else if (tLower.includes('pix') || tLower.includes('pagamento') || tLower.includes('recibo') || tLower.includes('boleto') || tLower.includes('extrato') || tLower.includes('cheque') || tLower.includes('talao') || tLower.includes('promissória') || tLower.includes('promissoria') || tLower.includes('imposto de renda') || tLower.includes('irpf') || tLower.includes('informe')) {
        newDom = 'financeiro';
      } else if (tLower.includes('rg') || tLower.includes('cnh') || tLower.includes('cpf') || tLower.includes('certidão') || tLower.includes('certidao') || tLower.includes('passaporte') || tLower.includes('eleitor')) {
        newDom = 'identificacao';
      } else if (tLower.includes('contrato') || tLower.includes('procuração') || tLower.includes('procuracao') || tLower.includes('posse')) {
        newDom = 'juridico';
      }
      doc.dominio = newDom;

      const selectDom = document.getElementById('select_dominio');
      if (selectDom) selectDom.value = newDom;
      onDominioChange();

      const selectTipo = document.getElementById('select_tipo_documento');
      if (selectTipo) {
        let exists = false;
        for (let i = 0; i < selectTipo.options.length; i++) {
          if (selectTipo.options[i].value === tipo) { exists = true; break; }
        }
        if (!exists) {
          const opt = document.createElement('option');
          opt.value = tipo;
          opt.innerText = tipo;
          selectTipo.appendChild(opt);
        }
        selectTipo.value = tipo;
      }

      renderMultiTags(doc);
      markDirty();
      saveCurrentDoc();
      showToast(`Documento principal definido como: ${tipo}`, 'success');
    }

    function recalculateDocDomains(doc) {
      if (!doc) return [];
      const doms = new Set();
      if (doc.dominio) doms.add(doc.dominio);
      const allTipos = Array.isArray(doc.todos_tipos) ? doc.todos_tipos : [];
      allTipos.forEach(t => {
        const tLower = safeString(t).toLowerCase();
        if (tLower.includes('crv') || tLower.includes('crlv') || tLower.includes('atpv') || tLower.includes('veicular') || tLower.includes('veiculo') || tLower.includes('vistoria') || tLower.includes('detran') || tLower.includes('senatran') || tLower.includes('denatran') || tLower.includes('remocao') || tLower.includes('remoção') || tLower.includes('arrematacao') || tLower.includes('arrematação')) {
          doms.add('veicular');
        } else if (tLower.includes('pix') || tLower.includes('pagamento') || tLower.includes('recibo') || tLower.includes('boleto') || tLower.includes('extrato') || tLower.includes('nota fiscal') || tLower.includes('cheque') || tLower.includes('talao') || tLower.includes('promissória') || tLower.includes('promissoria') || tLower.includes('imposto de renda') || tLower.includes('irpf') || tLower.includes('informe')) {
          doms.add('financeiro');
        } else if (tLower.includes('rg') || tLower.includes('cnh') || tLower.includes('cpf') || tLower.includes('certid') || tLower.includes('passaporte') || tLower.includes('eleitor')) {
          doms.add('identificacao');
        } else if (tLower.includes('procur') || tLower.includes('contrato') || tLower.includes('posse')) {
          doms.add('juridico');
        } else if (tLower.includes('cnpj') || tLower.includes('cadastral') || tLower.includes('trabalho') || tLower.includes('ctps') || tLower.includes('lattes') || tLower.includes('curriculo') || tLower.includes('registro profissional')) {
          doms.add('profissional');
        } else if (tLower.includes('diploma') || tLower.includes('certificado') || tLower.includes('histórico') || tLower.includes('declar') || tLower.includes('ementa')) {
          doms.add('academico');
        }
      });
      if (doms.size === 0) doms.add(doc.dominio || 'academico');
      doc.todos_dominios = Array.from(doms);
      return doc.todos_dominios;
    }

    function removeTag(tipo) {
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      const tipoLower = safeString(tipo).toLowerCase().trim();
      let tipos = Array.isArray(doc.todos_tipos) ? [...doc.todos_tipos] : [];
      tipos = tipos.filter(t => t.toLowerCase().trim() !== tipoLower);
      doc.todos_tipos = tipos;

      // Se removeu o tipo principal, define o próximo como principal
      if (doc.tipo_documento && doc.tipo_documento.toLowerCase().trim() === tipoLower) {
        if (tipos.length > 0) {
          doc.tipo_documento = tipos[0];
          const selectTipo = document.getElementById('select_tipo_documento');
          if (selectTipo) selectTipo.value = tipos[0];
        } else {
          doc.tipo_documento = 'Outro';
          const selectTipo = document.getElementById('select_tipo_documento');
          if (selectTipo) selectTipo.value = 'Outro';
        }
      }

      // Sanitiza páginas do dossiê para não ressuscitar a tag excluída
      if (Array.isArray(doc.dossie_paginas)) {
        const replacementTipo = doc.tipo_documento || (tipos.length > 0 ? tipos[0] : 'Outro');
        doc.dossie_paginas.forEach(p => {
          if (p.tipo && p.tipo.toLowerCase().trim() === tipoLower) {
            p.tipo = replacementTipo;
          }
        });
      }

      // Se removeu tag de PIX, limpa dados PIX se não houver mais tags financeiras
      if (tipoLower.includes('pix')) {
        const hasOtherPix = tipos.some(t => t.toLowerCase().includes('pix'));
        if (!hasOtherPix) {
          doc.valor_monetario = null;
          delete doc.pix_pagador_nome;
          delete doc.pix_pagador_cpf_cnpj;
          delete doc.pix_pagador_banco;
          delete doc.pix_recebedor_nome;
          delete doc.pix_recebedor_cpf_cnpj;
          delete doc.pix_recebedor_banco;
          delete doc.pix_chave;
          delete doc.pix_e2e_id;
          delete doc.pix_autenticacao;
          if (doc.dados_extras && typeof doc.dados_extras === 'object') {
            delete doc.dados_extras.pix_pagador_nome;
            delete doc.dados_extras.pix_pagador_cpf_cnpj;
            delete doc.dados_extras.pix_pagador_banco;
            delete doc.dados_extras.pix_recebedor_nome;
            delete doc.dados_extras.pix_recebedor_cpf_cnpj;
            delete doc.dados_extras.pix_recebedor_banco;
            delete doc.dados_extras.pix_chave;
            delete doc.dados_extras.pix_e2e_id;
            delete doc.dados_extras.pix_autenticacao;
          }
          const pixCard = document.getElementById('pixReceiptCard');
          if (pixCard) pixCard.classList.add('hidden');
        }
      }

      // Se o domínio atual era financeiro mas não há mais tags financeiras, reajusta domínio
      const hasFinancialTag = tipos.some(t => {
        const tl = t.toLowerCase();
        return tl.includes('pix') || tl.includes('pagamento') || tl.includes('recibo') || tl.includes('boleto') || tl.includes('extrato') || tl.includes('nota fiscal');
      });
      if (doc.dominio === 'financeiro' && !hasFinancialTag) {
        const curTipoLower = (doc.tipo_documento || '').toLowerCase();
        if (curTipoLower.includes('cnpj') || curTipoLower.includes('cadastral') || curTipoLower.includes('trabalho') || curTipoLower.includes('curriculo')) {
          doc.dominio = 'profissional';
        } else if (curTipoLower.includes('rg') || curTipoLower.includes('cnh') || curTipoLower.includes('cpf')) {
          doc.dominio = 'identificacao';
        } else {
          doc.dominio = 'academico';
        }
        const selectDom = document.getElementById('select_dominio');
        if (selectDom) selectDom.value = doc.dominio;
        onDominioChange();
      }

      recalculateDocDomains(doc);
      renderMultiTags(doc);
      renderDynamicInspector(doc);
      markDirty();
      saveCurrentDoc();
      showToast(`Classificação "${tipo}" removida.`, 'info');
    }

    function removePixFromCurrentDoc() {
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      
      // 1. Limpa campos visuais do formulário
      const clearVal = (id) => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      };
      clearVal('input_pix_pagador_nome');
      clearVal('input_pix_pagador_cpf_cnpj');
      clearVal('input_pix_pagador_banco');
      clearVal('input_pix_recebedor_nome_preview');
      clearVal('input_pix_recebedor_cpf_preview');
      clearVal('input_pix_recebedor_banco');
      clearVal('input_pix_chave');
      clearVal('input_pix_e2e_id');
      clearVal('input_pix_autenticacao');
      clearVal('input_valor_monetario');

      // 2. Limpa dados de PIX no objeto do documento
      doc.valor_monetario = null;
      delete doc.pix_pagador_nome;
      delete doc.pix_pagador_cpf_cnpj;
      delete doc.pix_pagador_banco;
      delete doc.pix_recebedor_nome;
      delete doc.pix_recebedor_cpf_cnpj;
      delete doc.pix_recebedor_banco;
      delete doc.pix_chave;
      delete doc.pix_e2e_id;
      delete doc.pix_autenticacao;

      if (doc.dados_extras && typeof doc.dados_extras === 'object') {
        delete doc.dados_extras.pix_pagador_nome;
        delete doc.dados_extras.pix_pagador_cpf_cnpj;
        delete doc.dados_extras.pix_pagador_banco;
        delete doc.dados_extras.pix_recebedor_nome;
        delete doc.dados_extras.pix_recebedor_cpf_cnpj;
        delete doc.dados_extras.pix_recebedor_banco;
        delete doc.dados_extras.pix_chave;
        delete doc.dados_extras.pix_e2e_id;
        delete doc.dados_extras.pix_autenticacao;
      }

      // 3. Remove tags com menção a PIX
      let tipos = Array.isArray(doc.todos_tipos) ? [...doc.todos_tipos] : [];
      tipos = tipos.filter(t => !t.toLowerCase().includes('pix'));
      doc.todos_tipos = tipos;

      if (doc.tipo_documento && doc.tipo_documento.toLowerCase().includes('pix')) {
        doc.tipo_documento = tipos.length > 0 ? tipos[0] : 'Outro';
        const selectTipo = document.getElementById('select_tipo_documento');
        if (selectTipo) selectTipo.value = doc.tipo_documento;
      }

      // 4. Limpa dossie_paginas que tinham menção a PIX
      if (Array.isArray(doc.dossie_paginas)) {
        doc.dossie_paginas.forEach(p => {
          if (p.tipo && p.tipo.toLowerCase().includes('pix')) {
            p.tipo = doc.tipo_documento || 'Outro';
          }
          if (p.dominio === 'financeiro') {
            p.dominio = 'profissional';
          }
        });
      }

      // 5. Se o domínio era financeiro, muda para profissional ou correspondente
      if (doc.dominio === 'financeiro') {
        const curTipoLower = (doc.tipo_documento || '').toLowerCase();
        if (curTipoLower.includes('cnpj') || curTipoLower.includes('cadastral') || curTipoLower.includes('trabalho') || curTipoLower.includes('curriculo')) {
          doc.dominio = 'profissional';
        } else if (curTipoLower.includes('rg') || curTipoLower.includes('cnh') || curTipoLower.includes('cpf')) {
          doc.dominio = 'identificacao';
        } else {
          doc.dominio = 'profissional';
        }
        const selectDom = document.getElementById('select_dominio');
        if (selectDom) selectDom.value = doc.dominio;
      }

      // 6. Recalcula todos_dominios
      recalculateDocDomains(doc);

      // 7. Esconde o card PIX e atualiza a interface
      const pixCard = document.getElementById('pixReceiptCard');
      if (pixCard) pixCard.classList.add('hidden');

      onDominioChange();
      renderDynamicInspector(doc);
      renderMultiTags(doc);
      markDirty();
      saveCurrentDoc();
      showToast('PIX desvinculado deste documento com sucesso!', 'success');
    }

    function openAddTagModal() {
      const modal = document.getElementById('modalAddTag');
      if (modal) {
        document.getElementById('quickSelectTag').value = '';
        document.getElementById('customTagNameInput').value = '';
        modal.classList.remove('hidden');
        document.getElementById('customTagNameInput').focus();
      }
    }

    function closeAddTagModal() {
      const modal = document.getElementById('modalAddTag');
      if (modal) modal.classList.add('hidden');
    }

    function onQuickSelectTagChange() {
      const val = document.getElementById('quickSelectTag').value;
      if (val) {
        document.getElementById('customTagNameInput').value = val;
      }
    }

    function confirmAddTag() {
      const customVal = (document.getElementById('customTagNameInput').value || '').trim();
      const selectVal = document.getElementById('quickSelectTag').value;
      const finalTag = customVal || selectVal;
      if (!finalTag) {
        showToast('Selecione ou digite o nome do documento.', 'info');
        return;
      }

      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      let tipos = Array.isArray(doc.todos_tipos) ? [...doc.todos_tipos] : [];

      if (tipos.some(t => t.toLowerCase().trim() === finalTag.toLowerCase().trim())) {
        showToast(`O documento "${finalTag}" já está listado neste arquivo.`, 'info');
        closeAddTagModal();
        return;
      }

      tipos.push(finalTag);
      doc.todos_tipos = tipos;

      recalculateDocDomains(doc);
      renderMultiTags(doc);
      closeAddTagModal();
      markDirty();
      saveCurrentDoc();
      showToast(`Documento "${finalTag}" adicionado com sucesso!`, 'success');
    }

