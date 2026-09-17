    let currentImageScale = 1.0;
    let currentImageRotation = 0;

    function isImageDoc(doc) {
      if (!doc) return false;
      const ext = safeString(doc.extensao || '').toLowerCase();
      if (['.png', '.jpg', '.jpeg', '.webp'].includes(ext)) return true;
      const file = safeString(doc.nome_arquivo || doc.caminho_relativo || '').toLowerCase();
      return file.endsWith('.png') || file.endsWith('.jpg') || file.endsWith('.jpeg') || file.endsWith('.webp');
    }

    function isWordDoc(doc) {
      if (!doc) return false;
      const ext = safeString(doc.extensao || '').toLowerCase();
      if (['.docx', '.doc', '.odt', '.rtf'].includes(ext)) return true;
      const file = safeString(doc.nome_arquivo || doc.caminho_relativo || '').toLowerCase();
      return file.endsWith('.docx') || file.endsWith('.doc') || file.endsWith('.odt') || file.endsWith('.rtf');
    }

    function isTextDoc(doc) {
      if (!doc) return false;
      const ext = safeString(doc.extensao || '').toLowerCase();
      if (ext === '.txt') return true;
      const file = safeString(doc.nome_arquivo || doc.caminho_relativo || '').toLowerCase();
      return file.endsWith('.txt');
    }

    function getDocFormatMeta(doc) {
      if (isWordDoc(doc)) {
        const ext = safeString(doc.extensao || 'DOCX').replace('.', '').toUpperCase();
        return { 
          type: 'word', 
          label: ext, 
          icon: 'fa-solid fa-file-word', 
          color: 'text-sky-400', 
          badgeClass: 'bg-sky-500/15 text-sky-300 border-sky-500/30' 
        };
      }
      if (isImageDoc(doc)) {
        const ext = safeString(doc.extensao || 'IMG').replace('.', '').toUpperCase();
        return { 
          type: 'image', 
          label: ext, 
          icon: 'fa-regular fa-image', 
          color: 'text-emerald-400', 
          badgeClass: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' 
        };
      }
      if (isTextDoc(doc)) {
        return { 
          type: 'text', 
          label: 'TXT', 
          icon: 'fa-regular fa-file-lines', 
          color: 'text-amber-400', 
          badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30' 
        };
      }
      return { 
        type: 'pdf', 
        label: 'PDF', 
        icon: 'fa-regular fa-file-pdf', 
        color: 'text-rose-400', 
        badgeClass: 'bg-rose-500/15 text-rose-300 border-rose-500/30' 
      };
    }

    function applyImageTransform() {
      const imgEl = document.getElementById('docImageEl');
      if (imgEl) {
        imgEl.style.transform = `scale(${currentImageScale}) rotate(${currentImageRotation}deg)`;
      }
    }

    function zoomImage(delta) {
      currentImageScale = Math.max(0.2, Math.min(5.0, currentImageScale + delta));
      applyImageTransform();
    }

    function resetImageZoom() {
      currentImageScale = 1.0;
      applyImageTransform();
    }

    function rotateImage() {
      currentImageRotation = (currentImageRotation + 90) % 360;
      applyImageTransform();
    }

    function resetImageTransform() {
      currentImageScale = 1.0;
      currentImageRotation = 0;
      applyImageTransform();
    }

    function onDominioChange() {
      const selectDom = document.getElementById('select_dominio');
      const dom = selectDom ? selectDom.value : 'academico';
      const badge = document.getElementById('domainBadgePreview');
      const pixCard = document.getElementById('pixReceiptCard');
      const secAcademico = document.getElementById('section_academico');
      const labelBeneficiario = document.getElementById('label_beneficiario');
      const labelFaculdade = document.getElementById('label_faculdade');
      const labelData = document.getElementById('label_data');

      if (badge) {
        badge.innerText = dom;
        if (dom === 'financeiro') {
          badge.className = "text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
        } else if (dom === 'veicular') {
          badge.className = "text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-orange-500/20 text-orange-400 border border-orange-500/30";
        } else if (dom === 'identificacao') {
          badge.className = "text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-cyan-500/20 text-cyan-400 border border-cyan-500/30";
        } else if (dom === 'juridico') {
          badge.className = "text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-amber-500/20 text-amber-400 border border-amber-500/30";
        } else if (dom === 'profissional') {
          badge.className = "text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-sky-500/20 text-sky-400 border border-sky-500/30";
        } else if (dom === 'outro') {
          badge.className = "text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-purple-500/20 text-purple-400 border border-purple-500/30";
        } else {
          badge.className = "text-[10px] px-2 py-0.5 rounded font-mono font-medium bg-indigo-500/20 text-indigo-300 border border-indigo-500/30";
        }
      }

      // Visibilidade da seção acadêmica
      if (secAcademico) {
        if (dom === 'academico') {
          secAcademico.classList.remove('hidden');
        } else {
          secAcademico.classList.add('hidden');
        }
      }

      // Visibilidade do card Cadastral da Receita Federal e adaptação contextual de rótulos
      const cnpjCard = document.getElementById('cartaoCnpjCard');
      const tipoVal = (document.getElementById('select_tipo_documento')?.value || '').toLowerCase();
      const isActualCadastralDoc = (
        tipoVal.includes('situação cadastral') ||
        tipoVal.includes('situacao cadastral') ||
        tipoVal.includes('cartão cnpj') ||
        tipoVal.includes('cartao cnpj') ||
        tipoVal.includes('cartão do cnpj') ||
        tipoVal.includes('cartao do cnpj') ||
        tipoVal.includes('cadastro nacional da pessoa') ||
        (dom === 'profissional' && (tipoVal.includes('cnpj') || tipoVal.includes('cadastral')))
      );

      if (cnpjCard) {
        if (isActualCadastralDoc) {
          cnpjCard.classList.remove('hidden');
        } else {
          cnpjCard.classList.add('hidden');
        }
      }

      const isIrpf = tipoVal.includes('imposto de renda') || tipoVal.includes('ajuste anual');
      const isInforme = tipoVal.includes('informe');
      const isCheque = tipoVal.includes('cheque') || tipoVal.includes('talao') || tipoVal.includes('talão');
      const isBoleto = tipoVal.includes('boleto');
      const isPromissoria = tipoVal.includes('promissoria') || tipoVal.includes('promissória');
      const isPix = tipoVal.includes('pix');

      if (dom === 'financeiro') {
        if (pixCard) {
          if (isPix) {
            pixCard.classList.remove('hidden');
          } else {
            pixCard.classList.add('hidden');
          }
        }
        if (isIrpf) {
          if (labelBeneficiario) labelBeneficiario.innerText = "Contribuinte / Declarante";
          if (labelFaculdade) labelFaculdade.innerText = "Órgão Emissor / Secretaria da Receita Federal (RFB)";
          if (labelData) labelData.innerText = "Data de Transmissão / Entrega";
        } else if (isInforme) {
          if (labelBeneficiario) labelBeneficiario.innerText = "Titular / Beneficiário dos Rendimentos";
          if (labelFaculdade) labelFaculdade.innerText = "Fonte Pagadora / Instituição Financeira";
          if (labelData) labelData.innerText = "Ano-Calendário / Data de Emissão";
        } else if (isCheque) {
          if (labelBeneficiario) labelBeneficiario.innerText = "Nominal a / Favorecido";
          if (labelFaculdade) labelFaculdade.innerText = "Instituição Bancária do Cheque";
          if (labelData) labelData.innerText = "Data de Emissão do Cheque";
        } else if (isBoleto) {
          if (labelBeneficiario) labelBeneficiario.innerText = "Pagador / Sacado / Beneficiário";
          if (labelFaculdade) labelFaculdade.innerText = "Instituição Bancária Emissora";
          if (labelData) labelData.innerText = "Data de Vencimento / Pagamento";
        } else if (isPromissoria) {
          if (labelBeneficiario) labelBeneficiario.innerText = "Emitente / Devedor";
          if (labelFaculdade) labelFaculdade.innerText = "Credor / Beneficiário";
          if (labelData) labelData.innerText = "Data de Vencimento / Emissão";
        } else {
          if (labelBeneficiario) labelBeneficiario.innerText = "Nome do Favorecido / Recebedor";
          if (labelFaculdade) labelFaculdade.innerText = "Instituição Financeira / Banco";
          if (labelData) labelData.innerText = "Data e Hora da Operação";
        }
      } else if (dom === 'veicular') {
        if (pixCard) pixCard.classList.add('hidden');
        if (labelBeneficiario) labelBeneficiario.innerText = "Proprietário / Comprador / Titular";
        if (labelFaculdade) labelFaculdade.innerText = "Órgão de Trânsito (DETRAN / SENATRAN)";
        if (labelData) labelData.innerText = "Data do Documento / Venda / Emissão";
      } else if (dom === 'identificacao') {
        if (pixCard) pixCard.classList.add('hidden');
        if (labelBeneficiario) labelBeneficiario.innerText = "Nome Completo do Titular";
        if (labelFaculdade) labelFaculdade.innerText = "Órgão Emissor / Expedidor (SSP, Detran, PF)";
        if (labelData) labelData.innerText = "Data de Emissão / Expedição";
      } else if (dom === 'juridico') {
        if (pixCard) pixCard.classList.add('hidden');
        if (labelBeneficiario) labelBeneficiario.innerText = "Parte Principal / Titular / Outorgante";
        if (labelFaculdade) labelFaculdade.innerText = "Órgão / Cartório / Empresa / Vara";
        if (labelData) labelData.innerText = "Data do Documento / Assinatura";
      } else if (dom === 'profissional') {
        if (pixCard) pixCard.classList.add('hidden');
        if (labelBeneficiario) labelBeneficiario.innerText = isActualCadastralDoc ? "Nome Empresarial (Razão Social)" : "Razão Social / Nome da Pessoa / Titular";
        if (labelFaculdade) labelFaculdade.innerText = isActualCadastralDoc ? "Receita Federal do Brasil (RFB)" : "Órgão Emissor / Entidade";
        if (labelData) labelData.innerText = isActualCadastralDoc ? "Data da Situação Cadastral / Abertura" : "Data de Emissão / Expedição";
      } else if (dom === 'outro') {
        if (pixCard) pixCard.classList.add('hidden');
        if (labelBeneficiario) labelBeneficiario.innerText = "Nome do Titular / Beneficiário";
        if (labelFaculdade) labelFaculdade.innerText = "Entidade / Instituição Emissora";
        if (labelData) labelData.innerText = "Data do Documento";
      } else {
        // Acadêmico
        if (pixCard) pixCard.classList.add('hidden');
        if (labelBeneficiario) labelBeneficiario.innerText = "Nome do Aluno / Diplomado";
        if (labelFaculdade) labelFaculdade.innerText = "Faculdade / Instituição Emissora";
        if (labelData) labelData.innerText = "Data de Conclusão / Emissão";
      }

      // Adaptação contextual do campo de CPF/CNPJ e RG/Registro
      const labelCpf = document.getElementById('label_cpf');
      const badgeCpf = document.getElementById('badge_cpf');
      const inputCpf = document.getElementById('input_cpf');
      const labelRg = document.getElementById('label_rg');
      const inputRg = document.getElementById('input_rg');
      const labelDocCnpj = document.getElementById('label_doc_cnpj');
      const labelDocEnd = document.getElementById('label_doc_endereco');

      if (isActualCadastralDoc) {
        if (labelCpf) labelCpf.innerText = "CPF do Responsável (se houver)";
        if (badgeCpf) badgeCpf.innerText = "cpf";
        if (inputCpf) inputCpf.placeholder = "000.000.000-00";
        if (labelRg) labelRg.innerText = "Inscrição Estadual / Registro";
        if (inputRg) inputRg.placeholder = "Ex: ISENTO ou Nº de Registro";
      } else {
        if (labelCpf) labelCpf.innerText = dom === 'academico' ? "CPF do Aluno / Titular" : (dom === 'veicular' ? "CPF do Proprietário / Comprador" : (dom === 'identificacao' ? "CPF do Titular" : "CPF"));
        if (badgeCpf) badgeCpf.innerText = "cpf";
        if (inputCpf) inputCpf.placeholder = "000.000.000-00";
        if (labelRg) labelRg.innerText = dom === 'veicular' ? "Placa / Renavam / Chassi" : "RG / Identidade";
        if (inputRg) inputRg.placeholder = dom === 'veicular' ? "Ex: MQB-4382 ou Renavam" : "Ex: 2030359 SSP-ES";
      }

      if (labelDocCnpj) {
        if (dom === 'academico') {
          labelDocCnpj.innerText = "CNPJ da Faculdade / Emissor";
        } else if (isActualCadastralDoc || dom === 'profissional') {
          labelDocCnpj.innerText = "CNPJ da Empresa / Titular";
        } else if (dom === 'financeiro') {
          if (isIrpf) {
            labelDocCnpj.innerText = "CPF do Contribuinte / CNPJ Fonte Pagadora";
          } else if (isInforme) {
            labelDocCnpj.innerText = "CNPJ da Fonte Pagadora";
          } else {
            labelDocCnpj.innerText = "CNPJ do Pagador / Recebedor";
          }
        } else {
          labelDocCnpj.innerText = "CNPJ";
        }
      }

      if (labelDocEnd) {
        if (dom === 'academico') {
          labelDocEnd.innerText = "Cidade / Localidade da Instituição";
        } else if (isActualCadastralDoc || dom === 'profissional') {
          labelDocEnd.innerText = "Endereço Cadastral / Comercial";
        } else if (dom === 'identificacao') {
          labelDocEnd.innerText = "Endereço Residencial / Domiciliar";
        } else if (dom === 'juridico') {
          labelDocEnd.innerText = "Endereço das Partes / Comarca";
        } else {
          labelDocEnd.innerText = "Endereço / Localidade";
        }
      }
    }

    function updateCnpjBadge() {
      const sitEl = document.getElementById('input_cnpj_situacao');
      const badge = document.getElementById('cnpjSituacaoBadge');
      if (!badge || !sitEl) return;
      const sit = (sitEl.value || '').trim().toUpperCase();
      badge.innerText = sit || 'ATIVA';
      if (sit.includes('ATIVA')) {
        badge.className = "bg-emerald-500/20 text-emerald-300 text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold border border-emerald-500/30";
      } else if (sit.includes('BAIXADA') || sit.includes('INAPTA') || sit.includes('NULA')) {
        badge.className = "bg-rose-500/20 text-rose-300 text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold border border-rose-500/30";
      } else if (sit.includes('SUSPENSA')) {
        badge.className = "bg-amber-500/20 text-amber-300 text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold border border-amber-500/30";
      } else {
        badge.className = "bg-sky-500/20 text-sky-300 text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold border border-sky-500/30";
      }
    }

    function syncCnpjToGeneral(val) {
      const gEl = document.getElementById('input_doc_cnpj');
      if (gEl) gEl.value = val;
      const cpfEl = document.getElementById('input_cpf');
      const selectDom = document.getElementById('select_dominio');
      if (cpfEl && selectDom && selectDom.value === 'profissional') {
        cpfEl.value = val;
      }
    }

    function syncGeneralCnpjToCard(val) {
      const cEl = document.getElementById('input_cnpj');
      if (cEl) cEl.value = val;
      const cpfEl = document.getElementById('input_cpf');
      const selectDom = document.getElementById('select_dominio');
      if (cpfEl && selectDom && selectDom.value === 'profissional') {
        cpfEl.value = val;
      }
    }

    function syncGeneralEndereco(val) {
      const cEnd = document.getElementById('input_cnpj_endereco');
      if (cEnd) cEnd.value = val;
    }

    function syncCardEnderecoToGeneral(val) {
      const gEnd = document.getElementById('input_doc_endereco');
      if (gEnd) gEnd.value = val;
    }

    function onCpfInput(val) {
      markDirty();
      const selectDom = document.getElementById('select_dominio');
      if ((selectDom && selectDom.value === 'profissional') || (val && val.includes('/'))) {
        const cEl = document.getElementById('input_cnpj');
        if (cEl) cEl.value = val;
        const gEl = document.getElementById('input_doc_cnpj');
        if (gEl) gEl.value = val;
      }
    }

    function syncRazaoSocialFromCnpjCard(val) {
      const selectDom = document.getElementById('select_dominio');
      if (selectDom && selectDom.value === 'profissional') {
        const benEl = document.getElementById('input_beneficiario');
        if (benEl && (!benEl.value || benEl.value.trim() === '')) {
          benEl.value = val;
        }
      }
    }

    function onTipoDocumentoChange() {
      const selectTipo = document.getElementById('select_tipo_documento');
      const tipo = selectTipo ? selectTipo.value : '';
      const selectDom = document.getElementById('select_dominio');
      
      const mapTipoDom = {
        'Diploma': 'academico',
        'Certificado': 'academico',
        'Histórico Escolar': 'academico',
        'Declaração': 'academico',
        'Currículo': 'profissional',
        'Comprovante PIX': 'financeiro',
        'Talão de Cheques': 'financeiro',
        'Folha de Cheque': 'financeiro',
        'Nota Promissória': 'financeiro',
        'Recibo': 'financeiro',
        'Recibo de Pagamento': 'financeiro',
        'Boleto Bancário': 'financeiro',
        'Extrato Bancário': 'financeiro',
        'Nota Fiscal': 'financeiro',
        'Declaração de Imposto de Renda': 'financeiro',
        'Recibo de Entrega da Declaração de Ajuste Anual': 'financeiro',
        'Informe de Rendimentos Financeiros': 'financeiro',
        'Cartão CNPJ / Situação Cadastral': 'profissional',
        'Comprovante de Inscrição e de Situação Cadastral': 'profissional',
        'Cartão CNPJ': 'profissional',
        'Carteira de Trabalho': 'profissional',
        'Registro Profissional': 'profissional',
        'RG / Identidade': 'identificacao',
        'CNH': 'identificacao',
        'CPF': 'identificacao',
        'Certidão de Nascimento': 'identificacao',
        'Certidão de Casamento': 'identificacao',
        'Contrato de Compra e Venda': 'juridico',
        'Contrato Particular de Compra e Venda de Imóvel': 'juridico',
        'Contrato': 'juridico',
        'Procuração': 'juridico',
        'Termo de Posse': 'juridico',
        'Citação de Mandado de Busca e Apreensão': 'juridico',
        'Procuração / Substabelecimento Veicular': 'juridico',
        'Dossiê Veicular': 'veicular',
        'Certificado de Registro de Veículo (CRV)': 'veicular',
        'Certificado de Registro e Licenciamento de Veículo (CRLV)': 'veicular',
        'Autorização para Transferência de Propriedade de Veículo (ATPV)': 'veicular',
        'Comunicação de Venda ao DETRAN': 'veicular',
        'Laudo de Vistoria Veicular': 'veicular',
        'Guia de Remoção de Veículo': 'veicular',
        'Nota de Arrematação (Leilão)': 'veicular',
        'Comprovante de Agendamento DETRAN': 'veicular'
      };

      if (selectDom && mapTipoDom[tipo] && selectDom.value !== mapTipoDom[tipo]) {
        selectDom.value = mapTipoDom[tipo];
        onDominioChange();
      }

      if (currentIndex >= 0 && filteredDocs && filteredDocs[currentIndex]) {
        const doc = filteredDocs[currentIndex];
        doc.tipo_documento = tipo;
        let tipos = Array.isArray(doc.todos_tipos) ? [...doc.todos_tipos] : [];
        if (tipo && !tipos.some(t => t.toLowerCase() === tipo.toLowerCase())) {
          tipos.unshift(tipo);
        }
        doc.todos_tipos = tipos;
        renderMultiTags(doc);
      }

      onDominioChange();
      markDirty();
    }

    function syncRecebedorFromPixCard(val) {
      const benEl = document.getElementById('input_beneficiario');
      if (benEl) benEl.value = val;
    }

    function syncCpfFromPixCard(val) {
      const cpfEl = document.getElementById('input_cpf');
      if (cpfEl) cpfEl.value = val;
    }

    // Filtro de Domínio do Documento (Hierarquia 1 - Multi-seleção por Tags)
    function updateDominioFilterOptions() {
      const rawSearch = (document.getElementById('searchInput').value || '').trim();

      const baseDocs = documents.filter(doc => {
        if (activeQuickView === 'dossies') {
          const pgs = Array.isArray(doc.dossie_paginas) ? doc.dossie_paginas.length : 0;
          const tipos = Array.isArray(doc.todos_tipos) ? doc.todos_tipos.length : 0;
          if (pgs < 2 && tipos < 2) return false;
        }

        // Status filter
        if (selectedStatus.size > 0) {
          const isUnproc = isDocumentUnprocessed(doc);
          const isAppr = !isUnproc && safeString(doc.status_conferencia || 'pendente').toLowerCase() === 'aprovado';
          const isPend = !isUnproc && !isAppr;
          let match = false;
          if (selectedStatus.has('nao_processado') && isUnproc) match = true;
          if (selectedStatus.has('pendente') && isPend) match = true;
          if (selectedStatus.has('aprovado') && isAppr) match = true;
          if (!match) return false;
        }

        // Instituição filter
        if (selectedInstituicoes.size > 0) {
          const fac = safeString(doc.faculdade).trim().toLowerCase();
          if (!Array.from(selectedInstituicoes).some(s => s.toLowerCase() === fac)) return false;
        }

        // Tipo filter
        if (selectedTipos.size > 0) {
          const docTipo = safeString(doc.tipo_documento).trim().toLowerCase();
          const tipos = Array.isArray(doc.todos_tipos) && doc.todos_tipos.length > 0
            ? doc.todos_tipos.map(t => safeString(t).trim().toLowerCase())
            : [docTipo || 'não identificado'];
          if (!Array.from(selectedTipos).some(st => tipos.includes(st.toLowerCase()))) return false;
        }

        // Natureza filter
        if (selectedNaturezas.size > 0) {
          const docNat = safeString(doc.natureza_curso).trim();
          if (!Array.from(selectedNaturezas).some(sn => docNat === sn || classifyNatureza(docNat) === sn)) return false;
        }

        return matchDocumentSearch(doc, rawSearch);
      });

      const counts = { academico: 0, financeiro: 0, identificacao: 0, outros: 0 };
      baseDocs.forEach(d => {
        const dom = safeString(d.dominio || 'academico').toLowerCase();
        const doms = Array.isArray(d.todos_dominios) && d.todos_dominios.length > 0
          ? d.todos_dominios.map(x => safeString(x).toLowerCase())
          : [dom];

        if (doms.includes('academico') || dom === 'academico') counts.academico++;
        if (doms.includes('financeiro') || dom === 'financeiro') counts.financeiro++;
        if (doms.includes('identificacao') || dom === 'identificacao') counts.identificacao++;
        const hasOutros = doms.some(x => x !== 'academico' && x !== 'financeiro' && x !== 'identificacao');
        if (hasOutros || (dom !== 'academico' && dom !== 'financeiro' && dom !== 'identificacao')) counts.outros++;
      });

      ['dominioChips', 'g-dominioChips'].forEach(cid => {
        const chipsContainer = document.getElementById(cid);
        if (chipsContainer) {
          chipsContainer.innerHTML = '';
          const domainItems = [
            { key: 'academico', label: 'Acadêmico', icon: 'fa-solid fa-graduation-cap' },
            { key: 'financeiro', label: 'PIX / Financeiro', icon: 'fa-solid fa-money-bill-wave' },
            { key: 'identificacao', label: 'Identificação', icon: 'fa-regular fa-id-card' },
            { key: 'outros', label: 'Outros', icon: 'fa-solid fa-box-archive' }
          ];

          domainItems.forEach(item => {
            const isSelected = selectedDominios.has(item.key);
            const count = counts[item.key] || 0;
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = `px-2.5 py-1 rounded-lg text-xs font-medium border transition flex items-center gap-1.5 ${
              isSelected
                ? 'bg-cyan-600 text-white border-cyan-500 shadow-sm font-semibold ring-1 ring-cyan-400/50'
                : (count === 0 
                    ? 'bg-slate-950/40 text-slate-500 border-slate-900/60 opacity-60 hover:opacity-90 hover:text-slate-300' 
                    : 'bg-slate-950/70 text-slate-300 border-slate-800 hover:bg-slate-800/80 hover:text-cyan-300')
            }`;
            btn.innerHTML = `
              <i class="${item.icon} text-[10px] ${isSelected ? 'text-white' : 'text-cyan-400'}"></i>
              <span>${item.label}</span>
              <span class="text-[10px] px-1.5 py-0.2 rounded-full font-mono ml-0.5 ${isSelected ? 'bg-cyan-950/70 text-cyan-200' : 'bg-slate-800 text-slate-400'}">${count}</span>
            `;
            btn.onclick = () => {
              toggleDomainFilter(item.key);
            };
            chipsContainer.appendChild(btn);
          });
        }
      });

      ['btnClearDomain', 'g-btnClearDomain'].forEach(bid => {
        const btnClearDom = document.getElementById(bid);
        if (btnClearDom) {
          if (selectedDominios.size > 0) btnClearDom.classList.remove('hidden');
          else btnClearDom.classList.add('hidden');
        }
      });
    }

    function toggleDomainFilter(domKey) {
      if (selectedDominios.has(domKey)) {
        selectedDominios.delete(domKey);
      } else {
        selectedDominios.add(domKey);
      }
      syncActiveFilterVars();
      ['containerFilterNatureza', 'g-containerFilterNatureza'].forEach(id => {
        const contNat = document.getElementById(id);
        if (contNat) {
          if (selectedDominios.size > 0 && !selectedDominios.has('academico')) {
            contNat.classList.add('hidden');
            selectedNaturezas.clear();
            activeNaturezaFilter = '';
          } else {
            contNat.classList.remove('hidden');
          }
        }
      });
      applyFilter(false);
    }

    function setDomainFilter(dom) {
      selectedDominios.clear();
      if (dom && dom !== 'todos') {
        selectedDominios.add(dom);
      }
      syncActiveFilterVars();
      ['containerFilterNatureza', 'g-containerFilterNatureza'].forEach(id => {
        const contNat = document.getElementById(id);
        if (contNat) {
          if (selectedDominios.size > 0 && !selectedDominios.has('academico')) {
            contNat.classList.add('hidden');
            selectedNaturezas.clear();
            activeNaturezaFilter = '';
          } else {
            contNat.classList.remove('hidden');
          }
        }
      });
      applyFilter(false);
    }

    function resetDomainFilter() {
      selectedDominios.clear();
      syncActiveFilterVars();
      ['containerFilterNatureza', 'g-containerFilterNatureza'].forEach(id => {
        const contNat = document.getElementById(id);
        if (contNat) contNat.classList.remove('hidden');
      });
      applyFilter(false);
    }

    function updateDomainButtonsUI() {}

    // --- Funções Utilitárias de Sanitização e Normalização ---
    function safeString(val) {
      if (val === null || val === undefined) return '';
      if (Array.isArray(val)) return val.map(safeString).filter(Boolean).join(', ');
      if (typeof val === 'object') return JSON.stringify(val);
      return String(val);
    }

    function normalizeText(val) {
      const str = safeString(val);
      if (!str) return '';
      return str
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .trim();
    }

    function extractDigits(val) {
      const str = safeString(val);
      if (!str) return '';
      return str.replace(/\D/g, '');
    }

    function formatTitlePt(str) {
      if (!str) return '';
      const connectives = new Set(['de', 'da', 'do', 'das', 'dos', 'e', 'em', 'para', 'com', 'no', 'na', 'nos', 'nas', 'a', 'o', 'as', 'os']);
      const knownAcronyms = new Set(['FIVAR', 'FAB', 'CETEC', 'CTEC', 'CEITEC', 'CEIC', 'CEIT', 'CEEC', 'FACI', 'FAD', 'FAP', 'UESC', 'IASES', 'UGF', 'SENAC', 'UNIFTB', 'UNIFENAS', 'UNIFIL', 'FABRANI', 'FABAVI', 'NEJA', 'DETRAN', 'CEUFTB', 'UNIP', 'USP', 'UFRJ', 'UFBA', 'UFMG', 'UNIFESP', 'PUC']);
      
      const mPar = str.match(/\s*\(([A-Za-z0-9\s\-]+)\)$/);
      let parenSigla = '';
      let body = str;
      if (mPar) {
        parenSigla = ` (${mPar[1].trim().toUpperCase()})`;
        body = str.substring(0, mPar.index).trim();
      }

      const words = body.split(/\s+/);
      const res = words.map((w, idx) => {
        const wl = w.toLowerCase();
        const wu = w.toUpperCase();
        if (knownAcronyms.has(wu)) return wu;
        if (idx > 0 && connectives.has(wl)) return wl;
        if (wl.startsWith('(') && wl.endsWith(')')) return w.toUpperCase();
        if (w.length <= 5 && w === wu && /^[A-Z]+$/.test(w) && !connectives.has(wl)) return wu;
        return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
      });
      return res.join(' ') + parenSigla;
    }

    function normalizeInstitution(raw) {
      if (!raw || typeof raw !== 'string') return null;
      let text = raw.trim();
      if (!text) return null;
      const lower = text.toLowerCase();
      if (['null', 'none', 'nao informada', 'nao informado', 'não informada', 'não informado', 'n/a', 'desconhecida', 'desconhecido', 'sem instituicao', 'universidade', 'faculdade'].includes(lower)) {
        return null;
      }

      text = text.replace(/[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]/g, '-');
      text = text.replace(/[\"\'\`´]/g, '');
      text = text.replace(/\s+/g, ' ').trim();
      text = text.replace(/\b(LTDA|S\/?A|EIRELI|ME|EPP)\b\.?/gi, '').trim();
      text = text.replace(/\s*-\s*$/g, '').trim();

      const semAcento = normalizeText(text);
      const compact = semAcento.replace(/[^a-z0-9]/g, '');

      // 1. Dicionário canônico de alta frequência
      if (semAcento.includes('vale do rio') || semAcento.includes('fivar') || compact.includes('fivar')) {
        if (semAcento.includes('itarare') && !semAcento.includes('vale do rio')) {
          return 'Faculdades Integradas de Itararé';
        }
        return 'Faculdades Integradas Vale do Rio Verde (FIVAR)';
      }

      if (semAcento.includes('uniftb') || semAcento.includes('tobias barreto') || semAcento.includes('ceuftb')) {
        return 'Faculdade UNIFTB';
      }

      if (
        ((semAcento.includes('alfa') || semAcento.includes('alffa') || semAcento.includes('afpa') || semAcento.includes('fauldaffe') || semAcento.includes('fauldae')) &&
         (semAcento.includes('brasil') || semAcento.includes('fab'))) ||
        compact === 'fab' || compact === 'faculdadefab'
      ) {
        return 'Faculdade Alffa do Brasil (FAB)';
      }

      if ((semAcento.includes('cetec') || semAcento.includes('ctec') || semAcento.includes('ceitec') || semAcento.includes('ceic') || semAcento.includes('ceit') || semAcento.includes('ceec')) && semAcento.includes('capacitacao')) {
        return 'Centro Técnico de Capacitação (CETEC)';
      }
      if (semAcento.includes('centro tecnico de capacitacao')) {
        return 'Centro Técnico de Capacitação (CETEC)';
      }

      if (semAcento.includes('impacto') || semAcento.includes('impracto') || (semAcento.includes('faci') && (semAcento.includes('faculdade') || semAcento.includes('faculdades')))) {
        return 'Faculdades Impactos Brasil (FACI)';
      }

      if (semAcento.includes('domini') || semAcento.includes('dominus')) {
        return 'Faculdade Dominius (FAD)';
      }

      if ((semAcento.includes('parana') || semAcento.includes('jarani')) && (semAcento.includes('faculdade') || semAcento.includes('fap'))) {
        return 'Faculdade Paraná (FAP)';
      }

      if (semAcento.includes('itarare') || semAcento.includes('itarae')) {
        return 'Faculdades Integradas de Itararé';
      }

      if (semAcento.includes('famart')) {
        return 'Faculdade Famart';
      }

      if (semAcento.includes('santa cruz') && (semAcento.includes('universidade') || semAcento.includes('uesc'))) {
        return 'Universidade Estadual de Santa Cruz (UESC)';
      }

      if (semAcento.includes('iases') || semAcento.includes('socioeducativo')) {
        return 'Instituto de Atendimento Socioeducativo do Espírito Santo (IASES)';
      }

      if (semAcento.includes('gama filho')) {
        return 'Universidade Gama Filho (UGF)';
      }

      if (semAcento.includes('wenceslau braz')) {
        return 'Faculdade de Ciências de Wenceslau Braz';
      }

      if (semAcento.includes('scardua') || semAcento.includes('scarda')) {
        return 'Scardua Educacional';
      }

      if (semAcento.includes('sao geraldo')) {
        return 'Faculdade São Geraldo (Multivix)';
      }

      if (semAcento.includes('faculdade do v ale') || semAcento.includes('faculdade do vale')) {
        return 'Faculdade do Vale';
      }

      // Regras estruturais genéricas de inversão
      // Caso A: SIGLA - Nome Extenso
      const mSiglaIni = text.match(/^([A-Z0-9]{2,8})\s*[-–—:/|]\s*(.+)$/);
      if (mSiglaIni) {
        const sigla = mSiglaIni[1].trim();
        const resto = mSiglaIni[2].replace(/^[-–—:/|]\s*/, '').trim();
        return `${formatTitlePt(resto)} (${sigla})`;
      }

      // Caso B: Nome Extenso - SIGLA
      const mSiglaFim = text.match(/^(.+?)\s*[-–—:/|]\s*([A-Z0-9]{2,8})$/);
      if (mSiglaFim) {
        const resto = mSiglaFim[1].trim();
        const sigla = mSiglaFim[2].trim();
        return `${formatTitlePt(resto)} (${sigla})`;
      }

      // Caso C: (SIGLA) Nome Extenso
      const mParenIni = text.match(/^\((.+?)\)\s*(.+)$/);
      if (mParenIni) {
        const p1 = mParenIni[1].trim();
        const p2 = mParenIni[2].trim();
        if (p1.length <= 8) return `${formatTitlePt(p2)} (${p1.toUpperCase()})`;
      }

      // Caso D: Nome (SIGLA)
      const mParenFim = text.match(/^(.+?)\s*\(([A-Za-z0-9\s\-]+)\)$/);
      if (mParenFim) {
        const nomeExt = mParenFim[1].trim();
        const sigla = mParenFim[2].trim();
        if (sigla.length <= 8) return `${formatTitlePt(nomeExt)} (${sigla.toUpperCase()})`;
      }

      return formatTitlePt(text);
    }

    function classifyNatureza(val) {
      const raw = normalizeText(safeString(val));
      if (!raw) return 'Não identificada';
      if (raw.includes('stricto') || raw.includes('mestrado') || raw.includes('doutorado')) {
        return 'Pós-Graduação Stricto Sensu (Mestrado/Doutorado)';
      }
      if (raw.includes('lato sensu') || raw.includes('especializacao') || raw.includes('mba') || raw.includes('pos-graduacao') || raw.includes('pos graduacao')) {
        return 'Pós-Graduação Lato Sensu (Especialização/MBA)';
      }
      if (raw.includes('graduacao') || raw.includes('superior') || raw.includes('bacharel') || raw.includes('licenciatura') || raw.includes('tecnologo')) {
        return 'Graduação / Curso Superior';
      }
      if (raw.includes('tecnico') || raw.includes('profissionalizante')) {
        return 'Curso Técnico / Profissionalizante';
      }
      if (raw.includes('extensao') || raw.includes('aperfeicoamento') || raw.includes('capacitacao')) {
        return 'Curso de Extensão / Aperfeiçoamento';
      }
      if (raw.includes('basica') || raw.includes('medio') || raw.includes('fundamental')) {
        return 'Educação Básica';
      }
      return 'Não identificada';
    }

    window.addEventListener('DOMContentLoaded', () => {
      initTheme();
      loadAccordionsState();
      applyAccordionsState();
      updateThumbnailToggleUI();
      const savedTab = localStorage.getItem('joakindex_active_tab') || 'galeria';
      switchMainTab(savedTab);
      loadDocuments();
      setupKeyboardShortcuts();
      checkBatchStatusOnLoad();
      loadSystemConfig();
      loadLearnedRulesCount();
    });

