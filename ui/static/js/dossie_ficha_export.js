    let selectedDossierPages = new Set();
    let targetDossierClassifyPages = [];
    let lastRenderedDossieMd5 = null;

    const KNOWN_DOSSIER_TYPES = [
      // Financeiro
      { name: 'Contrato de Compra e Venda', category: 'Jurídico', icon: 'fa-solid fa-file-contract' },
      { name: 'Recibo', category: 'Financeiro', icon: 'fa-solid fa-receipt' },
      { name: 'Recibo de Pagamento', category: 'Financeiro', icon: 'fa-solid fa-receipt' },
      { name: 'Nota Promissória', category: 'Financeiro', icon: 'fa-solid fa-money-bill-wave' },
      { name: 'Boleto Bancário', category: 'Financeiro', icon: 'fa-solid fa-barcode' },
      { name: 'Folha de Cheque', category: 'Financeiro', icon: 'fa-solid fa-money-check' },
      { name: 'Talão de Cheques', category: 'Financeiro', icon: 'fa-solid fa-money-check-dollar' },
      { name: 'Comprovante PIX', category: 'Financeiro', icon: 'fa-brands fa-pix' },
      { name: 'Comprovante de Pagamento Bancário', category: 'Financeiro', icon: 'fa-solid fa-circle-dollar-to-slot' },
      { name: 'Comprovante de Transferência Bancária (TED/DOC)', category: 'Financeiro', icon: 'fa-solid fa-money-bill-transfer' },
      { name: 'Extrato Bancário', category: 'Financeiro', icon: 'fa-solid fa-list-ol' },
      { name: 'Nota Fiscal', category: 'Financeiro', icon: 'fa-solid fa-file-invoice-dollar' },
      { name: 'Informe de Rendimentos Financeiros', category: 'Financeiro', icon: 'fa-solid fa-chart-line' },
      { name: 'Declaração de Imposto de Renda', category: 'Financeiro', icon: 'fa-solid fa-file-invoice' },
      { name: 'Recibo de Entrega da Declaração de Ajuste Anual', category: 'Financeiro', icon: 'fa-solid fa-file-invoice' },
      // Identificação
      { name: 'RG / Identidade', category: 'Identificação', icon: 'fa-regular fa-id-card' },
      { name: 'CPF', category: 'Identificação', icon: 'fa-solid fa-fingerprint' },
      { name: 'CNH', category: 'Identificação', icon: 'fa-solid fa-id-badge' },
      { name: 'Certidão de Nascimento', category: 'Identificação', icon: 'fa-solid fa-baby' },
      { name: 'Certidão de Casamento', category: 'Identificação', icon: 'fa-solid fa-ring' },
      // Jurídico
      { name: 'Contrato', category: 'Jurídico', icon: 'fa-solid fa-file-signature' },
      { name: 'Procuração', category: 'Jurídico', icon: 'fa-solid fa-handshake' },
      { name: 'Termo de Posse', category: 'Jurídico', icon: 'fa-solid fa-landmark' },
      // Acadêmico
      { name: 'Diploma', category: 'Acadêmico', icon: 'fa-solid fa-graduation-cap' },
      { name: 'Certificado', category: 'Acadêmico', icon: 'fa-solid fa-award' },
      { name: 'Histórico Escolar', category: 'Acadêmico', icon: 'fa-solid fa-book-open' },
      { name: 'Declaração', category: 'Acadêmico', icon: 'fa-solid fa-file-lines' },
      // Profissional
      { name: 'Carteira de Trabalho', category: 'Profissional', icon: 'fa-solid fa-briefcase' },
      { name: 'Cartão CNPJ', category: 'Profissional', icon: 'fa-solid fa-building' },
      // Outros
      { name: 'Documento Diverso', category: 'Outros', icon: 'fa-solid fa-file' },
      { name: 'Outro', category: 'Outros', icon: 'fa-solid fa-folder-open' }
    ];

    function renderDossierPagesGrid(doc) {
      const gridEl = document.getElementById('dossierPagesGrid');
      const countBadge = document.getElementById('dossierPageCountBadge');
      const pillsEl = document.getElementById('dossierQuickPills');
      const tabBadge = document.getElementById('tabBadgePaginas');
      if (!gridEl) return;
      gridEl.innerHTML = '';
      if (pillsEl) pillsEl.innerHTML = '';

      if (!doc) {
        gridEl.innerHTML = '<div class="col-span-2 text-center py-8 text-slate-500 text-xs">Nenhum documento selecionado.</div>';
        if (countBadge) countBadge.innerText = '0 páginas';
        if (tabBadge) tabBadge.classList.add('hidden');
        selectedDossierPages.clear();
        updateDossierBatchUI(0);
        return;
      }

      // Se mudou de documento, limpa a seleção de páginas
      if (lastRenderedDossieMd5 !== doc.md5) {
        selectedDossierPages.clear();
        lastRenderedDossieMd5 = doc.md5;
      }

      const isImg = isImageDoc(doc);
      const dossie = (Array.isArray(doc.dossie_paginas) && doc.dossie_paginas.length > 0)
        ? doc.dossie_paginas
        : [{ pagina: 1, tipo: doc.tipo_documento || 'Documento' }];

      const totalPages = Math.max(1, parseInt(doc.paginas) || dossie.length);

      // Atualiza limites dos inputs de intervalo
      const rangeFrom = document.getElementById('dossierRangeFrom');
      const rangeTo = document.getElementById('dossierRangeTo');
      if (rangeFrom) rangeFrom.max = totalPages;
      if (rangeTo) {
        rangeTo.max = totalPages;
        if (!rangeTo.value) rangeTo.placeholder = totalPages;
      }

      if (countBadge) {
        countBadge.innerText = `${totalPages} ${totalPages > 1 ? 'páginas' : 'página'}`;
      }
      if (tabBadge) {
        tabBadge.innerText = `${totalPages}p`;
        tabBadge.classList.remove('hidden');
      }

      // Atalhos rápidos no cabeçalho do dossiê
      dossie.forEach(item => {
        if (pillsEl && item.pagina) {
          const pill = document.createElement('button');
          pill.type = 'button';
          pill.id = `dossiePillPage_${item.pagina}`;
          const isPillActive = (currentDossieActivePage === item.pagina);
          pill.className = isPillActive
            ? 'px-2 py-0.5 rounded bg-emerald-600 text-white font-semibold border border-emerald-500 text-[10px] flex items-center gap-1 transition shadow-sm cursor-pointer'
            : 'px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-cyan-300 border border-slate-700/80 text-[10px] flex items-center gap-1 transition cursor-pointer';
          pill.title = `Ir para página ${item.pagina} (${item.tipo || 'Página'})`;
          pill.innerHTML = `<span class="font-mono ${isPillActive ? 'text-white' : 'text-cyan-400'} font-semibold">P.${item.pagina}</span> <span class="truncate max-w-[120px]">${escapeHtml(item.tipo || '')}</span>`;
          pill.onclick = () => jumpToPdfPage(item.pagina);
          pillsEl.appendChild(pill);
        }
      });

      // Mapeamento das páginas para seus respectivos tipos
      const pageTypeMap = {};
      dossie.forEach(d => {
        if (d.pagina) pageTypeMap[d.pagina] = d.tipo;
      });

      for (let pNum = 1; pNum <= totalPages; pNum++) {
        const pageType = pageTypeMap[pNum] || (pNum === 1 ? (doc.tipo_documento || 'Página Inicial') : `Página ${pNum}`);
        const card = document.createElement('div');
        card.id = `dossieCardPage_${pNum}`;
        const isCardActive = (currentDossieActivePage === pNum);
        const isSelected = selectedDossierPages.has(pNum);

        let cardBorderClass = 'border-slate-800 hover:border-indigo-500/50';
        if (isSelected) {
          cardBorderClass = 'ring-2 ring-indigo-500 border-indigo-500/80 bg-indigo-950/20';
        } else if (isCardActive) {
          cardBorderClass = 'ring-2 ring-emerald-500 border-emerald-500 bg-slate-800/90';
        }

        card.className = `bg-slate-900/90 border ${cardBorderClass} rounded-xl p-2.5 flex flex-col gap-2 transition-all hover:shadow-lg group relative`;

        const thumbUrl = isImg ? `/api/arquivo/${doc.md5}` : `/api/thumbnail/${doc.md5}/${pNum}?w=720`;

        card.innerHTML = `
          <div class="flex items-center justify-between text-[11px] pb-1.5 border-b border-slate-800/80 gap-1.5 select-none">
            <label class="flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" class="dossier-page-cb rounded border-slate-700 bg-slate-950 text-indigo-500 focus:ring-indigo-500 h-3.5 w-3.5 cursor-pointer"
                     data-page="${pNum}" ${isSelected ? 'checked' : ''}
                     onchange="toggleDossierPageSelection(${pNum}, this.checked)">
              <span class="font-mono font-bold text-cyan-400 flex items-center gap-1 text-[11px] cursor-pointer">
                <i class="fa-regular fa-file-lines text-[10px]"></i> Pág. ${pNum}
              </span>
            </label>
            <button type="button" onclick="openDossierClassifyModalSingle(${pNum})"
                    class="text-[10px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-indigo-300 border border-slate-700/90 truncate max-w-[130px] flex items-center gap-1 transition shadow-sm cursor-pointer"
                    title="Clique para alterar o tipo de documento desta página">
              <span class="truncate font-medium">${escapeHtml(pageType)}</span>
              <i class="fa-solid fa-pen text-[8px] text-slate-400 group-hover:text-indigo-400 shrink-0"></i>
            </button>
          </div>
          <div class="relative aspect-[3/4] bg-slate-950 rounded-lg overflow-hidden border border-slate-800/80 cursor-pointer" onclick="openDossiePageLightbox(${pNum})" title="Clique para Visualizar em Alta Resolução (Página ${pNum})">
            <img src="${thumbUrl}" loading="lazy" alt="Página ${pNum}" class="w-full h-full object-cover object-top transition-transform duration-200 group-hover:scale-105"
                 onerror="this.style.display='none'; this.nextElementSibling.classList.remove('hidden');">
            <div class="hidden w-full h-full flex flex-col items-center justify-center text-slate-600 bg-slate-950 p-2 text-center">
              <i class="fa-regular fa-file-pdf text-2xl text-slate-700 mb-1"></i>
              <span class="text-[10px]">Página ${pNum}</span>
            </div>
            <div class="absolute inset-0 bg-emerald-500/15 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
              <span class="bg-slate-900/90 text-emerald-400 text-[10px] font-semibold px-2.5 py-1.5 rounded shadow-lg border border-emerald-500/40 flex items-center gap-1.5 backdrop-blur-sm">
                <i class="fa-solid fa-magnifying-glass-plus text-[10px]"></i> Visualizar Ampliado
              </span>
            </div>
          </div>
          <button type="button" id="dossieBtnPage_${pNum}" onclick="jumpToPdfPage(${pNum})"
                  class="w-full py-1.5 px-2 ${isCardActive ? 'bg-emerald-600 text-white font-semibold shadow' : 'bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-emerald-300'} rounded text-[10px] font-medium transition flex items-center justify-center gap-1.5 cursor-pointer">
            <i class="fa-solid ${isCardActive ? 'fa-circle-check text-emerald-200' : 'fa-eye text-slate-400'} text-[9px]"></i>
            <span>${isCardActive ? 'Exibindo no Leitor' : 'Exibir no Leitor'}</span>
          </button>
        `;
        gridEl.appendChild(card);
      }

      updateDossierBatchUI(totalPages);
    }

    // Manipuladores de Seleção de Páginas no Dossiê (Simples, Direto, Sem Teclas Modificadoras)
    function toggleDossierPageSelection(pNum, isChecked) {
      if (isChecked) {
        selectedDossierPages.add(pNum);
      } else {
        selectedDossierPages.delete(pNum);
      }
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      const totalPages = Math.max(1, parseInt(doc.paginas) || (Array.isArray(doc.dossie_paginas) ? doc.dossie_paginas.length : 1));
      updateDossierBatchUI(totalPages);
      syncDossierCardSelection(pNum);
    }

    function syncDossierCardSelection(pNum) {
      const card = document.getElementById(`dossieCardPage_${pNum}`);
      if (!card) return;
      const cb = card.querySelector('.dossier-page-cb');
      const isSel = selectedDossierPages.has(pNum);
      if (cb && cb.checked !== isSel) cb.checked = isSel;
      const isCardActive = (currentDossieActivePage === pNum);
      if (isSel) {
        card.className = 'bg-slate-900/90 border ring-2 ring-indigo-500 border-indigo-500/80 bg-indigo-950/20 rounded-xl p-2.5 flex flex-col gap-2 transition-all hover:shadow-lg group relative';
      } else if (isCardActive) {
        card.className = 'bg-slate-900/90 border ring-2 ring-emerald-500 border-emerald-500 bg-slate-800/90 rounded-xl p-2.5 flex flex-col gap-2 transition-all hover:shadow-lg group relative';
      } else {
        card.className = 'bg-slate-900/90 border border-slate-800 hover:border-indigo-500/50 rounded-xl p-2.5 flex flex-col gap-2 transition-all hover:shadow-lg group relative';
      }
    }

    function syncAllDossierCardsSelection(totalPages) {
      for (let p = 1; p <= totalPages; p++) {
        syncDossierCardSelection(p);
      }
    }

    function toggleSelectAllDossierPages(isChecked) {
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      const totalPages = Math.max(1, parseInt(doc.paginas) || (Array.isArray(doc.dossie_paginas) ? doc.dossie_paginas.length : 1));

      if (isChecked) {
        for (let p = 1; p <= totalPages; p++) {
          selectedDossierPages.add(p);
        }
      } else {
        selectedDossierPages.clear();
      }

      updateDossierBatchUI(totalPages);
      syncAllDossierCardsSelection(totalPages);
    }

    function selectDossierPageRange() {
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      const totalPages = Math.max(1, parseInt(doc.paginas) || (Array.isArray(doc.dossie_paginas) ? doc.dossie_paginas.length : 1));

      const fromInput = document.getElementById('dossierRangeFrom');
      const toInput = document.getElementById('dossierRangeTo');
      const fromVal = parseInt(fromInput?.value);
      const toVal = parseInt(toInput?.value);

      if (isNaN(fromVal) || isNaN(toVal)) {
        showToast('Informe os números inicial e final do intervalo.', 'info');
        return;
      }

      const start = Math.max(1, Math.min(fromVal, toVal));
      const end = Math.min(totalPages, Math.max(fromVal, toVal));

      for (let p = start; p <= end; p++) {
        selectedDossierPages.add(p);
      }

      updateDossierBatchUI(totalPages);
      syncAllDossierCardsSelection(totalPages);
      showToast(`Páginas de ${start} a ${end} marcadas (${selectedDossierPages.size} no total).`, 'info');
    }

    function updateDossierBatchUI(totalPages) {
      const countEl = document.getElementById('dossierSelectedCount');
      const btnClassify = document.getElementById('btnDossierBatchClassify');
      const badgeEl = document.getElementById('dossierBatchBtnBadge');
      const selectAllCb = document.getElementById('dossierSelectAllPages');

      const count = selectedDossierPages.size;
      if (countEl) countEl.innerText = count;

      if (btnClassify) {
        if (count > 0) {
          btnClassify.disabled = false;
          btnClassify.className = 'px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow-sm cursor-pointer';
        } else {
          btnClassify.disabled = true;
          btnClassify.className = 'px-3 py-1 bg-slate-800/80 text-slate-500 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition border border-slate-700/50 disabled:cursor-not-allowed cursor-pointer';
        }
      }

      if (badgeEl) {
        if (count > 0) {
          badgeEl.classList.remove('hidden');
          badgeEl.innerText = count;
        } else {
          badgeEl.classList.add('hidden');
        }
      }

      if (selectAllCb) {
        if (count === 0) {
          selectAllCb.checked = false;
          selectAllCb.indeterminate = false;
        } else if (totalPages > 0 && count >= totalPages) {
          selectAllCb.checked = true;
          selectAllCb.indeterminate = false;
        } else {
          selectAllCb.checked = false;
          selectAllCb.indeterminate = true;
        }
      }
    }

    function formatDossierPageNumbers(arr) {
      if (!arr || arr.length === 0) return 'nenhuma';
      const sorted = [...arr].sort((a, b) => a - b);
      if (sorted.length <= 3) {
        return sorted.map(p => `Pág. ${p}`).join(', ');
      }
      let isContiguous = true;
      for (let i = 1; i < sorted.length; i++) {
        if (sorted[i] !== sorted[i - 1] + 1) {
          isContiguous = false;
          break;
        }
      }
      if (isContiguous) {
        return `Páginas ${sorted[0]} a ${sorted[sorted.length - 1]}`;
      }
      return `Páginas ${sorted.slice(0, 3).join(', ')} e mais ${sorted.length - 3}`;
    }

    // Abertura e Controle da Modal de Reclassificação (Individual e em Massa)
    function openDossierClassifyModalSingle(pNum) {
      targetDossierClassifyPages = [pNum];
      setupAndOpenDossierClassifyModal();
    }

    function openDossierBatchClassifyModal() {
      if (selectedDossierPages.size === 0) {
        showToast('Selecione ao menos uma página para classificar.', 'info');
        return;
      }
      targetDossierClassifyPages = Array.from(selectedDossierPages).sort((a, b) => a - b);
      setupAndOpenDossierClassifyModal();
    }

    function setupAndOpenDossierClassifyModal() {
      const modal = document.getElementById('modalDossierClassifyPages');
      const listEl = document.getElementById('dossierClassifyPagesList');
      const badgeEl = document.getElementById('dossierClassifyPagesBadge');
      const searchInput = document.getElementById('dossierClassifySearchInput');
      if (!modal) return;

      const count = targetDossierClassifyPages.length;
      if (listEl) listEl.innerText = formatDossierPageNumbers(targetDossierClassifyPages);
      if (badgeEl) badgeEl.innerText = `${count} ${count > 1 ? 'págs' : 'pág'}`;
      if (searchInput) searchInput.value = '';

      renderDossierClassifyTypeList('');
      modal.classList.remove('hidden');
      setTimeout(() => searchInput?.focus(), 50);
    }

    function closeDossierClassifyModal() {
      const modal = document.getElementById('modalDossierClassifyPages');
      if (modal) modal.classList.add('hidden');
    }

    function filterDossierClassifyTypes(query) {
      renderDossierClassifyTypeList(query);
    }

    function applyCustomDossierClassifyType() {
      const searchInput = document.getElementById('dossierClassifySearchInput');
      const val = searchInput ? searchInput.value.trim() : '';
      if (val) {
        applyDossierClassifyType(val);
      } else {
        showToast('Digite ou selecione um tipo de documento.', 'info');
      }
    }

    function renderDossierClassifyTypeList(query = '') {
      const container = document.getElementById('dossierClassifyTypeList');
      if (!container) return;
      container.innerHTML = '';
      const q = (query || '').toLowerCase().trim();

      const typesMap = new Map();
      KNOWN_DOSSIER_TYPES.forEach(item => typesMap.set(item.name.toLowerCase(), item));

      const selectTipo = document.getElementById('select_tipo_documento');
      if (selectTipo) {
        Array.from(selectTipo.options).forEach(opt => {
          const name = opt.value;
          if (name && !typesMap.has(name.toLowerCase())) {
            typesMap.set(name.toLowerCase(), {
              name: name,
              category: opt.parentElement?.label || 'Geral',
              icon: 'fa-solid fa-file'
            });
          }
        });
      }

      const allItems = Array.from(typesMap.values());
      const filtered = q
        ? allItems.filter(item => item.name.toLowerCase().includes(q) || item.category.toLowerCase().includes(q))
        : allItems;

      if (filtered.length === 0) {
        container.innerHTML = `
          <div class="text-center py-4 text-slate-400 text-xs">
            <p>Nenhum tipo pré-cadastrado encontrado para "<strong>${escapeHtml(query)}</strong>".</p>
            <button type="button" onclick="applyDossierClassifyType('${escapeHtmlAttr(query)}')" class="mt-2 px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold cursor-pointer">
              Usar "${escapeHtml(query)}"
            </button>
          </div>
        `;
        return;
      }

      const groups = {};
      filtered.forEach(item => {
        if (!groups[item.category]) groups[item.category] = [];
        groups[item.category].push(item);
      });

      Object.entries(groups).forEach(([cat, items]) => {
        const groupDiv = document.createElement('div');
        groupDiv.className = 'space-y-1 mb-2';
        groupDiv.innerHTML = `<div class="text-[10px] font-semibold text-slate-500 uppercase px-1 pt-1 tracking-wider">${escapeHtml(cat)}</div>`;

        const grid = document.createElement('div');
        grid.className = 'grid grid-cols-1 sm:grid-cols-2 gap-1';

        items.forEach(item => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'w-full text-left px-2.5 py-1.5 rounded-lg bg-slate-900/80 hover:bg-indigo-600 hover:text-white text-slate-200 border border-slate-800/80 text-xs flex items-center justify-between group transition shadow-sm cursor-pointer';
          btn.innerHTML = `
            <span class="flex items-center gap-2 truncate">
              <i class="${item.icon} text-[11px] text-indigo-400 group-hover:text-white transition"></i>
              <span class="truncate font-medium">${escapeHtml(item.name)}</span>
            </span>
            <i class="fa-solid fa-chevron-right text-[9px] text-slate-600 group-hover:text-indigo-200 opacity-0 group-hover:opacity-100 transition"></i>
          `;
          btn.onclick = () => applyDossierClassifyType(item.name);
          grid.appendChild(btn);
        });

        groupDiv.appendChild(grid);
        container.appendChild(groupDiv);
      });
    }

    function applyDossierClassifyType(chosenType) {
      const cleanType = (chosenType || '').trim();
      if (!cleanType) {
        showToast('Informe ou selecione um tipo de documento válido.', 'error');
        return;
      }
      if (!targetDossierClassifyPages || targetDossierClassifyPages.length === 0) {
        showToast('Nenhuma página alvo selecionada.', 'error');
        closeDossierClassifyModal();
        return;
      }
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      const totalPages = Math.max(1, parseInt(doc.paginas) || (Array.isArray(doc.dossie_paginas) ? doc.dossie_paginas.length : 1));

      // Garante inicialização correta de dossie_paginas
      if (!Array.isArray(doc.dossie_paginas) || doc.dossie_paginas.length === 0) {
        doc.dossie_paginas = [];
        for (let i = 1; i <= totalPages; i++) {
          doc.dossie_paginas.push({
            pagina: i,
            tipo: (i === 1 ? (doc.tipo_documento || 'Página Inicial') : `Página ${i}`)
          });
        }
      }

      // Atualiza as páginas alvo
      targetDossierClassifyPages.forEach(pNum => {
        let pItem = doc.dossie_paginas.find(x => x.pagina === pNum);
        if (!pItem) {
          pItem = { pagina: pNum, tipo: cleanType };
          doc.dossie_paginas.push(pItem);
        } else {
          pItem.tipo = cleanType;
        }

        // Se a página 1 foi alterada, reflete no tipo_documento principal
        if (pNum === 1) {
          doc.tipo_documento = cleanType;
          const selectTipo = document.getElementById('select_tipo_documento');
          if (selectTipo) selectTipo.value = cleanType;
        }
      });

      // Ordena dossie_paginas numericamente
      doc.dossie_paginas.sort((a, b) => a.pagina - b.pagina);

      // Recalcula todos_tipos
      const tiposSet = new Set();
      if (doc.tipo_documento) tiposSet.add(doc.tipo_documento);
      doc.dossie_paginas.forEach(p => {
        if (p.tipo && p.tipo.trim() && !p.tipo.startsWith('Página ')) {
          tiposSet.add(p.tipo.trim());
        }
      });
      doc.todos_tipos = Array.from(tiposSet);

      // Recalcula todos_dominios automaticamente sem exigir que o usuário informe domínio
      recalculateDocDomains(doc);

      // Atualiza no repositório de documentos
      const mainIdx = documents.findIndex(d => d.md5 === doc.md5);
      if (mainIdx !== -1) documents[mainIdx] = doc;
      filteredDocs[currentIndex] = doc;

      // Marca formulário como modificado
      markDirty();

      // Atualiza UI
      renderDossierPagesGrid(doc);
      renderMultiTags(doc);
      if (typeof initMasterFilterLists === 'function') initMasterFilterLists();
      if (typeof updateFacetFilters === 'function') updateFacetFilters();

      const countAff = targetDossierClassifyPages.length;
      showToast(`${countAff} ${countAff > 1 ? 'páginas reclassificadas' : 'página reclassificada'} como "${cleanType}"!`, 'success');

      // Limpa seleções e fecha modal
      selectedDossierPages.clear();
      targetDossierClassifyPages = [];
      closeDossierClassifyModal();
    }

    async function loadDocumentText(md5, force = false) {
      if (!md5) return;
      const contentEl = document.getElementById('docTextContent');
      const loadingEl = document.getElementById('docTextLoading');
      const badgeEl = document.getElementById('textDocOriginBadge');

      if (!force && docTextCache[md5]) {
        currentDocRawText = docTextCache[md5].texto || '';
        if (badgeEl) badgeEl.innerText = docTextCache[md5].origem || 'cache';
        renderDocText(currentDocRawText);
        return;
      }

      if (loadingEl) loadingEl.classList.remove('hidden');
      try {
        const res = await fetch(`/api/texto/${md5}`);
        const data = await res.json();
        if (data.status === 'sucesso' && data.texto) {
          docTextCache[md5] = data;
          currentDocRawText = data.texto;
          if (badgeEl) badgeEl.innerText = data.origem || 'extraído';
          renderDocText(currentDocRawText);
        } else if (data.status === 'aviso' && data.texto) {
          currentDocRawText = data.texto;
          if (badgeEl) badgeEl.innerText = data.origem || 'sem texto digital';
          renderDocText(currentDocRawText);
        } else {
          currentDocRawText = data.mensagem || 'Texto não disponível.';
          if (badgeEl) badgeEl.innerText = 'indisponível';
          renderDocText(currentDocRawText);
        }
      } catch (err) {
        console.error('Erro ao obter texto do documento:', err);
        currentDocRawText = 'Erro ao carregar texto: ' + err.message;
        if (badgeEl) badgeEl.innerText = 'erro';
        renderDocText(currentDocRawText);
      } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
      }
    }

    function renderDocText(textToRender, highlightTerm = '') {
      const contentEl = document.getElementById('docTextContent');
      if (!contentEl) return;
      if (!textToRender) {
        contentEl.innerHTML = '<span class="text-slate-500 italic">Nenhum texto extraído para este documento.</span>';
        return;
      }

      if (textToRender.includes("sem camada de texto nativa detectada")) {
        contentEl.innerHTML = `
          <div class="p-6 text-center space-y-3 bg-slate-900/60 rounded-xl border border-slate-800 my-4 shadow-sm">
            <div class="w-12 h-12 mx-auto rounded-full bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 text-xl">
              <i class="fa-solid fa-file-lines"></i>
            </div>
            <div class="text-xs font-semibold text-slate-200">Documento Digitalizado / Sem Camada de Texto Digital</div>
            <div class="text-[11px] text-slate-400 max-w-md mx-auto leading-relaxed">
              Este arquivo não possui texto digital embutido. Acione o botão <strong class="text-purple-300">"Ler e Classificar (OCR)"</strong> para executar a leitura visual integral e transcrição via IA.
            </div>
            <div class="pt-2">
              <button type="button" onclick="triggerProcessarDocumento()" class="px-3.5 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-medium inline-flex items-center gap-1.5 transition shadow-sm">
                <i class="fa-solid fa-wand-magic-sparkles text-amber-300"></i>
                <span>Ler e Classificar com OCR Agora</span>
              </button>
            </div>
          </div>
        `;
        return;
      }

      const cleanTerm = (highlightTerm || '').trim();
      if (!cleanTerm) {
        contentEl.innerText = textToRender;
        return;
      }

      const escaped = textToRender
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

      try {
        const escapedTerm = cleanTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${escapedTerm})`, 'gi');
        const highlighted = escaped.replace(regex, '<mark class="bg-amber-400 text-slate-950 font-bold px-0.5 rounded">$1</mark>');
        contentEl.innerHTML = highlighted;
      } catch (e) {
        contentEl.innerText = textToRender;
      }
    }

    function onSearchDocTextInput(query) {
      const container = document.getElementById('textSearchCountContainer');
      const countEl = document.getElementById('textSearchMatchCount');
      const clean = (query || '').trim();

      if (!clean) {
        if (container) container.classList.add('hidden');
        renderDocText(currentDocRawText);
        return;
      }

      try {
        const escapedTerm = clean.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(escapedTerm, 'gi');
        const matches = (currentDocRawText.match(regex) || []).length;
        if (container && countEl) {
          container.classList.remove('hidden');
          countEl.innerText = `${matches} ocorrência${matches === 1 ? '' : 's'}`;
        }
        renderDocText(currentDocRawText, clean);
      } catch (e) {
        if (container) container.classList.add('hidden');
        renderDocText(currentDocRawText);
      }
    }

    function clearDocTextSearch() {
      const input = document.getElementById('searchDocTextInput');
      if (input) input.value = '';
      onSearchDocTextInput('');
    }

    function copyDocumentRawText() {
      if (!currentDocRawText) {
        showToast('Nenhum texto disponível para copiar.', 'info');
        return;
      }
      navigator.clipboard.writeText(currentDocRawText).then(() => {
        showToast('Texto integral copiado para a área de transferência!', 'success');
      }).catch(() => {
        showToast('Não foi possível copiar o texto.', 'error');
      });
    }

    function updateFichaTecnica(doc) {
      if (!doc) return;
      const setEl = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = safeString(val) || '-';
      };

      setEl('audit_md5', doc.md5);
      setEl('audit_nome_arquivo', doc.nome_arquivo || `${doc.md5}.${doc.extensao || 'pdf'}`);
      const fNameEl = document.getElementById('audit_nome_arquivo');
      if (fNameEl) fNameEl.title = doc.nome_arquivo || '';

      const bytes = parseInt(doc.tamanho_bytes) || 0;
      let sizeStr = '-';
      if (bytes > 0) {
        sizeStr = bytes > 1048576 
          ? `${(bytes / 1048576).toFixed(2)} MB (${bytes.toLocaleString()} bytes)`
          : `${(bytes / 1024).toFixed(1)} KB (${bytes.toLocaleString()} bytes)`;
      }
      setEl('audit_tamanho', sizeStr);
      setEl('audit_caminho', doc.caminho_relativo || '-');
      const auditMetodoEl = document.getElementById('audit_metodo_leitura');
      if (auditMetodoEl) {
        if (doc.metodo_leitura === 'hibrido_fallback_openai') {
          auditMetodoEl.innerHTML = '<span class="text-amber-300 font-semibold inline-flex items-center gap-1"><i class="fa-solid fa-bolt text-amber-400"></i> Híbrido (Ollama ➔ Nuvem)</span>';
        } else {
          auditMetodoEl.innerText = doc.metodo_leitura || (doc.status === 'nao_processado' ? 'não processado' : 'texto_digital');
        }
      }
      setEl('audit_tentativa_ocr', doc.tentativa_ocr_llm ? 'Sim (Executado)' : 'Não');
      setEl('audit_data_modificacao', doc.data_modificacao || '-');
      setEl('audit_autor', doc.autor || '-');
      const auditAutEl = document.getElementById('audit_autor');
      if (auditAutEl) auditAutEl.title = doc.autor || '-';

      // Metadados Dublin Core & XMP
      let dc = doc.dublin_core;
      if (typeof dc === 'string') {
        try { dc = JSON.parse(dc); } catch (e) { dc = null; }
      }
      dc = (dc && typeof dc === 'object') ? dc : {};

      const dcTitleVal = dc.title || doc.dc_title || '';
      const dcCreatorVal = dc.creator || doc.autor || '';
      const dcSubjectVal = dc.subject || doc.dc_subject || '';
      const dcKeywordsVal = dc.keywords || '';
      const dcToolVal = dc.creator_tool || doc.dc_creator_tool || '';
      const dcProducerVal = dc.producer || '';
      const dcDateVal = dc.date || '';
      const dcModifiedVal = dc.modified || '';
      const dcFormatVal = dc.format || '';
      const dcDescVal = dc.description || '';

      setEl('dc_title', dcTitleVal || '-');
      setEl('dc_creator', dcCreatorVal || '-');
      setEl('dc_subject', dcSubjectVal || '-');
      setEl('dc_keywords', dcKeywordsVal || '-');
      setEl('dc_creator_tool', dcToolVal || '-');
      setEl('dc_producer', dcProducerVal || '-');
      setEl('dc_date', dcDateVal || '-');
      setEl('dc_modified', dcModifiedVal || '-');
      setEl('dc_format', dcFormatVal || '-');
      setEl('dc_description', dcDescVal || '-');

      const titleEl = document.getElementById('dc_title');
      if (titleEl) titleEl.title = dcTitleVal || '-';
      const creatorEl = document.getElementById('dc_creator');
      if (creatorEl) creatorEl.title = dcCreatorVal || '-';
      const subjEl = document.getElementById('dc_subject');
      if (subjEl) subjEl.title = dcSubjectVal || '-';
      const kwEl = document.getElementById('dc_keywords');
      if (kwEl) kwEl.title = dcKeywordsVal || '-';
      const toolEl = document.getElementById('dc_creator_tool');
      if (toolEl) toolEl.title = dcToolVal || '-';
      const prodEl = document.getElementById('dc_producer');
      if (prodEl) prodEl.title = dcProducerVal || '-';

      const hasDc = Boolean(
        dcTitleVal || dcCreatorVal || dcSubjectVal || dcKeywordsVal ||
        dcToolVal || dcProducerVal || dcDateVal || dcModifiedVal || dcFormatVal || dcDescVal
      );
      const dcGrid = document.getElementById('dcGridContainer');
      const dcNotice = document.getElementById('dcEmptyNotice');
      if (dcGrid) dcGrid.classList.toggle('hidden', !hasDc);
      if (dcNotice) dcNotice.classList.toggle('hidden', hasDc);

      const statusEl = document.getElementById('audit_status_conferencia');
      if (statusEl) {
        const st = safeString(doc.status_conferencia || 'pendente').toLowerCase();
        if (st === 'aprovado') {
          statusEl.className = 'text-emerald-400 font-semibold';
          statusEl.innerText = 'Aprovado / Conferido';
        } else {
          statusEl.className = 'text-amber-400 font-semibold';
          statusEl.innerText = 'Pendente';
        }
      }

      const typeBadge = document.getElementById('auditFileTypeBadge');
      if (typeBadge) {
        const fmt = getDocFormatMeta(doc);
        typeBadge.innerText = fmt.label;
        typeBadge.className = `text-[10px] font-mono px-2 py-0.5 rounded border ${fmt.badgeClass || 'bg-slate-800 text-slate-300 border-slate-700'}`;
      }

      // Integridade, Origem & Assinaturas
      const ehNativo = doc.eh_nativo_digital === 1 || doc.eh_nativo_digital === true;
      const ehDigitalizado = doc.eh_nativo_digital === 0 || doc.eh_nativo_digital === false;
      const camadaEl = document.getElementById('audit_camada_texto');
      if (camadaEl) {
        if (ehNativo) {
          camadaEl.innerHTML = '<span class="text-emerald-400 font-semibold inline-flex items-center gap-1"><i class="fa-solid fa-file-lines"></i> Nativo Digital (Vetor)</span>';
        } else if (ehDigitalizado && doc.metodo_leitura && doc.metodo_leitura.includes('ocr')) {
          camadaEl.innerHTML = '<span class="text-amber-400 font-semibold inline-flex items-center gap-1"><i class="fa-solid fa-camera"></i> Digitalizado (OCR)</span>';
        } else if (ehDigitalizado) {
          camadaEl.innerHTML = '<span class="text-slate-300 inline-flex items-center gap-1"><i class="fa-regular fa-file"></i> Documento / Imagem</span>';
        } else {
          camadaEl.innerHTML = '<span class="text-slate-500 italic">Pendente de inspeção</span>';
        }
      }

      const assinado = doc.tem_assinatura_digital === 1 || doc.tem_assinatura_digital === true;
      const assEl = document.getElementById('audit_assinatura_status');
      if (assEl) {
        if (assinado) {
          assEl.innerHTML = '<span class="text-emerald-400 font-bold inline-flex items-center gap-1"><i class="fa-solid fa-certificate text-emerald-400"></i> PAdES / ICP-Brasil</span>';
        } else if (doc.tem_assinatura_digital === 0 || doc.tem_assinatura_digital === false) {
          assEl.innerHTML = '<span class="text-slate-400">Sem assinatura digital</span>';
        } else {
          assEl.innerHTML = '<span class="text-slate-500 italic">Não inspecionado</span>';
        }
      }

      setEl('audit_dossie_id', doc.dossie_id || 'Não vinculado');
      const dupEl = document.getElementById('audit_duplicata_status');
      if (dupEl) {
        if (doc.duplicata_de) {
          dupEl.innerHTML = `<span class="text-amber-400 font-semibold" title="Duplicata de ${escapeHtml(doc.duplicata_de)}">Duplicata (${Math.round((doc.similaridade_duplicata || 1) * 100)}%)</span>`;
        } else {
          dupEl.innerText = 'Documento Único';
          dupEl.className = 'font-mono text-slate-300 block truncate';
        }
      }
      setEl('audit_caminho_organizado', doc.caminho_organizado || 'Não organizado fisicamente');

      // Lista de assinaturas
      renderAuditSignatures(doc.info_assinaturas_json);
    }

    function renderAuditSignatures(info) {
      const container = document.getElementById('auditSignaturesDetailContainer');
      const listEl = document.getElementById('auditSignaturesList');
      if (!container || !listEl) return;

      let sigs = info;
      if (typeof sigs === 'string') {
        try { sigs = JSON.parse(sigs); } catch (e) { sigs = null; }
      }

      // Suporte a objeto do inspect_pdf
      if (sigs && typeof sigs === 'object' && !Array.isArray(sigs)) {
        const sigsList = sigs.signatarios || [];
        const authsList = sigs.autoridades || [];
        if (!sigs.tem_assinatura && sigsList.length === 0 && authsList.length === 0) {
          container.classList.add('hidden');
          listEl.innerHTML = '';
          return;
        }

        container.classList.remove('hidden');
        listEl.innerHTML = `
          <div class="bg-slate-950/80 p-2 rounded border border-slate-800 text-[11px] space-y-1">
            <div class="flex items-center justify-between">
              <span class="font-semibold text-emerald-400 flex items-center gap-1">
                <i class="fa-solid fa-check-circle text-[10px]"></i> ${escapeHtml(sigsList.join(', ') || 'Assinatura PAdES Detectada')}
              </span>
              <span class="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                ${escapeHtml(sigs.tipo_assinatura || 'PAdES / ICP-Brasil')}
              </span>
            </div>
            ${authsList.length > 0 ? `<div class="text-[10px] text-slate-400"><span class="text-slate-500">Autoridade:</span> ${escapeHtml(authsList.join(', '))}</div>` : ''}
            ${sigs.data_assinatura ? `<div class="text-[10px] text-slate-400"><i class="fa-regular fa-clock"></i> ${escapeHtml(sigs.data_assinatura)}</div>` : ''}
          </div>
        `;
        return;
      }

      if (!Array.isArray(sigs) || sigs.length === 0) {
        container.classList.add('hidden');
        listEl.innerHTML = '';
        return;
      }

      container.classList.remove('hidden');
      listEl.innerHTML = sigs.map(s => `
        <div class="bg-slate-950/80 p-2 rounded border border-slate-800 text-[11px] space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-semibold text-emerald-400 flex items-center gap-1">
              <i class="fa-solid fa-check-circle text-[10px]"></i> ${escapeHtml(s.assinado_por || s.campo || 'Assinatura PAdES')}
            </span>
            <span class="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
              ${escapeHtml(s.tipo || 'PAdES')}
            </span>
          </div>
          ${s.data ? `<div class="text-[10px] text-slate-400"><i class="fa-regular fa-clock"></i> ${escapeHtml(s.data)}</div>` : ''}
          ${s.motivo ? `<div class="text-[10px] text-slate-400 truncate"><span class="text-slate-500">Motivo:</span> ${escapeHtml(s.motivo)}</div>` : ''}
          ${s.local ? `<div class="text-[10px] text-slate-400 truncate"><span class="text-slate-500">Local:</span> ${escapeHtml(s.local)}</div>` : ''}
        </div>
      `).join('');
    }

    async function inspectCurrentDocument() {
      const curDoc = (filteredDocs && currentIndex >= 0 && currentIndex < filteredDocs.length) ? filteredDocs[currentIndex] : null;
      if (!curDoc) return showToast('Nenhum documento selecionado', 'warning');

      showToast('Inspecionando assinaturas e integridade...', 'info');
      try {
        const resp = await fetch(`/api/inspecionar/${curDoc.md5}`);
        const data = await resp.json();
        if (data.erro) {
          showToast('Aviso de inspeção: ' + data.erro, 'warning');
          return;
        }
        curDoc.eh_nativo_digital = data.eh_nativo_digital ? 1 : 0;
        curDoc.tem_assinatura_digital = data.tem_assinatura_digital ? 1 : 0;
        curDoc.info_assinaturas_json = data.info_assinaturas || data.assinaturas || {};

        updateFichaTecnica(curDoc);
        renderDynamicInspector(curDoc);

        if (data.tem_assinatura_digital) {
          showToast('Assinatura digital criptográfica identificada com sucesso!', 'success');
        } else {
          showToast('Inspeção concluída: documento sem assinaturas criptográficas.', 'info');
        }
      } catch (err) {
        showToast('Falha na comunicação com o servidor: ' + err.message, 'error');
      }
    }

    function copyDublinCoreJson() {
      const curDoc = (filteredDocs && currentIndex >= 0 && currentIndex < filteredDocs.length) ? filteredDocs[currentIndex] : null;
      if (!curDoc) {
        showToast('Nenhum documento selecionado.', 'info');
        return;
      }
      let dc = curDoc.dublin_core;
      if (typeof dc === 'string') {
        try { dc = JSON.parse(dc); } catch (e) { dc = null; }
      }
      if (!dc || typeof dc !== 'object' || Object.keys(dc).length === 0) {
        const fallback = {};
        if (curDoc.autor) fallback.creator = curDoc.autor;
        if (curDoc.dc_title) fallback.title = curDoc.dc_title;
        if (curDoc.dc_subject) fallback.subject = curDoc.dc_subject;
        if (curDoc.dc_creator_tool) fallback.creator_tool = curDoc.dc_creator_tool;
        if (Object.keys(fallback).length > 0) dc = fallback;
      }
      if (!dc || Object.keys(dc).length === 0) {
        showToast('Nenhum metadado Dublin Core disponível para este documento.', 'info');
        return;
      }
      navigator.clipboard.writeText(JSON.stringify(dc, null, 2)).then(() => {
        showToast('Metadados Dublin Core copiados com sucesso!', 'success');
      }).catch(() => {
        showToast('Erro ao copiar metadados.', 'error');
      });
    }

    function copyJsonData() {
      const jsonViewer = document.getElementById('jsonViewer');
      if (!jsonViewer || !jsonViewer.innerText) {
        showToast('Nenhum dado JSON para copiar.', 'info');
        return;
      }
      navigator.clipboard.writeText(jsonViewer.innerText).then(() => {
        showToast('JSON copiado com sucesso!', 'success');
      }).catch(() => {
        showToast('Erro ao copiar JSON.', 'error');
      });
    }

    function copyMd5() {
      const md5 = document.getElementById('field_md5').innerText;
      navigator.clipboard.writeText(md5);
      showToast('Hash MD5 copiado!', 'info');
    }

    function copyFieldValue(elementId, label, btnEl) {
      const el = document.getElementById(elementId);
      if (!el) return;
      let val = '';
      if (el.tagName === 'SELECT') {
        val = el.value || '';
      } else {
        val = el.value || '';
      }
      val = val.trim();
      if (!val) {
        showToast(`O campo "${label}" está vazio neste documento.`, 'info');
        return;
      }

      const updateBtnVisual = () => {
        if (btnEl) {
          const origHtml = btnEl.innerHTML;
          btnEl.innerHTML = '<i class="fa-solid fa-check text-emerald-400"></i> Copiado';
          btnEl.classList.add('text-emerald-400');
          setTimeout(() => {
            btnEl.innerHTML = origHtml;
            btnEl.classList.remove('text-emerald-400');
          }, 1400);
        }
      };

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(val).then(() => {
          showToast(`"${label}" copiado!`, 'success');
          updateBtnVisual();
        }).catch(() => {
          copyTextFallback(val);
          showToast(`"${label}" copiado!`, 'success');
          updateBtnVisual();
        });
      } else {
        copyTextFallback(val);
        showToast(`"${label}" copiado!`, 'success');
        updateBtnVisual();
      }
    }

    async function copyAllExtractedData(btnEl) {
      if (!filteredDocs || filteredDocs.length === 0 || currentIndex < 0 || currentIndex >= filteredDocs.length) {
        showToast('Nenhum documento selecionado para cópia.', 'info');
        return;
      }

      const doc = filteredDocs[currentIndex] || {};
      const selectDom = document.getElementById('select_dominio');
      const dominio = (selectDom ? selectDom.value : (doc.dominio || 'outro')).toLowerCase();
      const tipoDoc = (document.getElementById('select_tipo_documento')?.value || doc.tipo_documento || '').trim();
      const tipoLower = tipoDoc.toLowerCase();

      // Verifica se o documento de fato contém chave ou transação PIX
      const hasPix = !!(
        document.querySelector('[data-dynamic-key="pix_chave"]')?.value?.trim() ||
        document.querySelector('[data-dynamic-key="pix_e2e_id"]')?.value?.trim() ||
        doc.dados_extras?.pix_chave ||
        doc.dados_extras?.pix_e2e_id
      );

      // Verifica se o documento é manuscrito ou preenchido à mão
      const isHandwrittenDoc = (
        doc.manuscrito === true ||
        doc.dados_extras?.manuscrito === true ||
        doc.dados_extras?.manuscrito === 'true' ||
        (Array.isArray(doc.todos_tipos) && doc.todos_tipos.some(t => {
          const tl = safeString(t).toLowerCase();
          return tl.includes('manuscrito') || tl.includes('mão') || tl.includes('mao') || tl.includes('punho');
        }))
      );

      let boxTitle = 'FICHA DE DADOS DO DOCUMENTO';
      let themeColor = '#1e40af'; // Azul padrão

      if (hasPix) {
        boxTitle = 'COMPROVANTE DE TRANSAÇÃO FINANCEIRA (PIX)';
        themeColor = '#059669'; // Esmeralda
      } else if (dominio === 'financeiro' || tipoLower.includes('pagamento') || tipoLower.includes('recibo') || tipoLower.includes('boleto') || tipoLower.includes('ted') || tipoLower.includes('doc')) {
        boxTitle = tipoDoc ? (isHandwrittenDoc && !tipoDoc.toLowerCase().includes('manuscrito') ? `${tipoDoc.toUpperCase()} (MANUSCRITO)` : tipoDoc.toUpperCase()) : 'COMPROVANTE DE OPERAÇÃO FINANCEIRA';
        themeColor = '#059669';
      } else if (tipoLower.includes('declaração') || tipoLower.includes('declaracao') || tipoLower.includes('punho')) {
        boxTitle = isHandwrittenDoc ? 'DECLARAÇÃO DE PRÓPRIO PUNHO / MANUSCRITA' : 'DECLARAÇÃO';
        themeColor = '#d97706';
      } else if (dominio === 'veiculo' || tipoLower.includes('crlv') || tipoLower.includes('veículo') || tipoLower.includes('veiculo') || tipoLower.includes('detran')) {
        boxTitle = 'DOCUMENTO VEICULAR / CRLV';
        themeColor = '#d97706'; // Âmbar escuro
      } else if (dominio === 'identificacao' || tipoLower.includes('rg') || tipoLower.includes('cpf') || tipoLower.includes('cnh') || tipoLower.includes('certidão') || tipoLower.includes('certidao')) {
        boxTitle = 'DOCUMENTO DE IDENTIFICAÇÃO CIVIL';
        themeColor = '#0284c7'; // Sky
      } else if (dominio === 'profissional' || tipoLower.includes('cadastral') || tipoLower.includes('cnpj')) {
        boxTitle = 'COMPROVANTE DE SITUAÇÃO CADASTRAL / PROFISSIONAL';
        themeColor = '#0d9488'; // Teal
      } else if (dominio === 'juridico' || tipoLower.includes('processo') || tipoLower.includes('petição') || tipoLower.includes('procuração')) {
        boxTitle = 'DOCUMENTO JURÍDICO / PROCESSUAL';
        themeColor = '#7c3aed'; // Roxo
      } else if (dominio === 'academico') {
        boxTitle = 'COMPROVAÇÃO DE QUALIFICAÇÃO / DOCUMENTO ACADÊMICO';
        themeColor = '#1e40af'; // Azul
      } else if (isHandwrittenDoc) {
        boxTitle = tipoDoc ? `${tipoDoc.toUpperCase()} (PREENCHIDO À MÃO)` : 'DOCUMENTO PREENCHIDO À MÃO / MANUSCRITO';
        themeColor = '#d97706';
      } else {
        boxTitle = tipoDoc ? tipoDoc.toUpperCase() : 'FICHA DE DADOS DO DOCUMENTO';
        themeColor = '#475569';
      }

      const items = [];
      const processedKeys = new Set();

      if (tipoDoc) {
        items.push({ label: 'Tipo de Documento', val: tipoDoc, highlight: false });
        processedKeys.add('tipo_documento');
      }

      if (isHandwrittenDoc) {
        items.push({ label: 'Preenchimento', val: 'Manuscrito / Preenchido à Mão com Caneta', highlight: true });
      }

      // Prioriza ler os inputs renderizados dinamicamente no formulário (reflete edições ativas)
      const dynamicInputs = document.querySelectorAll('[data-dynamic-key]');
      if (dynamicInputs && dynamicInputs.length > 0) {
        dynamicInputs.forEach(input => {
          const key = input.getAttribute('data-dynamic-key');
          const val = input.value.trim();
          if (!val || processedKeys.has(key) || key === 'manuscrito') return;
          processedKeys.add(key);

          const meta = getCanonicalFieldMeta(key);
          const isHighlight = meta.type === 'currency' || key === 'beneficiario' || key === 'razao_social' || key === 'curso' || key === 'placa' || key === 'emitente';
          const isMono = meta.type === 'mono' || key === 'cpf' || key === 'cnpj' || key === 'rg' || key.includes('id') || key.includes('codigo') || key.includes('autenticacao') || key.includes('chave');

          items.push({
            label: meta.label,
            val: val,
            highlight: isHighlight,
            mono: isMono
          });
        });
      } else {
        // Fallback: extrai diretamente do objeto doc caso o container DOM não esteja carregado
        const activeFields = extractActiveDocumentFields(doc);
        activeFields.forEach(f => {
          if (processedKeys.has(f.key) || f.key === 'manuscrito') return;
          processedKeys.add(f.key);

          const isHighlight = f.meta.type === 'currency' || f.key === 'beneficiario' || f.key === 'razao_social' || f.key === 'curso' || f.key === 'placa' || f.key === 'emitente';
          const isMono = f.meta.type === 'mono' || f.key === 'cpf' || f.key === 'cnpj' || f.key === 'rg' || f.key.includes('id') || f.key.includes('codigo') || f.key.includes('autenticacao') || f.key.includes('chave');

          items.push({
            label: f.meta.label,
            val: f.val,
            highlight: isHighlight,
            mono: isMono
          });
        });
      }

      const obs = (document.getElementById('input_obs')?.value || doc.observacoes || '').trim();
      if (obs) {
        items.push({ label: 'Observações / Notas', val: obs });
      }

      if (items.length === 0) {
        showToast('Nenhum dado extraído disponível para copiar.', 'info');
        return;
      }

      // --- 1. Formatação Visual Law para Rich Text (Word / Google Docs / LibreOffice) ---
      let htmlContent = `<div style="font-family: 'Segoe UI', Calibri, Arial, sans-serif; font-size: 11pt; color: #1e293b; background-color: #f8fafc; border-left: 4.5px solid ${themeColor}; border-top: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; border-radius: 4px; padding: 12px 18px; margin: 12px 0; max-width: 680px;">
  <div style="font-size: 11.5pt; font-weight: bold; color: ${themeColor}; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #cbd5e1; text-transform: uppercase; letter-spacing: 0.5px;">
    ${boxTitle}
  </div>
  <table style="width: 100%; border-collapse: collapse; font-size: 10.5pt; line-height: 1.55;">`;

      items.forEach(it => {
        const valStyle = it.highlight ? 'font-weight: 600; color: #0f172a;' : (it.mono ? 'font-family: Consolas, monospace; color: #0f172a;' : 'color: #1e293b;');
        htmlContent += `
    <tr>
      <td style="padding: 3px 12px 3px 0; font-weight: bold; color: #475569; width: 190px; vertical-align: top; white-space: nowrap;">${it.label}:</td>
      <td style="padding: 3px 0; vertical-align: top; ${valStyle}">${it.val}</td>
    </tr>`;
      });

      htmlContent += `
  </table>
</div>`;

      // --- 2. Formatação Visual Law para Plain Text (Notepad / WhatsApp / Petições em texto simples) ---
      const maxLabelLen = Math.max(...items.map(it => it.label.length));
      let plainContent = `${boxTitle}\n`;
      plainContent += '─'.repeat(60) + '\n';
      items.forEach(it => {
        const paddedLabel = it.label.padEnd(maxLabelLen, ' ');
        plainContent += `• ${paddedLabel} : ${it.val}\n`;
      });
      plainContent += '─'.repeat(60);

      const updateBtnVisual = () => {
        if (btnEl) {
          const origHtml = btnEl.innerHTML;
          btnEl.innerHTML = '<i class="fa-solid fa-check text-emerald-300"></i> <span>Copiado para o Word!</span>';
          setTimeout(() => { btnEl.innerHTML = origHtml; }, 2000);
        }
      };

      const copyRes = await copyRichAndPlainText(htmlContent, plainContent);
      if (copyRes.rich) {
        showToast('Ficha copiada em formato Visual Law para o Word!', 'success');
      } else {
        showToast('Ficha copiada em texto simples!', 'info');
      }
      updateBtnVisual();
    }

    async function copyRichAndPlainText(htmlContent, plainContent) {
      const fullHtml = `<!--StartFragment-->${htmlContent}<!--EndFragment-->`;

      // Estratégia 1: Clipboard API moderna (funciona quando em Secure Context: localhost ou HTTPS)
      if (window.isSecureContext && navigator.clipboard && window.ClipboardItem) {
        try {
          const blobText = new Blob([plainContent], { type: 'text/plain' });
          const blobHtml = new Blob([fullHtml], { type: 'text/html' });
          await navigator.clipboard.write([
            new ClipboardItem({
              'text/plain': blobText,
              'text/html': blobHtml
            })
          ]);
          return { success: true, rich: true };
        } catch (e) {
          console.warn('ClipboardItem moderno falhou, tentando fallback rico via evento copy:', e);
        }
      }

      // Estratégia 2: Fallback rico via evento síncrono 'copy'
      // Este método funciona em navegadores no Windows acessando via rede local (HTTP não-seguro como 192.168.x.x)
      try {
        let eventHandled = false;
        const copyHandler = (e) => {
          e.preventDefault();
          e.clipboardData.setData('text/html', fullHtml);
          e.clipboardData.setData('text/plain', plainContent);
          eventHandled = true;
        };
        document.addEventListener('copy', copyHandler);
        let execSuccess = false;
        try {
          execSuccess = document.execCommand('copy');
        } finally {
          document.removeEventListener('copy', copyHandler);
        }
        if (eventHandled && execSuccess) {
          return { success: true, rich: true };
        }
      } catch (e) {
        console.warn('Fallback de evento copy rico falhou:', e);
      }

      // Estratégia 3: Fallback via elemento HTML no DOM selecionado
      try {
        const container = document.createElement('div');
        container.innerHTML = fullHtml;
        container.style.position = 'fixed';
        container.style.left = '-9999px';
        container.style.top = '0';
        container.style.opacity = '0';
        document.body.appendChild(container);

        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(container);
        selection.removeAllRanges();
        selection.addRange(range);

        const execSuccess = document.execCommand('copy');
        selection.removeAllRanges();
        document.body.removeChild(container);

        if (execSuccess) {
          return { success: true, rich: true };
        }
      } catch (e) {
        console.warn('Fallback de seleção DOM falhou:', e);
      }

      // Estratégia 4: Fallback final para texto simples
      copyTextFallback(plainContent);
      return { success: true, rich: false };
    }

    function copyTextFallback(text) {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
      } catch (e) {
        console.error('Falha ao copiar:', e);
      }
      document.body.removeChild(ta);
    }


    // Exporta o arquivo JSON atualizado com a base de documentos
    function exportJSONFile(showNotification = false) {
      const allDocs = (documents || []).map(d => {
        const copy = { ...d };
        delete copy.data_criacao;
        return copy;
      });
      const jsonStr = JSON.stringify(allDocs, null, 2);
      const blob = new Blob([jsonStr], { type: 'application/json;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
      const downloadAnchor = document.createElement('a');
      downloadAnchor.href = url;
      downloadAnchor.download = `joakindex_revisado_${timestamp}.json`;
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      document.body.removeChild(downloadAnchor);
      URL.revokeObjectURL(url);
      if (showNotification) {
        showToast('Download do arquivo JSON concluído!', 'success');
      }
    }

    // Exporta uma planilha CSV COMPLETA com todas as informações extraídas do JSON
    function exportFullCSV(showNotification = true) {
      const allDocs = documents || [];
      if (allDocs.length === 0) {
        showToast('Nenhum documento disponível para exportação.', 'error');
        return;
      }

      // Colunas estruturadas para compatibilidade analítica e humana
      const columnDefs = [
        { key: 'beneficiario', header: 'Beneficiario' },
        { key: 'cpf', header: 'CPF' },
        { key: 'rg', header: 'RG' },
        { key: 'cnpj', header: 'CNPJ' },
        { key: 'faculdade', header: 'Instituicao_Ensino' },
        { key: 'curso', header: 'Curso' },
        { key: 'natureza_curso', header: 'Natureza_Curso' },
        { key: 'tipo_documento', header: 'Tipo_Documento' },
        { key: 'carga_horaria', header: 'Carga_Horaria' },
        { key: 'data', header: 'Data_Documento' },
        { key: 'status_conferencia', header: 'Status_Conferencia' },
        { key: 'revisado_em', header: 'Revisado_Em' },
        { key: 'observacoes_conferencia', header: 'Observacoes_Conferencia' },
        { key: 'status', header: 'Status_Processamento' },
        { key: 'metodo_leitura', header: 'Metodo_Leitura' },
        { key: 'tentativa_ocr_llm', header: 'Tentativa_OCR_LLM' },
        { key: 'erro', header: 'Mensagem_Erro' },
        { key: 'processado_em', header: 'Processado_Em' },
        { key: 'nome_arquivo', header: 'Nome_Arquivo_PDF' },
        { key: 'caminho_relativo', header: 'Caminho_Relativo' },
        { key: 'md5', header: 'MD5' },
        { key: 'data_modificacao', header: 'Data_Ultima_Alteracao_PDF' },
        { key: 'autor', header: 'dc_creator' },
        { key: 'dc_title', header: 'dc_title' },
        { key: 'dc_subject', header: 'dc_subject' },
        { key: 'dc_creator_tool', header: 'dc_creator_tool' }
      ];

      // Mapeia chaves extras dinamicamente para garantir que nenhum metadado adicional seja omitido
      const mappedKeys = new Set(columnDefs.map(c => c.key));
      const extraKeys = new Set();
      allDocs.forEach(doc => {
        if (doc && typeof doc === 'object') {
          Object.keys(doc).forEach(k => {
            if (k === 'data_criacao') return;
            if (!mappedKeys.has(k)) extraKeys.add(k);
          });
        }
      });
      extraKeys.forEach(k => {
        columnDefs.push({ key: k, header: k });
      });

      // Formata cada célula para compatibilidade com Excel e ferramentas de BI
      function formatCsvCell(val) {
        if (val === null || val === undefined) return '';
        if (typeof val === 'boolean') return val ? 'Sim' : 'Não';
        if (typeof val === 'object') return JSON.stringify(val);
        // Remove quebras de linha dentro do texto da célula para manter cada documento em uma linha
        return String(val).replace(/\r?\n|\r/g, ' ').trim();
      }

      const headerRow = columnDefs.map(col => `"${col.header.replace(/"/g, '""')}"`).join(';');
      const dataRows = allDocs.map(doc => {
        return columnDefs.map(col => {
          const rawVal = doc[col.key];
          const cellStr = formatCsvCell(rawVal);
          return `"${cellStr.replace(/"/g, '""')}"`;
        }).join(';');
      });

      // UTF-8 BOM (\uFEFF) para abrir com acentuação correta no Microsoft Excel
      const csvContent = '\uFEFF' + [headerRow, ...dataRows].join('\r\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
      const downloadAnchor = document.createElement('a');
      downloadAnchor.href = url;
      downloadAnchor.download = `joakindex_completo_${timestamp}.csv`;
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      document.body.removeChild(downloadAnchor);
      URL.revokeObjectURL(url);

      if (showNotification) {
        showToast('Planilha CSV completa baixada com sucesso!', 'success');
      }
    }

    // Exporta simultaneamente o JSON atualizado e a planilha CSV com todas as informações extraídas
    function exportJSON() {
      exportJSONFile(false);
      setTimeout(() => {
        exportFullCSV(false);
      }, 200);
      showToast('Exportação concluída! Baixando JSON e CSV com todas as informações extraídas.', 'success');
    }

