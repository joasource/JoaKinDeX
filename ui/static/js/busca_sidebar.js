    function matchDocumentSearch(doc, rawQuery) {
      if (!rawQuery) return true;
      const normQuery = normalizeText(rawQuery);
      if (!normQuery) return true;

      const tokens = normQuery.split(/\s+/).filter(t => t.length > 0);
      if (tokens.length === 0) return true;

      const md5 = normalizeText(doc.md5);
      const beneficiario = normalizeText(doc.beneficiario);
      const cpf = normalizeText(doc.cpf);
      const cpfDigits = extractDigits(doc.cpf);
      const rg = normalizeText(doc.rg);
      const rgDigits = extractDigits(doc.rg);
      const curso = normalizeText(doc.curso);
      const faculdade = normalizeText(doc.faculdade);
      const faculdadeNorm = normalizeText(normalizeInstitution(doc.faculdade));
      const natureza = normalizeText(doc.natureza_curso);
      const tipo = normalizeText(doc.tipo_documento);
      const obs = normalizeText(doc.observacoes_conferencia);
      const data = normalizeText(doc.data);
      const carga = normalizeText(doc.carga_horaria);
      const dominio = normalizeText(doc.dominio);
      const extensao = normalizeText(doc.extensao);
      const valor = normalizeText(doc.valor_monetario);
      const de = doc.dados_extras || {};
      const pixChave = normalizeText(doc.pix_chave || de.pix_chave);
      const pixE2e = normalizeText(doc.pix_e2e_id || de.pix_e2e_id);
      const pixAut = normalizeText(doc.pix_autenticacao || de.pix_autenticacao);
      const pixPag = normalizeText(doc.pix_pagador_nome || de.pix_pagador_nome);
      const pixPagBanco = normalizeText(doc.pix_pagador_banco || de.pix_pagador_banco);
      const pixRecBanco = normalizeText(doc.pix_recebedor_banco || de.pix_recebedor_banco);
      const cnpj = normalizeText(doc.cnpj || de.cnpj);
      const cnpjDigits = extractDigits(doc.cnpj || de.cnpj);
      const cnpjRazao = normalizeText(de.razao_social || doc.razao_social);
      const cnpjFantasia = normalizeText(de.nome_fantasia || doc.nome_fantasia);
      const cnpjSituacao = normalizeText(de.situacao_cadastral || doc.situacao_cadastral);
      const cnpjCnae = normalizeText(de.cnae_principal || doc.cnae_principal);
      const cnpjNatJur = normalizeText(de.natureza_juridica || doc.natureza_juridica);
      const cnpjEnd = normalizeText(de.endereco_completo || doc.endereco_completo);
      const todosTipos = Array.isArray(doc.todos_tipos) ? normalizeText(doc.todos_tipos.join(' ')) : '';
      const todosDominios = Array.isArray(doc.todos_dominios) ? normalizeText(doc.todos_dominios.join(' ')) : '';
      const autor = normalizeText(doc.autor);
      const dcObj = (typeof doc.dublin_core === 'object' && doc.dublin_core !== null) ? doc.dublin_core : {};
      const dcTitle = normalizeText(doc.dc_title || dcObj.title);
      const dcSubject = normalizeText(doc.dc_subject || dcObj.subject);
      const dcTool = normalizeText(doc.dc_creator_tool || dcObj.creator_tool);
      const dcProducer = normalizeText(dcObj.producer);
      const dcKeywords = normalizeText(dcObj.keywords);
      const dcDesc = normalizeText(dcObj.description);
      const dcPub = normalizeText(dcObj.publisher);
      const nomesDetectados = Array.isArray(doc.nomes_detectados)
        ? normalizeText(doc.nomes_detectados.join(' '))
        : (Array.isArray(de.nomes_detectados) ? normalizeText(de.nomes_detectados.join(' ')) : '');

      const fullBlob = `${md5} ${beneficiario} ${nomesDetectados} ${cpf} ${cpfDigits} ${rg} ${rgDigits} ${cnpj} ${cnpjDigits} ${cnpjRazao} ${cnpjFantasia} ${cnpjSituacao} ${cnpjCnae} ${cnpjNatJur} ${cnpjEnd} ${curso} ${faculdade} ${faculdadeNorm} ${natureza} ${tipo} ${todosTipos} ${data} ${carga} ${obs} ${dominio} ${todosDominios} ${extensao} ${valor} ${pixChave} ${pixE2e} ${pixAut} ${pixPag} ${pixPagBanco} ${pixRecBanco} ${autor} ${dcTitle} ${dcSubject} ${dcTool} ${dcProducer} ${dcKeywords} ${dcDesc} ${dcPub}`;

      return tokens.every(token => {
        // 1. Busca textual direta na junção de todos os campos
        if (fullBlob.includes(token)) return true;

        // 2. Busca por dígitos de CPF, RG ou CNPJ (sem traço, barra ou pontos)
        const tokenDigits = extractDigits(token);
        if (tokenDigits.length >= 2) {
          if (cpfDigits && cpfDigits.includes(tokenDigits)) return true;
          if (rgDigits && rgDigits.includes(tokenDigits)) return true;
          if (cnpjDigits && cnpjDigits.includes(tokenDigits)) return true;
        }

        return false;
      });
    }

    let isFtsModeActive = false;
    let ftsDebounceTimer = null;

    function toggleFtsSearchMode(forceState) {
      if (typeof forceState === 'boolean') {
        isFtsModeActive = forceState;
      } else {
        isFtsModeActive = !isFtsModeActive;
      }

      const btn = document.getElementById('btnToggleFts');
      const notice = document.getElementById('ftsSearchNotice');
      if (btn) {
        if (isFtsModeActive) {
          btn.classList.add('bg-amber-500', 'text-slate-950', 'font-bold', 'border-amber-400');
          btn.classList.remove('bg-slate-800', 'text-slate-400');
        } else {
          btn.classList.remove('bg-amber-500', 'text-slate-950', 'font-bold', 'border-amber-400');
          btn.classList.add('bg-slate-800', 'text-slate-400');
        }
      }
      if (notice) {
        if (isFtsModeActive) notice.classList.remove('hidden');
        else notice.classList.add('hidden');
      }

      onSearchInput();
    }

    function onSearchInput() {
      const q = (document.getElementById('searchInput').value || '').trim();
      const btnClear = document.getElementById('clearSearchBtn');
      if (q) {
        btnClear.classList.remove('hidden');
      } else {
        btnClear.classList.add('hidden');
      }

      if (isFtsModeActive && q.length >= 2) {
        clearTimeout(ftsDebounceTimer);
        ftsDebounceTimer = setTimeout(() => executeFtsSearch(q), 250);
        return;
      }

      // Modo de busca local padrão
      documents.forEach(d => { delete d.fts_snippet; });
      applyFilter(false);
    }

    async function executeFtsSearch(query) {
      if (!query || query.trim().length < 2) {
        applyFilter(false);
        return;
      }
      try {
        const resp = await fetch(`/api/busca_fts?q=${encodeURIComponent(query)}&limit=100`);
        if (!resp.ok) return;
        const results = await resp.json();
        const ftsMap = new Map();
        results.forEach(r => ftsMap.set(r.md5, r));

        // Filtra documentos pelos resultados do FTS5 preservando dados em memória
        filteredDocs = [];
        results.forEach(r => {
          const original = documents.find(d => d.md5 === r.md5);
          if (original) {
            original.fts_snippet = r.fts_snippet;
            original.fts_score = r.fts_score;
            filteredDocs.push(original);
          } else {
            filteredDocs.push(r);
          }
        });

        currentIndex = filteredDocs.length > 0 ? 0 : -1;
        renderSidebar();
        if (currentIndex >= 0) selectDocument(0);
        updateDocumentCount();
      } catch (e) {
        console.error("Erro na busca FTS5:", e);
      }
    }

    function onSearchKeyDown(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        clearSearch();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        e.target.blur();
      }
    }

    function clearSearch() {
      document.getElementById('searchInput').value = '';
      document.getElementById('clearSearchBtn').classList.add('hidden');
      documents.forEach(d => { delete d.fts_snippet; });
      applyFilter(true);
    }

    function resetFiltersKeepSearch() {
      selectedDominios.clear();
      selectedInstituicoes.clear();
      selectedTipos.clear();
      selectedNaturezas.clear();
      selectedStatus.clear();
      syncActiveFilterVars();

      const inputInst = document.getElementById('inputSearchInst');
      if (inputInst) inputInst.value = '';
      const inputTipo = document.getElementById('inputSearchTipo');
      if (inputTipo) inputTipo.value = '';

      closeAllFilterPopovers();
      applyFilter(false);
    }

    // Determina se um documento ainda não foi processado com sucesso ou está sem classificação válida
    function isDocumentUnprocessed(doc) {
      if (!doc) return true;
      // 1. Explicitamente não processado
      if (doc.status === 'nao_processado' || safeString(doc.status_conferencia).toLowerCase() === 'nao_processado') return true;
      // 2. Falha na leitura ou processamento (nunca classificado com sucesso)
      if (doc.status === 'erro' || (doc.status && doc.status !== 'sucesso')) return true;

      const dom = safeString(doc.dominio || 'academico').toLowerCase();
      // 3. Documento financeiro / PIX: válido se tem valor, chave, id e2e ou pagador/recebedor
      if (dom === 'financeiro') {
        const de = doc.dados_extras || {};
        const hasFin = safeString(doc.valor_monetario).trim() ||
                       safeString(doc.pix_pagador_nome || de.pix_pagador_nome).trim() ||
                       safeString(doc.pix_e2e_id || de.pix_e2e_id).trim() ||
                       safeString(doc.pix_chave || de.pix_chave).trim() ||
                       safeString(doc.beneficiario).trim();
        return !hasFin;
      }
      // 4. Outros domínios (identificação, jurídico, etc.)
      if (dom !== 'academico') {
        if (!safeString(doc.beneficiario).trim() && !safeString(doc.tipo_documento).trim()) return true;
        return false;
      }
      // 5. Acadêmico: sem dados essenciais de classificação (beneficiário e curso vazios)
      if (!safeString(doc.beneficiario).trim() && !safeString(doc.curso).trim()) return true;
      return false;
    }

    function applyFilter(preserveCurrentDoc = true) {
      const rawSearch = (document.getElementById('searchInput').value || '').trim();
      
      filteredDocs = documents.filter(doc => docMatchesFilters(doc, rawSearch, ''));

      updateFacetFilters();
      updateCounters();
      renderSidebar();

      if (typeof currentMainTab !== 'undefined' && currentMainTab === 'galeria') {
        renderGalleryView();
      }

      if (filteredDocs.length > 0) {
        let targetIndex = 0;
        if (preserveCurrentDoc && currentSelectedMd5) {
          const foundIdx = filteredDocs.findIndex(d => d.md5 === currentSelectedMd5);
          if (foundIdx !== -1) {
            targetIndex = foundIdx;
          }
        }
        selectDocument(targetIndex, true);
      } else {
        clearSelectionView();
      }
    }

    // Filtro de Status da Conferência (Hierarquia 5 - Multi-seleção por Tags)
    function updateStatusFilterOptions() {
      const rawSearch = (document.getElementById('searchInput').value || '').trim();
      const baseDocs = documents.filter(doc => docMatchesFilters(doc, rawSearch, 'status'));

      let countPend = 0;
      let countAppr = 0;
      let countUnproc = 0;
      let countDossies = 0;

      baseDocs.forEach(d => {
        const isUnproc = isDocumentUnprocessed(d);
        if (isUnproc) {
          countUnproc++;
        } else {
          const isAppr = safeString(d.status_conferencia || 'pendente').toLowerCase() === 'aprovado';
          if (isAppr) countAppr++;
          else countPend++;
        }
        const pgs = Array.isArray(d.dossie_paginas) ? d.dossie_paginas.length : 0;
        const tipos = Array.isArray(d.todos_tipos) ? d.todos_tipos.length : 0;
        if (pgs >= 2 || tipos >= 2) countDossies++;
      });

      ['statusChips', 'g-statusChips'].forEach(cid => {
        const chipsContainer = document.getElementById(cid);
        if (!chipsContainer) return;
        chipsContainer.innerHTML = '';
        const statusItems = [
          { key: 'pendente', label: 'Pendentes', count: countPend, icon: 'fa-regular fa-clock', color: 'text-amber-400', activeBg: 'bg-amber-600 border-amber-500 text-white' },
          { key: 'aprovado', label: 'Aprovados', count: countAppr, icon: 'fa-solid fa-check-double', color: 'text-emerald-400', activeBg: 'bg-emerald-600 border-emerald-500 text-white' },
          { key: 'dossies', label: 'Dossiês (+2 págs)', count: countDossies, icon: 'fa-solid fa-folder-open', color: 'text-cyan-400', activeBg: 'bg-cyan-600 border-cyan-500 text-white' },
          { key: 'nao_processado', label: 'Não Classificados', count: countUnproc, icon: 'fa-solid fa-triangle-exclamation', color: 'text-rose-400', activeBg: 'bg-rose-600 border-rose-500 text-white' }
        ];

        statusItems.forEach(item => {
          const isSelected = selectedStatus.has(item.key);
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.className = `px-2.5 py-1 rounded-lg text-xs font-medium border transition flex items-center gap-1.5 ${
            isSelected
              ? `${item.activeBg} font-semibold ring-1 ring-amber-400/50 shadow-sm`
              : (item.count === 0 
                  ? 'bg-slate-950/40 text-slate-500 border-slate-900/60 opacity-60 hover:opacity-90 hover:text-slate-300' 
                  : 'bg-slate-950/70 text-slate-300 border-slate-800 hover:bg-slate-800/80 hover:text-amber-300')
          }`;
          chip.innerHTML = `
            <i class="${item.icon} text-[10.5px] ${isSelected ? 'text-white' : item.color}"></i>
            <span>${item.label}</span>
            <span class="text-[10px] px-1.5 py-0.2 rounded-full font-mono ml-0.5 ${isSelected ? 'bg-black/30 text-white font-bold' : 'bg-slate-800 text-slate-400'}">${item.count}</span>
          `;
          chip.onclick = () => {
            toggleStatusFilter(item.key);
          };
          chipsContainer.appendChild(chip);
        });
      });

      ['btnClearStatus', 'g-btnClearStatus'].forEach(bid => {
        const btnClear = document.getElementById(bid);
        if (btnClear) {
          if (selectedStatus.size > 0) btnClear.classList.remove('hidden');
          else btnClear.classList.add('hidden');
        }
      });
    }

    function toggleStatusFilter(st) {
      if (selectedStatus.has(st)) {
        selectedStatus.delete(st);
      } else {
        selectedStatus.add(st);
      }
      syncActiveFilterVars();
      applyFilter(false);
    }

    function setStatusFilter(filter) {
      selectedStatus.clear();
      if (filter && filter !== 'todos') {
        selectedStatus.add(filter);
      }
      syncActiveFilterVars();
      applyFilter(false);
    }

    function resetStatusFilter() {
      selectedStatus.clear();
      syncActiveFilterVars();
      applyFilter(false);
    }

    // Filtro de Formato de Arquivo (PDF, Word, Imagens, Texto - Multi-seleção)
    function updateFormatoFilterOptions() {
      const rawSearch = (document.getElementById('searchInput').value || '').trim();
      const baseDocs = documents.filter(doc => docMatchesFilters(doc, rawSearch, 'formato'));

      let countPdf = 0;
      let countWord = 0;
      let countImage = 0;
      let countText = 0;

      baseDocs.forEach(d => {
        const fmt = getDocFormatMeta(d);
        if (fmt.type === 'pdf') countPdf++;
        else if (fmt.type === 'word') countWord++;
        else if (fmt.type === 'image') countImage++;
        else if (fmt.type === 'text') countText++;
      });

      ['formatoChips', 'g-formatoChips'].forEach(cid => {
        const chipsContainer = document.getElementById(cid);
        if (!chipsContainer) return;
        chipsContainer.innerHTML = '';
        const formatoItems = [
          { key: 'pdf', label: 'PDFs', count: countPdf, icon: 'fa-regular fa-file-pdf', color: 'text-rose-400', activeBg: 'bg-rose-600 border-rose-500 text-white' },
          { key: 'word', label: 'Word / Docs', count: countWord, icon: 'fa-solid fa-file-word', color: 'text-sky-400', activeBg: 'bg-sky-600 border-sky-500 text-white' },
          { key: 'image', label: 'Imagens', count: countImage, icon: 'fa-regular fa-image', color: 'text-emerald-400', activeBg: 'bg-emerald-600 border-emerald-500 text-white' },
          { key: 'text', label: 'Arquivos Texto', count: countText, icon: 'fa-regular fa-file-lines', color: 'text-amber-400', activeBg: 'bg-amber-600 border-amber-500 text-white' }
        ];

        formatoItems.forEach(item => {
          const isSelected = selectedFormatos.has(item.key);
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.className = `px-2.5 py-1 rounded-lg text-xs font-medium border transition flex items-center gap-1.5 ${
            isSelected
              ? `${item.activeBg} font-semibold ring-1 ring-sky-400/50 shadow-sm`
              : (item.count === 0 
                  ? 'bg-slate-950/40 text-slate-500 border-slate-900/60 opacity-60 hover:opacity-90 hover:text-slate-300' 
                  : 'bg-slate-950/70 text-slate-300 border-slate-800 hover:bg-slate-800/80 hover:text-sky-300')
          }`;
          chip.innerHTML = `
            <i class="${item.icon} text-[10.5px] ${isSelected ? 'text-white' : item.color}"></i>
            <span>${item.label}</span>
            <span class="text-[10px] px-1.5 py-0.2 rounded-full font-mono ml-0.5 ${isSelected ? 'bg-black/30 text-white font-bold' : 'bg-slate-800 text-slate-400'}">${item.count}</span>
          `;
          chip.onclick = () => {
            toggleFormatoFilter(item.key);
          };
          chipsContainer.appendChild(chip);
        });
      });

      ['btnClearFormato', 'g-btnClearFormato'].forEach(bid => {
        const btnClear = document.getElementById(bid);
        if (btnClear) {
          if (selectedFormatos.size > 0) btnClear.classList.remove('hidden');
          else btnClear.classList.add('hidden');
        }
      });
    }

    function toggleFormatoFilter(fmt) {
      if (selectedFormatos.has(fmt)) {
        selectedFormatos.delete(fmt);
      } else {
        selectedFormatos.add(fmt);
      }
      syncActiveFilterVars();
      applyFilter(false);
    }

    function resetFormatoFilter() {
      selectedFormatos.clear();
      syncActiveFilterVars();
      applyFilter(false);
    }

    function updateStatusButtonsUI() {}

    function updateCounters() {
      const total = documents.length;

      // Contadores por domínio no total geral do acervo
      let countDomAcad = 0;
      let countDomFin = 0;
      let countDomOutros = 0;

      documents.forEach(d => {
        const dom = safeString(d.dominio || 'academico').toLowerCase();
        if (dom === 'academico') countDomAcad++;
        else if (dom === 'financeiro') countDomFin++;
        else countDomOutros++;
      });

      const elDomTodos = document.getElementById('count-dom-todos');
      if (elDomTodos) elDomTodos.innerText = total;
      const elDomAcad = document.getElementById('count-dom-academico');
      if (elDomAcad) elDomAcad.innerText = countDomAcad;
      const elDomFin = document.getElementById('count-dom-financeiro');
      if (elDomFin) elDomFin.innerText = countDomFin;
      const elDomOutros = document.getElementById('count-dom-outros');
      if (elDomOutros) elDomOutros.innerText = countDomOutros;

      const btnClearDom = document.getElementById('btnClearDomain');
      if (btnClearDom) {
        if (selectedDominios.size > 0) {
          btnClearDom.classList.remove('hidden');
        } else {
          btnClearDom.classList.add('hidden');
        }
      }

      // Contagem de status cruzada com os filtros ativos de Domínio, Instituição, Tipo, Natureza e Busca
      const rawSearch = (document.getElementById('searchInput').value || '').trim();
      const scopeDocs = documents.filter(doc => {
        if (selectedDominios.size > 0) {
          const dom = safeString(doc.dominio || 'academico').toLowerCase();
          const doms = Array.isArray(doc.todos_dominios) && doc.todos_dominios.length > 0
            ? doc.todos_dominios.map(d => safeString(d).toLowerCase())
            : [dom];
          let matchDom = false;
          for (const selDom of selectedDominios) {
            if (selDom === 'outros') {
              const hasOutros = doms.some(d => d !== 'academico' && d !== 'financeiro');
              if (hasOutros || (dom !== 'academico' && dom !== 'financeiro')) { matchDom = true; break; }
            } else {
              if (doms.includes(selDom) || dom === selDom) { matchDom = true; break; }
            }
          }
          if (!matchDom) return false;
        }
        if (selectedInstituicoes.size > 0) {
          const fac = safeString(doc.faculdade).trim().toLowerCase();
          if (!Array.from(selectedInstituicoes).some(s => s.toLowerCase() === fac)) return false;
        }
        if (selectedTipos.size > 0) {
          const docTipo = safeString(doc.tipo_documento).trim().toLowerCase();
          const tipos = Array.isArray(doc.todos_tipos) && doc.todos_tipos.length > 0
            ? doc.todos_tipos.map(t => safeString(t).trim().toLowerCase())
            : [docTipo || 'não identificado'];
          if (!Array.from(selectedTipos).some(st => tipos.includes(st.toLowerCase()))) return false;
        }
        if (selectedNaturezas.size > 0) {
          const docNat = safeString(doc.natureza_curso).trim();
          if (!Array.from(selectedNaturezas).some(sn => docNat === sn || classifyNatureza(docNat) === sn)) return false;
        }
        return matchDocumentSearch(doc, rawSearch);
      });

      const scopeTotal = scopeDocs.length;
      const naoProcessados = scopeDocs.filter(d => isDocumentUnprocessed(d)).length;
      const aprovados = scopeDocs.filter(d => !isDocumentUnprocessed(d) && safeString(d.status_conferencia || 'pendente').toLowerCase() === 'aprovado').length;
      const pendentes = scopeTotal - aprovados - naoProcessados;

      const cntTodos = document.getElementById('count-todos');
      if (cntTodos) cntTodos.innerText = scopeTotal;
      const cntPend = document.getElementById('count-pendente');
      if (cntPend) cntPend.innerText = pendentes;
      const cntAprov = document.getElementById('count-aprovado');
      if (cntAprov) cntAprov.innerText = aprovados;
      const cntNaoProc = document.getElementById('count-nao_processado');
      if (cntNaoProc) cntNaoProc.innerText = naoProcessados;

      document.getElementById('filterResultCount').innerText = `${filteredDocs.length} de ${total}`;
      const mobBadge = document.getElementById('mobBadgeCount');
      if (mobBadge) mobBadge.innerText = filteredDocs.length;
      updateBulkUI();
      
      const label = [];
      if (rawSearch) {
        const shortQ = rawSearch.length > 15 ? rawSearch.substring(0, 15) + '...' : rawSearch;
        label.push(`"${shortQ}"`);
      }
      if (selectedDominios.size > 0) {
        const dMap = { academico: 'Acadêmico', financeiro: 'PIX / Fin', outros: 'Outros', identificacao: 'Identificação' };
        label.push(`Domínio: ${Array.from(selectedDominios).map(d => dMap[d] || d).join(', ')}`);
      }
      if (selectedInstituicoes.size > 0) {
        const instList = Array.from(selectedInstituicoes);
        const instLabel = instList.length === 1 ? instList[0] : `${instList.length} Instituições`;
        label.push(instLabel);
      }
      if (selectedTipos.size > 0) {
        const tipoList = Array.from(selectedTipos);
        const tipoLabel = tipoList.length === 1 ? tipoList[0] : `${tipoList.length} Tipos`;
        label.push(tipoLabel);
      }
      if (selectedNaturezas.size > 0) {
        const natList = Array.from(selectedNaturezas);
        const natLabel = natList.length === 1 ? formatShortNature(natList[0]) : `${natList.length} Níveis`;
        label.push(natLabel);
      }
      if (selectedStatus.size > 0) {
        const stMap = { pendente: 'Pendentes', aprovado: 'Aprovados', nao_processado: 'Não Classificados' };
        label.push(Array.from(selectedStatus).map(s => stMap[s] || s).join(', '));
      }
      document.getElementById('activeFilterLabel').innerText = label.length > 0 ? `(${label.join(' • ')})` : '';

      const totalUnprocessed = documents.filter(d => isDocumentUnprocessed(d)).length;
      const totalClassificados = total - totalUnprocessed;
      const totalAprovados = documents.filter(d => !isDocumentUnprocessed(d) && safeString(d.status_conferencia).toLowerCase() === 'aprovado').length;
      const pctHumano = totalClassificados > 0 ? Math.round((totalAprovados / totalClassificados) * 100) : 0;
      const pctIA = total > 0 ? Math.round((totalClassificados / total) * 100) : 0;

      const aiElem = document.getElementById('aiClassifiedText');
      if (aiElem) {
        aiElem.innerText = `${totalClassificados} / ${total} (${pctIA}%)`;
      }

      const progElem = document.getElementById('progressText');
      if (progElem) {
        progElem.innerText = `${totalAprovados} / ${totalClassificados} (${pctHumano}%)`;
      }

      const barElem = document.getElementById('progressBar');
      if (barElem) {
        barElem.style.width = `${pctHumano}%`;
      }

      // Atualiza contadores da Galeria de Documentos
      const tabBadgeGal = document.getElementById('tabBadgeGaleriaCount');
      if (tabBadgeGal) {
        const c = typeof filteredDocs !== 'undefined' ? filteredDocs.length : total;
        tabBadgeGal.innerText = c.toLocaleString('pt-BR');
      }
      const subCounter = document.getElementById('galeriaSubheaderCounter');
      if (subCounter) {
        const c = typeof filteredDocs !== 'undefined' ? filteredDocs.length : total;
        subCounter.innerText = `${c.toLocaleString('pt-BR')} documentos no filtro atual`;
      }

      if (typeof currentMainTab !== 'undefined' && currentMainTab === 'bi') {
        renderBIDashboard();
      }
    }

    // Retorna badge visual estilizado para o tipo de natureza
    function getNaturezaBadge(natureza) {
      const natStr = safeString(natureza).trim();
      if (!natStr) {
        return `<span class="bg-slate-800 text-slate-400 border border-slate-700/80 px-1.5 py-0.5 rounded text-[10px] font-medium truncate max-w-[180px] inline-flex items-center gap-1"><i class="fa-regular fa-circle-question text-[9px]"></i>Não identificada</span>`;
      }
      const n = normalizeText(natStr);
      if (n.includes('graduacao') || n.includes('superior') || n.includes('bacharel')) {
        return `<span class="bg-purple-500/10 text-purple-300 border border-purple-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium truncate max-w-[190px] inline-flex items-center gap-1"><i class="fa-solid fa-graduation-cap text-[9px] text-purple-400"></i>${natStr}</span>`;
      }
      if (n.includes('lato sensu') || n.includes('especializacao') || n.includes('mba')) {
        return `<span class="bg-sky-500/10 text-sky-300 border border-sky-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium truncate max-w-[190px] inline-flex items-center gap-1"><i class="fa-solid fa-certificate text-[9px] text-sky-400"></i>${natStr}</span>`;
      }
      if (n.includes('stricto sensu') || n.includes('mestrado') || n.includes('doutorado')) {
        return `<span class="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium truncate max-w-[190px] inline-flex items-center gap-1"><i class="fa-solid fa-award text-[9px] text-emerald-400"></i>${natStr}</span>`;
      }
      if (n.includes('tecnico') || n.includes('profissionalizante')) {
        return `<span class="bg-amber-500/10 text-amber-300 border border-amber-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium truncate max-w-[190px] inline-flex items-center gap-1"><i class="fa-solid fa-wrench text-[9px] text-amber-400"></i>${natStr}</span>`;
      }
      return `<span class="bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium truncate max-w-[190px] inline-flex items-center gap-1"><i class="fa-solid fa-book-bookmark text-[9px] text-indigo-400"></i>${natStr}</span>`;
    }

    // Retorna badge visual estilizado para o Tipo de Documento
    function getTipoBadge(tipo) {
      const t = safeString(tipo).trim() || 'Não identificado';
      const norm = normalizeText(t);
      if (norm.includes('diploma')) {
        return `<span class="bg-teal-500/10 text-teal-300 border border-teal-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-graduation-cap text-[9px] text-teal-400"></i>${t}</span>`;
      }
      if (norm.includes('certificado')) {
        return `<span class="bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-certificate text-[9px] text-cyan-400"></i>${t}</span>`;
      }
      if (norm.includes('historico')) {
        return `<span class="bg-violet-500/10 text-violet-300 border border-violet-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-book-bookmark text-[9px] text-violet-400"></i>${t}</span>`;
      }
      if (norm.includes('declaracao')) {
        return `<span class="bg-amber-500/10 text-amber-300 border border-amber-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-file-lines text-[9px] text-amber-400"></i>${t}</span>`;
      }
      if (norm.includes('ajuste anual') || norm.includes('imposto de renda')) {
        return `<span class="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-file-invoice-dollar text-[9px] text-emerald-400"></i>${t}</span>`;
      }
      if (norm.includes('informe') || norm.includes('rendimentos')) {
        return `<span class="bg-teal-500/10 text-teal-300 border border-teal-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-chart-line text-[9px] text-teal-400"></i>${t}</span>`;
      }
      if (norm.includes('cheque') || norm.includes('talao') || norm.includes('talão')) {
        return `<span class="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-money-check-dollar text-[9px] text-emerald-400"></i>${t}</span>`;
      }
      if (norm.includes('boleto')) {
        return `<span class="bg-amber-500/10 text-amber-300 border border-amber-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-barcode text-[9px] text-amber-400"></i>${t}</span>`;
      }
      if (norm.includes('promissoria') || norm.includes('promissória')) {
        return `<span class="bg-amber-500/10 text-amber-300 border border-amber-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-hashtag text-[9px] text-amber-400"></i>${t}</span>`;
      }
      if (norm.includes('pix')) {
        return `<span class="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-brands fa-pix text-[9px] text-emerald-400"></i>${t}</span>`;
      }
      if (norm.includes('recibo') || norm.includes('comprovante') || norm.includes('pagamento')) {
        return `<span class="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-receipt text-[9px] text-emerald-400"></i>${t}</span>`;
      }
      if (norm.includes('rg') || norm.includes('cnh') || norm.includes('identidade') || norm.includes('identificacao') || norm.includes('civil')) {
        return `<span class="bg-sky-500/10 text-sky-300 border border-sky-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-regular fa-id-card text-[9px] text-sky-400"></i>${t}</span>`;
      }
      if (norm.includes('crv') || norm.includes('dut')) {
        return `<span class="bg-orange-500/10 text-orange-300 border border-orange-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-car text-[9px] text-orange-400"></i>${t}</span>`;
      }
      if (norm.includes('crlv') || norm.includes('licenciamento')) {
        return `<span class="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-car-side text-[9px] text-emerald-400"></i>${t}</span>`;
      }
      if (norm.includes('atpv') || norm.includes('transferencia de propriedade') || norm.includes('transferência de propriedade')) {
        return `<span class="bg-amber-500/10 text-amber-300 border border-amber-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-right-left text-[9px] text-amber-400"></i>${t}</span>`;
      }
      if (norm.includes('veicular') || norm.includes('remocao') || norm.includes('remoção') || norm.includes('vistoria') || norm.includes('arrematacao') || norm.includes('arrematação')) {
        return `<span class="bg-orange-500/10 text-orange-300 border border-orange-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-car text-[9px] text-orange-400"></i>${t}</span>`;
      }
      if (norm.includes('contrato') || norm.includes('termo') || norm.includes('procuracao')) {
        return `<span class="bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-solid fa-file-contract text-[9px] text-indigo-400"></i>${t}</span>`;
      }
      return `<span class="bg-slate-800 text-slate-400 border border-slate-700/80 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1 truncate max-w-[130px]"><i class="fa-regular fa-file text-[9px]"></i>${t}</span>`;
    }

    function renderSidebar() {
      const listEl = document.getElementById('docList');
      listEl.innerHTML = '';

      if (filteredDocs.length === 0) {
        const rawSearch = (document.getElementById('searchInput').value || '').trim();
        const hasActiveFilters = selectedStatus.size > 0 || selectedNaturezas.size > 0 || selectedTipos.size > 0 || selectedInstituicoes.size > 0 || selectedDominios.size > 0;
        
        let extraMsg = '';
        if (rawSearch && hasActiveFilters) {
          const globalMatches = documents.filter(doc => matchDocumentSearch(doc, rawSearch)).length;
          if (globalMatches > 0) {
            const activeLabels = [];
            if (selectedDominios.size > 0) activeLabels.push(`Domínio (${selectedDominios.size})`);
            if (selectedInstituicoes.size > 0) activeLabels.push(`Instituição (${selectedInstituicoes.size})`);
            if (selectedTipos.size > 0) activeLabels.push(`Tipo (${selectedTipos.size})`);
            if (selectedNaturezas.size > 0) activeLabels.push(`Nível (${selectedNaturezas.size})`);
            if (selectedStatus.size > 0) activeLabels.push(`Status (${selectedStatus.size})`);

            extraMsg = `
              <div class="p-2.5 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-300 text-left space-y-1.5 mt-2">
                <p class="font-medium flex items-center gap-1.5 text-[11px]">
                  <i class="fa-solid fa-triangle-exclamation text-amber-400"></i>
                  ${globalMatches} resultado(s) em outras categorias!
                </p>
                <p class="text-[10px] text-slate-400">Filtros ativos (${activeLabels.join(' • ')}) ocultam esses registros.</p>
                <button onclick="resetFiltersKeepSearch()" class="w-full py-1 px-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-[11px] font-medium transition flex items-center justify-center gap-1">
                  <i class="fa-solid fa-filter-circle-xmark text-[10px]"></i> Ver todos os ${globalMatches} resultados
                </button>
              </div>
            `;
          }
        }

        listEl.innerHTML = `
          <div class="text-center py-10 px-4 text-xs text-slate-500 space-y-2">
            <i class="fa-solid fa-filter-circle-xmark text-2xl text-slate-600"></i>
            <p>Nenhum documento encontrado com os filtros atuais.</p>
            ${extraMsg}
            <div class="pt-2">
              <button onclick="resetAllFilters()" class="text-indigo-400 hover:underline text-[11px]">Limpar todos os filtros e busca</button>
            </div>
          </div>
        `;
        return;
      }

      filteredDocs.forEach((doc, idx) => {
        const isSelected = idx === currentIndex;
        const isDocChecked = selectedMd5s.has(doc.md5);
        const isUnproc = isDocumentUnprocessed(doc);
        const isApproved = !isUnproc && safeString(doc.status_conferencia || 'pendente').toLowerCase() === 'aprovado';
        const isImg = isImageDoc(doc);
        const docDom = safeString(doc.dominio || 'academico').toLowerCase();
        
        const card = document.createElement('div');
        let cardClass = 'p-2.5 rounded-lg border text-xs cursor-pointer transition flex flex-col gap-1.5 ';
        if (isDocChecked) {
          cardClass += 'bg-emerald-950/25 border-emerald-500/70 shadow-sm ring-1 ring-emerald-500/50 text-slate-200';
        } else if (isSelected) {
          cardClass += 'bg-slate-800/95 border-emerald-500/60 shadow-md ring-1 ring-emerald-500/30 text-slate-100';
        } else if (isUnproc) {
          cardClass += 'bg-slate-900/40 hover:bg-slate-800/50 border-slate-800/60 text-slate-400';
        } else {
          cardClass += 'bg-slate-900/50 hover:bg-slate-800/60 border-slate-800/80 text-slate-400';
        }
        card.className = cardClass;

        card.onclick = () => selectDocument(idx);

        let statusBadge = '';
        if (isUnproc) {
          statusBadge = `<span class="bg-rose-500/10 text-rose-400 border border-rose-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1"><i class="fa-solid fa-file-circle-question text-[9px]"></i> Não Lido</span>`;
        } else if (isApproved) {
          statusBadge = `<span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 flex items-center gap-1"><i class="fa-solid fa-check text-[9px]"></i> OK</span>`;
        } else {
          statusBadge = `<span class="bg-amber-500/10 text-amber-400 border border-amber-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0">Pendente</span>`;
        }

        const fmt = getDocFormatMeta(doc);
        const extIcon = `<i class="${fmt.icon} ${fmt.color} text-[10px]" title="Arquivo ${fmt.label}"></i>`;

        let middleBadge = '';
        if (docDom === 'financeiro') {
          const de = doc.dados_extras || {};
          const isPix = (doc.tipo_documento || '').toLowerCase().includes('pix') || (doc.todos_tipos || []).some(t => safeString(t).toLowerCase().includes('pix')) || doc.pix_chave || doc.pix_e2e_id || de.pix_chave || de.pix_e2e_id;
          const isCheque = (doc.tipo_documento || '').toLowerCase().includes('cheque') || (doc.tipo_documento || '').toLowerCase().includes('talao');
          const isBoleto = (doc.tipo_documento || '').toLowerCase().includes('boleto');
          const isIrpf = (doc.tipo_documento || '').toLowerCase().includes('imposto de renda') || (doc.tipo_documento || '').toLowerCase().includes('ajuste anual');
          const isInforme = (doc.tipo_documento || '').toLowerCase().includes('informe');
          
          let iconHtml = '<i class="fa-solid fa-coins text-[9px]"></i>';
          if (isPix) iconHtml = '<i class="fa-brands fa-pix text-[9px]"></i>';
          else if (isCheque) iconHtml = '<i class="fa-solid fa-money-check-dollar text-[9px]"></i>';
          else if (isBoleto) iconHtml = '<i class="fa-solid fa-barcode text-[9px]"></i>';
          else if (isIrpf) iconHtml = '<i class="fa-solid fa-file-invoice-dollar text-[9px]"></i>';
          else if (isInforme) iconHtml = '<i class="fa-solid fa-chart-line text-[9px]"></i>';

          const valDisplay = doc.valor_monetario ? doc.valor_monetario : (isPix ? 'PIX' : (isBoleto ? 'Boleto' : (isCheque ? 'Cheque' : (isIrpf ? 'IRPF' : (isInforme ? 'Informe' : 'Financeiro')))));
          middleBadge = `<span class="bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold flex items-center gap-1 shrink-0">${iconHtml}${valDisplay}</span>`;
        } else if (docDom === 'veicular') {
          middleBadge = `<span class="bg-orange-500/10 text-orange-300 border border-orange-500/30 px-1.5 py-0.5 rounded text-[10px] font-medium flex items-center gap-1 shrink-0"><i class="fa-solid fa-car text-[9px]"></i>Veicular</span>`;
        } else if (docDom === 'identificacao') {
          middleBadge = `<span class="bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 px-1.5 py-0.5 rounded text-[10px] font-medium flex items-center gap-1 shrink-0"><i class="fa-regular fa-id-badge text-[9px]"></i>Identidade</span>`;
        } else if (docDom === 'juridico') {
          middleBadge = `<span class="bg-amber-500/10 text-amber-300 border border-amber-500/30 px-1.5 py-0.5 rounded text-[10px] font-medium flex items-center gap-1 shrink-0"><i class="fa-solid fa-gavel text-[9px]"></i>Jurídico</span>`;
        } else if (docDom === 'outro') {
          middleBadge = `<span class="bg-purple-500/10 text-purple-300 border border-purple-500/30 px-1.5 py-0.5 rounded text-[10px] font-medium flex items-center gap-1 shrink-0"><i class="fa-regular fa-file text-[9px]"></i>Outro</span>`;
        } else {
          middleBadge = isUnproc
            ? `<span class="bg-slate-800/80 text-slate-500 border border-slate-700/60 px-1.5 py-0.5 rounded text-[10px] font-medium inline-flex items-center gap-1"><i class="fa-solid fa-hourglass-start text-[9px]"></i>Aguardando</span>`
            : (doc.natureza_curso ? getNaturezaBadge(doc.natureza_curso) : (doc.curso ? `<span class="bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 px-1.5 py-0.5 rounded text-[10px] font-medium truncate max-w-[190px] inline-flex items-center gap-1"><i class="fa-solid fa-graduation-cap text-[9px]"></i>Acadêmico</span>` : ''));
        }

        const tipoBadge = isUnproc
          ? `<span class="bg-slate-800/80 text-slate-500 border border-slate-700/60 px-1.5 py-0.5 rounded text-[10px] font-medium inline-flex items-center gap-1">${extIcon}<span>${fmt.label}</span></span>`
          : getTipoBadge(doc.tipo_documento);

        const md5Short = safeString(doc.md5).substring(0, 10);
        const nome = safeString(doc.beneficiario) || (isUnproc ? (doc.nome_arquivo || 'Arquivo não lido') : 'Sem nome informado');
        const cpf = safeString(doc.cpf);
        const rg = safeString(doc.rg);

        let subText = '';
        if (docDom === 'financeiro') {
          const de = doc.dados_extras || {};
          const pagador = doc.pix_pagador_nome || de.pix_pagador_nome || '';
          const chave = doc.pix_chave || de.pix_chave || '';
          const isIrpf = (doc.tipo_documento || '').toLowerCase().includes('imposto de renda') || (doc.tipo_documento || '').toLowerCase().includes('ajuste anual');
          const isBoleto = (doc.tipo_documento || '').toLowerCase().includes('boleto');
          const isCheque = (doc.tipo_documento || '').toLowerCase().includes('cheque') || (doc.tipo_documento || '').toLowerCase().includes('talao');
          const isInforme = (doc.tipo_documento || '').toLowerCase().includes('informe');

          if (pagador) {
            subText = `Origem: ${pagador}`;
          } else if (chave) {
            subText = `Chave: ${chave}`;
          } else if (isIrpf) {
            const ex = de.exercicio || de.exercicio_irpf || '';
            const ano = de.ano_calendario || '';
            subText = (ex || ano) ? `IRPF Exercício ${ex || '-'} • Ano ${ano || '-'}` : (doc.observacoes_conferencia || 'Declaração de Ajuste Anual');
          } else if (isInforme) {
            const fonte = de.fonte_pagadora || doc.faculdade || '';
            subText = fonte ? `Fonte: ${fonte}` : (doc.observacoes_conferencia || 'Informe de Rendimentos');
          } else if (isCheque) {
            const bco = de.banco_cheque || doc.faculdade || '';
            const n = de.numero_cheque || (de.numeros_cheque && de.numeros_cheque[0]) || '';
            subText = [bco, n ? `Nº ${n}` : ''].filter(Boolean).join(' • ') || (doc.observacoes_conferencia || 'Cheque Bancário');
          } else if (isBoleto) {
            const bco = doc.faculdade || '';
            subText = bco ? `Banco: ${bco}` : (doc.observacoes_conferencia || 'Boleto Bancário');
          } else {
            subText = safeString(doc.observacoes_conferencia || doc.tipo_documento || 'Documento Financeiro');
          }
        } else if (docDom === 'veicular') {
          const de = doc.dados_extras || {};
          const p = doc.placa || de.placa || '';
          const ren = doc.renavam || de.renavam || '';
          const mm = de.marca_modelo || doc.curso || '';
          subText = [p ? `Placa: ${p}` : '', ren ? `Renavam: ${ren}` : '', mm, doc.faculdade || ''].filter(Boolean).join(' • ') || 'Documento Veicular';
        } else if (docDom === 'identificacao') {
          const emissor = doc.faculdade ? `Emissor: ${doc.faculdade}` : '';
          const rgNum = doc.rg ? `RG: ${doc.rg}` : '';
          subText = [emissor, rgNum].filter(Boolean).join(' • ') || 'Documento de Identificação';
        } else if (docDom === 'juridico') {
          subText = safeString(doc.faculdade ? `Órgão: ${doc.faculdade}` : (doc.tipo_documento || 'Documento Jurídico'));
        } else {
          subText = safeString(doc.curso) || (isUnproc ? (doc.caminho_relativo || 'Clique em Classificar para extrair dados') : (docDom === 'academico' ? 'Curso não informado' : safeString(doc.nome_arquivo || 'Documento')));
        }

        const tiposCount = Array.isArray(doc.todos_tipos) ? doc.todos_tipos.length : 1;
        const multiBadge = tiposCount > 1 
          ? `<span class="bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-1 py-0.2 rounded text-[9px] font-semibold shrink-0" title="${doc.todos_tipos.join(', ')}">+${tiposCount - 1} doc${tiposCount > 2 ? 's' : ''}</span>`
          : '';

        const isHybridFallback = (doc.metodo_leitura === 'hibrido_fallback_openai');
        const hybridBadge = isHybridFallback
          ? `<span class="bg-amber-500/20 text-amber-300 border border-amber-500/40 px-1 py-0.2 rounded text-[9px] font-semibold shrink-0 flex items-center gap-0.5" title="Classificado via Fallback Híbrido (Ollama ➔ OpenAI)"><i class="fa-solid fa-bolt text-amber-400 text-[8px]"></i>Híbrido</span>`
          : '';

        const isDuplicate = Boolean(doc.duplicata_de);
        const dupBadge = isDuplicate
          ? `<span class="bg-rose-500/20 text-rose-300 border border-rose-500/40 px-1 py-0.2 rounded text-[9px] font-semibold shrink-0 flex items-center gap-0.5" title="Possível duplicata"><i class="fa-solid fa-copy text-rose-400 text-[8px]"></i>Dup</span>`
          : '';

        const isSigned = Boolean(doc.tem_assinatura_digital);
        const sigBadge = isSigned
          ? `<span class="bg-purple-500/20 text-purple-300 border border-purple-500/40 px-1 py-0.2 rounded text-[9px] font-semibold shrink-0 flex items-center gap-0.5" title="Assinado Digitalmente ICP-Brasil"><i class="fa-solid fa-file-signature text-purple-400 text-[8px]"></i>Assinado</span>`
          : '';

        const isDigital = Boolean(doc.eh_nativo_digital);
        const digitalBadge = isDigital
          ? `<span class="bg-sky-500/20 text-sky-300 border border-sky-500/40 px-1 py-0.2 rounded text-[9px] font-semibold shrink-0 flex items-center gap-0.5" title="PDF Nativo Digital"><i class="fa-solid fa-file-lines text-sky-400 text-[8px]"></i>Digital</span>`
          : '';

        const isDossier = Boolean(doc.dossie_id);
        const dossierBadge = isDossier
          ? `<span class="bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 px-1 py-0.2 rounded text-[9px] font-semibold shrink-0 flex items-center gap-0.5" title="Parte de Dossiê"><i class="fa-solid fa-folder-tree text-indigo-400 text-[8px]"></i>Dossiê</span>`
          : '';

        const ftsSnippetHtml = doc.fts_snippet
          ? `<div class="text-[10px] text-amber-200/90 font-mono bg-amber-950/40 p-1 rounded border border-amber-500/20 mt-1 line-clamp-2">${doc.fts_snippet}</div>`
          : '';

        const chkBoxHtml = `<input type="checkbox" ${isDocChecked ? 'checked' : ''} onclick="event.stopPropagation(); toggleSelectDoc('${doc.md5}', this.checked)" class="rounded border-slate-700 bg-slate-950 text-emerald-500 focus:ring-emerald-500 cursor-pointer h-3.5 w-3.5 shrink-0 mr-0.5" title="Selecionar para ações em lote">`;

        if (sidebarViewMode === 'thumbnails') {
          const thumbSrc = `/api/thumbnail/${doc.md5}?w=240`;
          card.innerHTML = `
            <div class="flex gap-2.5 items-start">
              <div class="w-14 h-18 sm:w-16 sm:h-20 bg-slate-950 rounded border border-slate-800/90 overflow-hidden shrink-0 shadow-sm relative group">
                <img src="${thumbSrc}" loading="lazy" alt="Miniatura"
                     class="w-full h-full object-cover object-top transition-transform duration-200 group-hover:scale-105"
                     onerror="this.style.display='none'; this.nextElementSibling.classList.remove('hidden');">
                <div class="hidden w-full h-full flex flex-col items-center justify-center text-slate-600 bg-slate-950 p-1 text-center">
                  ${extIcon}
                  <span class="text-[8px] font-mono mt-0.5">${isImg ? 'IMG' : 'PDF'}</span>
                </div>
              </div>
              <div class="flex-1 min-w-0 flex flex-col gap-1">
                <div class="flex items-center justify-between gap-1">
                  <div class="flex items-center gap-1.5 truncate">
                    ${chkBoxHtml}
                    <span class="font-mono text-[11px] text-slate-300 shrink-0">${md5Short}...</span>
                    ${tipoBadge}
                    ${multiBadge}
                    ${hybridBadge}
                    ${dupBadge}
                    ${sigBadge}
                    ${digitalBadge}
                    ${dossierBadge}
                  </div>
                  ${statusBadge}
                </div>
                <div class="font-semibold text-slate-100 truncate text-[12px]">${nome}</div>
                <div class="flex items-center justify-between gap-1 pt-0.5">
                  ${middleBadge}
                  <div class="flex items-center gap-1 shrink-0">
                    ${rg ? `<span class="font-mono text-[10px] text-slate-400 bg-slate-800/80 px-1 rounded" title="RG / Identidade">${rg}</span>` : ''}
                    ${cpf ? `<span class="font-mono text-[10px] text-slate-500 shrink-0" title="CPF">${cpf}</span>` : ''}
                  </div>
                </div>
                <div class="text-[11px] text-slate-400 truncate">${subText}</div>
                ${ftsSnippetHtml}
              </div>
            </div>
          `;
        } else {
          card.innerHTML = `
            <div class="flex items-center justify-between gap-1">
              <div class="flex items-center gap-1.5 truncate">
                ${chkBoxHtml}
                ${extIcon}
                <span class="font-mono text-[11px] text-slate-300 shrink-0">${md5Short}...</span>
                ${tipoBadge}
                ${multiBadge}
                ${hybridBadge}
                ${dupBadge}
                ${sigBadge}
                ${digitalBadge}
                ${dossierBadge}
              </div>
              ${statusBadge}
            </div>
            <div class="font-semibold text-slate-100 truncate">${nome}</div>
            <div class="flex items-center justify-between gap-1 pt-0.5">
              ${middleBadge}
              <div class="flex items-center gap-1.5 shrink-0">
                ${rg ? `<span class="font-mono text-[10px] text-slate-400 bg-slate-800/80 px-1 rounded" title="RG / Identidade">${rg}</span>` : ''}
                ${cpf ? `<span class="font-mono text-[10px] text-slate-500 shrink-0" title="CPF">${cpf}</span>` : ''}
              </div>
            </div>
            <div class="text-[11px] text-slate-400 line-clamp-1">${subText}</div>
            ${ftsSnippetHtml}
          `;
        }
        listEl.appendChild(card);
      });
    }

    function resetAllFilters() {
      document.getElementById('searchInput').value = '';
      document.getElementById('clearSearchBtn').classList.add('hidden');
      const gSearch = document.getElementById('gallerySearchInput');
      if (gSearch) gSearch.value = '';
      const gClear = document.getElementById('galleryClearSearchBtn');
      if (gClear) gClear.classList.add('hidden');
      if (typeof galleryCurrentPage !== 'undefined') galleryCurrentPage = 1;

      activeQuickView = 'todos';
      updateQuickViewUI();

      selectedDominios.clear();
      selectedInstituicoes.clear();
      selectedTipos.clear();
      selectedNaturezas.clear();
      selectedStatus.clear();
      selectedFormatos.clear();
      syncActiveFilterVars();

      ['inputSearchInst', 'g-inputSearchInst'].forEach(id => {
        const inp = document.getElementById(id);
        if (inp) inp.value = '';
      });
      ['inputSearchTipo', 'g-inputSearchTipo'].forEach(id => {
        const inp = document.getElementById(id);
        if (inp) inp.value = '';
      });
      const selInst = document.getElementById('selectInstituicaoFilter');
      if (selInst) selInst.value = '';
      ['btnClearInstituicao', 'g-btnClearInstituicao'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.classList.add('hidden');
      });
      const selNat = document.getElementById('selectNaturezaFilter');
      if (selNat) selNat.value = '';
      ['btnClearNatureza', 'g-btnClearNatureza'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.classList.add('hidden');
      });
      const selTipo = document.getElementById('selectTipoFilter');
      if (selTipo) selTipo.value = '';
      ['btnClearTipo', 'g-btnClearTipo'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.classList.add('hidden');
      });
      ['btnClearDomain', 'g-btnClearDomain'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.classList.add('hidden');
      });
      ['btnClearStatus', 'g-btnClearStatus'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.classList.add('hidden');
      });
      ['btnClearFormato', 'g-btnClearFormato'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.classList.add('hidden');
      });

      closeAllFilterPopovers();
      applyFilter(true);
    }

    function updateSidebarSelection() {
      const listEl = document.getElementById('docList');
      if (!listEl) return;
      const cards = listEl.children;
      for (let i = 0; i < cards.length; i++) {
        if (!cards[i].classList || !cards[i].classList.contains('cursor-pointer')) continue;
        const doc = filteredDocs[i];
        const isDocChecked = doc && selectedMd5s.has(doc.md5);
        if (i === currentIndex) {
          cards[i].className = `p-2.5 rounded-lg border text-xs cursor-pointer transition flex flex-col gap-1.5 ${
            isDocChecked
              ? 'bg-emerald-950/30 border-emerald-500/80 ring-2 ring-emerald-500/50'
              : 'bg-slate-800/95 border-emerald-500/60 shadow-md ring-1 ring-emerald-500/30'
          }`;
          cards[i].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        } else {
          cards[i].className = `p-2.5 rounded-lg border text-xs cursor-pointer transition flex flex-col gap-1.5 ${
            isDocChecked
              ? 'bg-emerald-950/20 border-emerald-500/70 ring-1 ring-emerald-500/40 text-slate-200'
              : 'bg-slate-900/50 hover:bg-slate-800/60 border-slate-800/80 text-slate-400'
          }`;
        }
      }
    }

    let currentLoadedPdfMd5 = null;
    let currentDossieActivePage = 1;
    let pdfLoadTimeout = null;

