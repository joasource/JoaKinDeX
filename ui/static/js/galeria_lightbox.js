    let galleryCurrentPage = 1;
    let galleryPageSize = 48;
    let gallerySort = 'data_desc';
    let galleryDensity = 'normal'; // 'compact' | 'normal' | 'large'
    let currentLightboxDoc = null;
    let lightboxMode = 'gallery'; // 'gallery' | 'dossie'
    let currentLightboxDossiePage = 1;
    let lightboxZoomed = false;

    function getSortedGalleryDocs() {
      const docs = [...filteredDocs];
      switch (gallerySort) {
        case 'data_asc':
          return docs.sort((a, b) => {
            const dA = safeString(a.data || a.data_modificacao || '');
            const dB = safeString(b.data || b.data_modificacao || '');
            return dA.localeCompare(dB);
          });
        case 'data_desc':
          return docs.sort((a, b) => {
            const dA = safeString(a.data || a.data_modificacao || '');
            const dB = safeString(b.data || b.data_modificacao || '');
            return dB.localeCompare(dA);
          });
        case 'nome_asc':
          return docs.sort((a, b) => {
            const nA = safeString(a.beneficiario || a.nome_arquivo || '').toLowerCase();
            const nB = safeString(b.beneficiario || b.nome_arquivo || '').toLowerCase();
            return nA.localeCompare(nB);
          });
        case 'nome_desc':
          return docs.sort((a, b) => {
            const nA = safeString(a.beneficiario || a.nome_arquivo || '').toLowerCase();
            const nB = safeString(b.beneficiario || b.nome_arquivo || '').toLowerCase();
            return nB.localeCompare(nA);
          });
        case 'faculdade_asc':
          return docs.sort((a, b) => {
            const fA = safeString(a.faculdade || '').toLowerCase();
            const fB = safeString(b.faculdade || '').toLowerCase();
            return fA.localeCompare(fB);
          });
        case 'status_pendente':
          return docs.sort((a, b) => {
            const isUnprocA = isDocumentUnprocessed(a) ? 1 : 0;
            const isUnprocB = isDocumentUnprocessed(b) ? 1 : 0;
            const isPendA = safeString(a.status_conferencia).toLowerCase() === 'pendente' ? 0 : 1;
            const isPendB = safeString(b.status_conferencia).toLowerCase() === 'pendente' ? 0 : 1;
            if (isPendA !== isPendB) return isPendA - isPendB;
            return isUnprocA - isUnprocB;
          });
        case 'dossie_desc':
          return docs.sort((a, b) => {
            const pA = Array.isArray(a.dossie_paginas) ? a.dossie_paginas.length : 0;
            const pB = Array.isArray(b.dossie_paginas) ? b.dossie_paginas.length : 0;
            return pB - pA;
          });
        default:
          return docs;
      }
    }

    function renderGalleryView() {
      const grid = document.getElementById('galleryCardsGrid');
      const emptyState = document.getElementById('galleryEmptyState');
      if (!grid) return;

      // Sincroniza busca e contadores da galeria
      const searchInp = document.getElementById('gallerySearchInput');
      const mainSearch = document.getElementById('searchInput');
      if (searchInp && mainSearch && searchInp.value !== mainSearch.value) {
        searchInp.value = mainSearch.value;
      }
      const clearBtn = document.getElementById('galleryClearSearchBtn');
      if (clearBtn) {
        if (searchInp && searchInp.value) clearBtn.classList.remove('hidden');
        else clearBtn.classList.add('hidden');
      }

      // Sincroniza Quick Views visuais da galeria
      const gqvIds = ['todos', 'dossies', 'pendentes', 'cursos', 'financeiro', 'identificacao', 'nao_processado'];
      gqvIds.forEach(id => {
        const btn = document.getElementById(`gqv-${id}`);
        if (!btn) return;
        if (id === activeQuickView) {
          btn.className = "px-2.5 py-1 rounded-full font-medium shrink-0 transition flex items-center gap-1 border bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm";
        } else {
          btn.className = "px-2.5 py-1 rounded-full font-medium shrink-0 transition flex items-center gap-1 border bg-slate-900 hover:bg-slate-800 text-slate-400 border-slate-800";
        }
      });

      // Aplica classe de densidade na grade
      if (galleryDensity === 'compact') {
        grid.className = "grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3";
      } else if (galleryDensity === 'large') {
        grid.className = "grid grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5";
      } else {
        grid.className = "grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4";
      }

      const sorted = getSortedGalleryDocs();
      const totalDocs = sorted.length;
      const totalPages = Math.max(1, Math.ceil(totalDocs / galleryPageSize));
      if (galleryCurrentPage > totalPages) galleryCurrentPage = totalPages;
      if (galleryCurrentPage < 1) galleryCurrentPage = 1;

      const startIdx = totalDocs === 0 ? 0 : (galleryCurrentPage - 1) * galleryPageSize;
      const endIdx = Math.min(startIdx + galleryPageSize, totalDocs);
      const pageDocs = sorted.slice(startIdx, endIdx);

      // Atualiza indicadores de texto
      const countEl = document.getElementById('galleryCountText');
      if (countEl) {
        countEl.innerText = totalDocs === 0 
          ? '0 de 0' 
          : `Exibindo ${startIdx + 1}–${endIdx} de ${totalDocs.toLocaleString('pt-BR')}`;
      }
      const subCounter = document.getElementById('galeriaSubheaderCounter');
      if (subCounter) {
        subCounter.innerText = `${totalDocs.toLocaleString('pt-BR')} documentos no filtro atual`;
      }
      const tabBadge = document.getElementById('tabBadgeGaleriaCount');
      if (tabBadge) {
        tabBadge.innerText = totalDocs.toLocaleString('pt-BR');
      }

      if (totalDocs === 0) {
        grid.innerHTML = '';
        if (emptyState) emptyState.classList.remove('hidden');
        renderGalleryPagination(0, 1);
        return;
      }

      if (emptyState) emptyState.classList.add('hidden');

      // Gera HTML dos cards estilo Paperless-ngx
      let html = '';
      pageDocs.forEach(doc => {
        const isDocChecked = selectedMd5s.has(doc.md5);
        const isUnproc = isDocumentUnprocessed(doc);
        const isApproved = !isUnproc && safeString(doc.status_conferencia).toLowerCase() === 'aprovado';
        const isImg = isImageDoc(doc);
        const docFmt = getDocFormatMeta(doc);
        const docDom = safeString(doc.dominio || 'academico').toLowerCase();
        const md5Short = safeString(doc.md5).substring(0, 8);
        const thumbSrc = `/api/thumbnail/${doc.md5}?w=720`;

        // Nome / Beneficiário
        const nome = safeString(doc.beneficiario) || (isUnproc ? (doc.nome_arquivo || 'Arquivo não lido') : 'Sem titular');
        
        const dataDoc = safeString(doc.data || doc.data_modificacao) || '-';

        // Badge de Status
        let statusBadge = '';
        if (isUnproc) {
          statusBadge = `<span class="bg-rose-500/10 text-rose-400 border border-rose-500/20 px-1.5 py-0.5 rounded text-[9.5px] font-semibold flex items-center gap-1"><i class="fa-solid fa-circle-question text-[8px]"></i> Não Lido</span>`;
        } else if (isApproved) {
          statusBadge = `<span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded text-[9.5px] font-semibold flex items-center gap-1"><i class="fa-solid fa-check text-[8px]"></i> OK</span>`;
        } else {
          statusBadge = `<span class="bg-amber-500/10 text-amber-400 border border-amber-500/20 px-1.5 py-0.5 rounded text-[9.5px] font-semibold flex items-center gap-1"><i class="fa-regular fa-clock text-[8px]"></i> Pendente</span>`;
        }

        // Indicador de dossiê multipáginas
        const pgsCount = Array.isArray(doc.dossie_paginas) ? doc.dossie_paginas.length : 1;
        const dossieBadge = pgsCount > 1 
          ? `<span class="bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 px-1.5 py-0.2 rounded text-[9px] font-mono font-bold shrink-0" title="Dossiê com ${pgsCount} páginas">+${pgsCount}p</span>`
          : '';

        const isHybrid = (doc.metodo_leitura === 'hibrido_fallback_openai');
        const hybridGalleryBadge = isHybrid 
          ? `<span class="bg-amber-500/20 text-amber-300 border border-amber-500/40 px-1 py-0.2 rounded text-[8.5px] font-bold shrink-0 flex items-center gap-0.5" title="Fallback Híbrido: Promovido para OpenAI"><i class="fa-solid fa-bolt text-amber-400 text-[7.5px]"></i>Híbrido</span>`
          : '';

        // 1. Obtenção de TODAS as TAGs do documento de forma única e limpa
        let allDocTags = [];
        if (Array.isArray(doc.todos_tipos) && doc.todos_tipos.length > 0) {
          allDocTags = doc.todos_tipos.map(t => safeString(t).trim()).filter(Boolean);
        } else if (doc.tipo_documento) {
          allDocTags = [safeString(doc.tipo_documento).trim()];
        } else {
          allDocTags = [isImg ? 'Imagem' : 'Documento'];
        }

        // Desduplicação preservando a ordem
        const seenDocTags = new Set();
        allDocTags = allDocTags.filter(t => {
          const k = t.toLowerCase();
          if (seenDocTags.has(k)) return false;
          seenDocTags.add(k);
          return true;
        });

        // 2. Tag Principal (Tag-Mestre)
        const primaryTag = allDocTags.length > 0 ? allDocTags[0] : (isImg ? 'Imagem' : 'Documento');
        const primaryMeta = getTagMeta(primaryTag);

        // 3. Subtags da Tag Principal (Atributos Filhos: Curso, Nível, Emissor, etc.)
        const subtags = getPrimaryTagSubtags(doc, primaryTag, docDom);
        let subtagsHtml = '';
        subtags.forEach(sub => {
          subtagsHtml += `<span class="text-[9.5px] px-1.5 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/60 font-medium truncate max-w-[140px] inline-flex items-center gap-1 shadow-sm hover:border-slate-500 transition" title="${escapeHtml(sub.title)}: ${escapeHtml(sub.label)}">
            ${sub.icon ? `<i class="${sub.icon} text-[8.5px] shrink-0"></i>` : ''}
            <span class="truncate">${escapeHtml(sub.label)}</span>
          </span>`;
        });

        // 4. Anexos (Demais Tags presentes no arquivo)
        const anexosTags = allDocTags.slice(1);
        let anexosBlockHtml = '';
        if (anexosTags.length > 0) {
          let anexosPills = '';
          anexosTags.forEach(t => {
            const meta = getTagMeta(t);
            anexosPills += `<span onclick="event.stopPropagation(); setTipoFilter('${escapeHtml(t)}');"
              class="text-[9px] px-1.5 py-0.2 rounded border font-medium truncate max-w-[125px] inline-flex items-center gap-1 opacity-90 hover:opacity-100 hover:brightness-125 cursor-pointer shadow-sm transition ${meta.bg}"
              title="Filtrar por: ${escapeHtml(t)}">
              <i class="${meta.icon} text-[8px] ${meta.color} shrink-0"></i>
              <span class="truncate">${escapeHtml(t)}</span>
            </span>`;
          });

          anexosBlockHtml = `
            <div class="flex items-center gap-1 flex-wrap pt-1 border-t border-slate-800/60 mt-auto">
              <span class="text-[9px] text-slate-400 font-medium uppercase tracking-wider flex items-center gap-1 shrink-0" title="Outros documentos identificados neste arquivo">
                <i class="fa-solid fa-paperclip text-[8.5px] text-slate-400"></i> Anexos:
              </span>
              ${anexosPills}
            </div>
          `;
        }

        html += `
          <div id="gcard-${doc.md5}" onclick="openInConference('${doc.md5}')"
               class="gallery-card group bg-slate-900/90 border border-slate-800 hover:border-slate-700/90 rounded-xl p-3 flex flex-col justify-between shadow-sm cursor-pointer select-none relative overflow-hidden ${isDocChecked ? 'is-selected ring-2 ring-emerald-500/60 bg-emerald-950/20 border-emerald-500/70' : ''}">
            
            <!-- Topo do Card: Checkbox + Badges -->
            <div class="flex items-center justify-between gap-1.5 mb-2 shrink-0">
              <div class="flex items-center gap-1.5" onclick="event.stopPropagation()">
                <input type="checkbox" ${isDocChecked ? 'checked' : ''}
                       onchange="toggleSelectDoc('${doc.md5}', this.checked); updateGalleryCardSelection('${doc.md5}', this.checked);"
                       class="rounded border-slate-700 bg-slate-950 text-emerald-500 focus:ring-emerald-500 cursor-pointer h-3.5 w-3.5"
                       title="Selecionar para ações em lote">
                <span class="text-[9px] font-mono font-bold px-1.5 py-0.2 rounded border ${docFmt.badgeClass}" title="Formato: ${docFmt.label}">
                  <i class="${docFmt.icon} text-[8px] mr-0.5"></i>${docFmt.label}
                </span>
                ${dossieBadge}
                ${hybridGalleryBadge}
              </div>
              <div class="shrink-0" id="gcard-status-${doc.md5}">
                ${statusBadge}
              </div>
            </div>

            <!-- Miniatura do Documento (Proporção A4) com Overlay de Ações -->
            <div class="gallery-thumbnail-container relative w-full bg-slate-950 rounded-lg border border-slate-800/80 overflow-hidden mb-2.5 flex items-center justify-center shadow-inner group/thumb">
              <img src="${thumbSrc}" loading="lazy" decoding="async" alt="Capa"
                   class="w-full h-full object-cover object-top transition duration-200 group-hover/thumb:scale-[1.03]"
                   onerror="this.style.display='none'; this.nextElementSibling.classList.remove('hidden');">
              <div class="hidden w-full h-full flex flex-col items-center justify-center text-slate-600 bg-slate-950 p-2 text-center">
                <i class="${docFmt.icon} text-3xl ${docFmt.color} opacity-60 mb-1"></i>
                <span class="text-[9px] font-mono font-semibold text-slate-400">${docFmt.label}</span>
              </div>

              <!-- Hover Action Overlay (Paperless Action Bar) -->
              <div class="absolute inset-0 bg-slate-950/75 backdrop-blur-[2px] opacity-0 group-hover/thumb:opacity-100 transition-all duration-200 flex items-center justify-center gap-1.5 p-2" onclick="event.stopPropagation()">
                <button type="button" onclick="openGalleryLightbox('${doc.md5}', event)" title="Visualizar Ampliado"
                        class="p-2 bg-slate-800/90 hover:bg-slate-700 text-slate-200 hover:text-white rounded-lg text-xs shadow transition">
                  <i class="fa-solid fa-magnifying-glass-plus"></i>
                </button>
                <button type="button" onclick="openInConference('${doc.md5}', event)" title="Abrir na Conferência Humana"
                        class="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold shadow transition flex items-center gap-1">
                  <i class="fa-solid fa-table-columns text-[10px]"></i>
                  <span>Conferir</span>
                </button>
                <button type="button" onclick="quickApproveFromGallery('${doc.md5}', event)" title="Aprovar Documento Instantaneamente"
                        class="p-2 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-xs shadow transition">
                  <i class="fa-solid fa-check"></i>
                </button>
              </div>
            </div>

            <!-- Corpo de Metadados Hierárquico -->
            <div class="flex-1 flex flex-col gap-1.5 min-w-0">
              <!-- Nome / Titular -->
              <div class="font-bold text-xs text-slate-100 truncate group-hover:text-amber-300 transition" title="${nome}">
                ${nome}
              </div>

              <!-- Tag-Mestre com Subtags Inline -->
              <div class="flex items-center gap-1 flex-wrap pt-0.5">
                <span onclick="event.stopPropagation(); setTipoFilter('${escapeHtml(primaryTag)}');"
                      class="text-[10px] px-2 py-0.5 rounded font-semibold border inline-flex items-center gap-1 shadow-sm shrink-0 cursor-pointer hover:brightness-125 transition ${primaryMeta.bg}"
                      title="Filtrar por: ${escapeHtml(primaryTag)}">
                  <i class="${primaryMeta.icon} text-[9px] ${primaryMeta.color} shrink-0"></i>
                  <span>${escapeHtml(primaryTag)}</span>
                </span>
                ${subtags.length > 0 ? `<i class="fa-solid fa-angle-right text-[8.5px] text-slate-600 shrink-0"></i>` : ''}
                ${subtagsHtml}
              </div>

              <!-- Linha de Documentos Anexos (se houver) -->
              ${anexosBlockHtml}

              <!-- Rodapé do Card: Data & Hash MD5 -->
              <div class="flex items-center justify-between text-[10px] text-slate-500 pt-1.5 border-t border-slate-800/80 mt-auto font-mono">
                <span class="flex items-center gap-1"><i class="fa-regular fa-calendar text-[9px]"></i>${dataDoc}</span>
                <span title="${doc.md5}">${md5Short}...</span>
              </div>
            </div>

          </div>
        `;
      });

      grid.innerHTML = html;
      renderGalleryPagination(totalPages, galleryCurrentPage);
    }

    function renderGalleryPagination(totalPages, curPage) {
      const btnContainer = document.getElementById('galleryPaginationButtons');
      const pageNumEl = document.getElementById('galleryPageNum');
      const totalPagesEl = document.getElementById('galleryTotalPages');

      if (pageNumEl) pageNumEl.innerText = totalPages === 0 ? 0 : curPage;
      if (totalPagesEl) totalPagesEl.innerText = totalPages;
      if (!btnContainer) return;

      if (totalPages <= 1) {
        btnContainer.innerHTML = '';
        return;
      }

      let btns = '';

      // Primeira página
      btns += `
        <button type="button" onclick="changeGalleryPage(1)" ${curPage === 1 ? 'disabled' : ''}
                class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed text-slate-200 border border-slate-700 text-xs font-mono" title="Primeira Página">
          <i class="fa-solid fa-angles-left"></i>
        </button>
      `;

      // Página anterior
      btns += `
        <button type="button" onclick="changeGalleryPage(${curPage - 1})" ${curPage === 1 ? 'disabled' : ''}
                class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed text-slate-200 border border-slate-700 text-xs flex items-center gap-1 font-medium" title="Página Anterior">
          <i class="fa-solid fa-chevron-left"></i>
          <span class="hidden sm:inline">Anterior</span>
        </button>
      `;

      // Páginas ao redor
      const maxButtons = 5;
      let startP = Math.max(1, curPage - 2);
      let endP = Math.min(totalPages, startP + maxButtons - 1);
      if (endP - startP < maxButtons - 1) {
        startP = Math.max(1, endP - maxButtons + 1);
      }

      if (startP > 1) {
        btns += `<button type="button" onclick="changeGalleryPage(1)" class="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-400 border border-slate-800 text-xs font-mono">1</button>`;
        if (startP > 2) btns += `<span class="px-1 text-slate-600 font-mono">...</span>`;
      }

      for (let p = startP; p <= endP; p++) {
        if (p === curPage) {
          btns += `<button type="button" class="px-2.5 py-1 rounded bg-amber-600 text-white font-bold border border-amber-500 text-xs font-mono shadow-sm">${p}</button>`;
        } else {
          btns += `<button type="button" onclick="changeGalleryPage(${p})" class="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-xs font-mono transition">${p}</button>`;
        }
      }

      if (endP < totalPages) {
        if (endP < totalPages - 1) btns += `<span class="px-1 text-slate-600 font-mono">...</span>`;
        btns += `<button type="button" onclick="changeGalleryPage(${totalPages})" class="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-slate-400 border border-slate-800 text-xs font-mono">${totalPages}</button>`;
      }

      // Próxima página
      btns += `
        <button type="button" onclick="changeGalleryPage(${curPage + 1})" ${curPage === totalPages ? 'disabled' : ''}
                class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed text-slate-200 border border-slate-700 text-xs flex items-center gap-1 font-medium" title="Próxima Página">
          <span class="hidden sm:inline">Próxima</span>
          <i class="fa-solid fa-chevron-right"></i>
        </button>
      `;

      // Última página
      btns += `
        <button type="button" onclick="changeGalleryPage(${totalPages})" ${curPage === totalPages ? 'disabled' : ''}
                class="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed text-slate-200 border border-slate-700 text-xs font-mono" title="Última Página">
          <i class="fa-solid fa-angles-right"></i>
        </button>
      `;

      btnContainer.innerHTML = btns;
    }

    function changeGalleryPage(newPage) {
      galleryCurrentPage = newPage;
      renderGalleryView();
      const scrollEl = document.getElementById('galleryScrollContainer');
      if (scrollEl) scrollEl.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function setGallerySort(sortKey) {
      gallerySort = sortKey;
      galleryCurrentPage = 1;
      renderGalleryView();
    }

    function setGalleryDensity(density) {
      galleryDensity = density;
      ['compact', 'normal', 'large'].forEach(d => {
        const btn = document.getElementById(`btnDensity${d.charAt(0).toUpperCase() + d.slice(1)}`);
        if (btn) {
          if (d === density) {
            btn.className = "px-2 py-1 rounded text-[11px] font-medium transition bg-slate-800 text-amber-300 shadow-sm";
          } else {
            btn.className = "px-2 py-1 rounded text-[11px] font-medium transition text-slate-400 hover:text-slate-200";
          }
        }
      });
      renderGalleryView();
    }

    function setGalleryPageSize(size) {
      galleryPageSize = size;
      galleryCurrentPage = 1;
      renderGalleryView();
    }

    function onGallerySearchInput(val) {
      const mainSearch = document.getElementById('searchInput');
      if (mainSearch) {
        mainSearch.value = val;
      }
      clearTimeout(searchDebounceTimeout);
      searchDebounceTimeout = setTimeout(() => {
        applyFilter(true);
      }, 250);
    }

    function clearGallerySearch() {
      const gSearch = document.getElementById('gallerySearchInput');
      if (gSearch) gSearch.value = '';
      const mSearch = document.getElementById('searchInput');
      if (mSearch) mSearch.value = '';
      applyFilter(true);
    }

    function updateGalleryCardSelection(md5, isChecked) {
      const card = document.getElementById(`gcard-${md5}`);
      if (!card) return;
      if (isChecked) {
        card.classList.add('is-selected', 'ring-2', 'ring-emerald-500/60', 'bg-emerald-950/20', 'border-emerald-500/70');
      } else {
        card.classList.remove('is-selected', 'ring-2', 'ring-emerald-500/60', 'bg-emerald-950/20', 'border-emerald-500/70');
      }
    }

    function toggleSelectAllGallery() {
      const sorted = getSortedGalleryDocs();
      const startIdx = (galleryCurrentPage - 1) * galleryPageSize;
      const endIdx = Math.min(startIdx + galleryPageSize, sorted.length);
      const pageDocs = sorted.slice(startIdx, endIdx);

      const allPageSelected = pageDocs.every(d => selectedMd5s.has(d.md5));
      pageDocs.forEach(d => {
        if (allPageSelected) {
          selectedMd5s.delete(d.md5);
        } else {
          selectedMd5s.add(d.md5);
        }
      });

      renderGalleryView();
      updateBulkUI();
      renderSidebar();
    }

    function openInConference(md5, event) {
      if (event) event.stopPropagation();
      const idx = filteredDocs.findIndex(d => d.md5 === md5);
      if (idx !== -1) {
        selectDocument(idx);
      }
      switchMainTab('conferencia');
    }

    async function quickApproveFromGallery(md5, event) {
      if (event) event.stopPropagation();
      const doc = documents.find(d => d.md5 === md5);
      if (!doc) return;

      doc.status_conferencia = 'aprovado';
      const statusBadgeContainer = document.getElementById(`gcard-status-${md5}`);
      if (statusBadgeContainer) {
        statusBadgeContainer.innerHTML = `<span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded text-[9.5px] font-semibold flex items-center gap-1 animate-pulse"><i class="fa-solid fa-check text-[8px]"></i> OK</span>`;
      }

      showToast(`Documento ${safeString(doc.beneficiario) || md5.substring(0, 8)} aprovado!`, 'success');

      try {
        await fetch('/api/save_classification', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(doc)
        });
      } catch (e) {
        console.warn('Erro ao salvar aprovação no servidor:', e);
      }

      updateCounters();
    }

    function toggleLightboxZoom() {
      const imgEl = document.getElementById('lightboxImageEl');
      if (!imgEl) return;
      lightboxZoomed = !lightboxZoomed;
      if (lightboxZoomed) {
        imgEl.style.transform = 'scale(1.8)';
        imgEl.style.cursor = 'zoom-out';
      } else {
        imgEl.style.transform = '';
        imgEl.style.cursor = 'zoom-in';
      }
    }

    function openGalleryLightbox(md5, event) {
      if (event) event.stopPropagation();
      const doc = documents.find(d => d.md5 === md5);
      if (!doc) return;
      currentLightboxDoc = doc;
      lightboxMode = 'gallery';
      lightboxZoomed = false;

      const modal = document.getElementById('galleryLightboxModal');
      const titleEl = document.getElementById('lightboxTitle');
      const md5El = document.getElementById('lightboxMd5');
      const badgeEl = document.getElementById('lightboxStatusBadge');
      const imgEl = document.getElementById('lightboxImageEl');
      const detailsEl = document.getElementById('lightboxDetails');
      const btnPrev = document.getElementById('lightboxBtnPrev');
      const btnNext = document.getElementById('lightboxBtnNext');

      if (btnPrev) {
        btnPrev.style.display = '';
        btnPrev.title = 'Documento anterior (←)';
      }
      if (btnNext) {
        btnNext.style.display = '';
        btnNext.title = 'Próximo documento (→)';
      }

      if (imgEl) {
        imgEl.style.transform = '';
        imgEl.style.cursor = 'zoom-in';
        imgEl.src = `/api/thumbnail/${doc.md5}?w=1080`;
      }

      if (titleEl) titleEl.innerText = safeString(doc.beneficiario) || doc.nome_arquivo || 'Documento';

      const sorted = getSortedGalleryDocs();
      const curIdx = sorted.findIndex(d => d.md5 === doc.md5);
      if (md5El) {
        const posText = curIdx !== -1 ? `[${curIdx + 1} de ${sorted.length}] ` : '';
        md5El.innerText = `${posText}MD5: ${doc.md5}`;
      }

      const isAppr = safeString(doc.status_conferencia).toLowerCase() === 'aprovado';
      const isUnproc = isDocumentUnprocessed(doc);
      if (badgeEl) {
        if (isUnproc) {
          badgeEl.className = 'text-[10px] px-2 py-0.5 rounded font-medium border bg-rose-500/10 text-rose-400 border-rose-500/30 shrink-0';
          badgeEl.innerText = 'Não Lido';
        } else if (isAppr) {
          badgeEl.className = 'text-[10px] px-2 py-0.5 rounded font-medium border bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shrink-0';
          badgeEl.innerText = 'Aprovado / OK';
        } else {
          badgeEl.className = 'text-[10px] px-2 py-0.5 rounded font-medium border bg-amber-500/10 text-amber-400 border-amber-500/30 shrink-0';
          badgeEl.innerText = 'Pendente';
        }
      }

      if (detailsEl) {
        const docDom = safeString(doc.dominio || 'academico').toLowerCase();
        let metaHtml = '';
        const allTags = Array.isArray(doc.todos_tipos) && doc.todos_tipos.length > 0 
          ? doc.todos_tipos.join(', ') 
          : safeString(doc.tipo_documento || 'Documento');

        if (docDom === 'financeiro') {
          const valor = safeString(doc.valor_monetario || '-');
          const banco = safeString(doc.faculdade || doc.pix_pagador_banco || '-');
          metaHtml = `
            <span><strong>Valor:</strong> ${escapeHtml(valor)}</span>
            <span>•</span>
            <span><strong>Instituição / Banco:</strong> ${escapeHtml(banco)}</span>
            <span>•</span>
            <span><strong>Data:</strong> ${escapeHtml(safeString(doc.data || doc.data_modificacao) || '-')}</span>
            <span>•</span>
            <span><strong>TAGs:</strong> ${escapeHtml(allTags)}</span>
          `;
        } else if (docDom === 'identificacao') {
          const docId = [doc.cpf ? `CPF: ${doc.cpf}` : '', doc.rg ? `RG: ${doc.rg}` : ''].filter(Boolean).join(' • ') || '-';
          const emissor = safeString(doc.faculdade || 'Órgão Emissor');
          metaHtml = `
            <span><strong>Documento:</strong> ${escapeHtml(docId)}</span>
            <span>•</span>
            <span><strong>Órgão:</strong> ${escapeHtml(emissor)}</span>
            <span>•</span>
            <span><strong>Data:</strong> ${escapeHtml(safeString(doc.data || doc.data_modificacao) || '-')}</span>
            <span>•</span>
            <span><strong>TAGs:</strong> ${escapeHtml(allTags)}</span>
          `;
        } else if (docDom === 'juridico') {
          metaHtml = `
            <span><strong>Emissor / Cartório:</strong> ${escapeHtml(safeString(doc.faculdade) || '-')}</span>
            <span>•</span>
            <span><strong>Data:</strong> ${escapeHtml(safeString(doc.data || doc.data_modificacao) || '-')}</span>
            <span>•</span>
            <span><strong>TAGs:</strong> ${escapeHtml(allTags)}</span>
          `;
        } else if (docDom === 'profissional' || doc.cnpj || (doc.dados_extras && doc.dados_extras.cnpj)) {
          const de = doc.dados_extras || {};
          const cnpjVal = safeString(doc.cnpj || de.cnpj || '-');
          const sit = safeString(de.situacao_cadastral || doc.situacao_cadastral || '');
          const sitHtml = sit ? `<span>•</span><span><strong>Situação:</strong> <span class="${sit.includes('ATIVA') ? 'text-emerald-400 font-semibold' : 'text-rose-400 font-semibold'}">${escapeHtml(sit)}</span></span>` : '';
          const fantasia = safeString(de.nome_fantasia || doc.nome_fantasia || '');
          const fantasiaHtml = fantasia ? `<span>•</span><span><strong>Fantasia:</strong> ${escapeHtml(fantasia)}</span>` : '';
          const cnae = safeString(de.cnae_principal || doc.cnae_principal || '');
          const cnaeHtml = cnae ? `<span>•</span><span><strong>CNAE:</strong> ${escapeHtml(cnae.length > 28 ? cnae.substring(0, 25) + '...' : cnae)}</span>` : '';
          metaHtml = `
            <span><strong>CNPJ:</strong> <span class="font-mono text-emerald-400">${escapeHtml(cnpjVal)}</span></span>
            ${sitHtml}
            ${fantasiaHtml}
            ${cnaeHtml}
            <span>•</span>
            <span><strong>Data:</strong> ${escapeHtml(safeString(doc.data || doc.data_modificacao) || '-')}</span>
            <span>•</span>
            <span><strong>TAGs:</strong> ${escapeHtml(allTags)}</span>
          `;
        } else {
          // Acadêmico / Geral
          const cursoInfo = doc.curso ? `<span><strong>Curso:</strong> ${escapeHtml(doc.curso)}</span><span>•</span>` : '';
          metaHtml = `
            ${cursoInfo}
            <span><strong>Instituição:</strong> ${escapeHtml(safeString(doc.faculdade) || '-')}</span>
            <span>•</span>
            <span><strong>Data:</strong> ${escapeHtml(safeString(doc.data || doc.data_modificacao) || '-')}</span>
            <span>•</span>
            <span><strong>TAGs:</strong> ${escapeHtml(allTags)}</span>
          `;
        }
        detailsEl.innerHTML = metaHtml;
      }

      updateLightboxActionButtons();
      if (modal) modal.classList.remove('hidden');
    }

    function openDossiePageLightbox(pageNum) {
      if (currentIndex < 0 || !filteredDocs || !filteredDocs[currentIndex]) return;
      const doc = filteredDocs[currentIndex];
      currentLightboxDoc = doc;
      lightboxMode = 'dossie';
      currentLightboxDossiePage = parseInt(pageNum) || 1;
      lightboxZoomed = false;

      const modal = document.getElementById('galleryLightboxModal');
      const titleEl = document.getElementById('lightboxTitle');
      const md5El = document.getElementById('lightboxMd5');
      const badgeEl = document.getElementById('lightboxStatusBadge');
      const imgEl = document.getElementById('lightboxImageEl');
      const detailsEl = document.getElementById('lightboxDetails');
      const btnPrev = document.getElementById('lightboxBtnPrev');
      const btnNext = document.getElementById('lightboxBtnNext');

      const isImg = isImageDoc(doc);
      const dossie = (Array.isArray(doc.dossie_paginas) && doc.dossie_paginas.length > 0)
        ? doc.dossie_paginas
        : [{ pagina: 1, tipo: doc.tipo_documento || 'Documento' }];
      const totalPages = Math.max(1, parseInt(doc.paginas) || dossie.length);

      if (currentLightboxDossiePage < 1) currentLightboxDossiePage = 1;
      if (currentLightboxDossiePage > totalPages) currentLightboxDossiePage = totalPages;

      const pageItem = dossie.find(d => d.pagina === currentLightboxDossiePage);
      const pageType = pageItem ? pageItem.tipo : (currentLightboxDossiePage === 1 ? (doc.tipo_documento || 'Página Inicial') : `Página ${currentLightboxDossiePage}`);

      if (btnPrev) {
        btnPrev.style.display = (totalPages > 1) ? '' : 'none';
        btnPrev.title = 'Página anterior (←)';
      }
      if (btnNext) {
        btnNext.style.display = (totalPages > 1) ? '' : 'none';
        btnNext.title = 'Próxima página (→)';
      }

      if (imgEl) {
        imgEl.style.transform = '';
        imgEl.style.cursor = 'zoom-in';
        imgEl.src = isImg ? `/api/arquivo/${doc.md5}` : `/api/thumbnail/${doc.md5}/${currentLightboxDossiePage}?w=1440`;
      }

      if (titleEl) {
        titleEl.innerText = `${doc.nome_arquivo || 'Documento'} — Página ${currentLightboxDossiePage} de ${totalPages}`;
      }

      if (md5El) {
        md5El.innerText = `Pág. ${currentLightboxDossiePage} de ${totalPages} • MD5: ${doc.md5}`;
      }

      if (badgeEl) {
        badgeEl.className = 'text-[10px] px-2.5 py-0.5 rounded font-medium border bg-cyan-500/15 text-cyan-300 border-cyan-500/40 shrink-0';
        badgeEl.innerText = pageType;
      }

      if (detailsEl) {
        detailsEl.innerHTML = `
          <span><strong>Arquivo:</strong> ${escapeHtml(doc.nome_arquivo || '-')}</span>
          <span>•</span>
          <span><strong>Página:</strong> ${currentLightboxDossiePage} de ${totalPages}</span>
          <span>•</span>
          <span><strong>Classificação da Página:</strong> <span class="text-cyan-300 font-semibold">${escapeHtml(pageType)}</span></span>
          <span>•</span>
          <span><strong>Beneficiário:</strong> ${escapeHtml(doc.beneficiario || '-')}</span>
        `;
      }

      updateLightboxActionButtons();
      if (modal) modal.classList.remove('hidden');
    }

    function updateLightboxActionButtons() {
      const btnConf = document.getElementById('lightboxBtnConferir');
      if (!btnConf) return;
      if (lightboxMode === 'dossie') {
        btnConf.className = 'px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow';
        btnConf.innerHTML = `<i class="fa-solid fa-eye"></i><span>Exibir no Leitor (Pág. ${currentLightboxDossiePage})</span>`;
        btnConf.onclick = () => jumpToPdfPageFromLightbox(currentLightboxDossiePage);
      } else {
        btnConf.className = 'px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow';
        btnConf.innerHTML = `<i class="fa-solid fa-table-columns"></i><span>Abrir na Conferência</span>`;
        btnConf.onclick = () => openLightboxDocInConference();
      }
    }

    function jumpToPdfPageFromLightbox(pageNum) {
      closeGalleryLightbox();
      if (typeof currentMainTab !== 'undefined' && currentMainTab !== 'conferencia') {
        switchMainTab('conferencia');
      }
      jumpToPdfPage(pageNum);
      const card = document.getElementById(`dossieCardPage_${pageNum}`);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }

    function navigateLightbox(step) {
      if (!currentLightboxDoc) return;

      if (lightboxMode === 'dossie') {
        const doc = currentLightboxDoc;
        const totalPages = Math.max(1, parseInt(doc.paginas) || (Array.isArray(doc.dossie_paginas) ? doc.dossie_paginas.length : 1));
        const nextPage = currentLightboxDossiePage + step;
        if (nextPage >= 1 && nextPage <= totalPages) {
          openDossiePageLightbox(nextPage);
        } else {
          if (step > 0) {
            showToast('Você já está na última página deste dossiê.', 'info');
          } else {
            showToast('Você já está na primeira página deste dossiê.', 'info');
          }
        }
        return;
      }

      const sorted = getSortedGalleryDocs();
      const idx = sorted.findIndex(d => d.md5 === currentLightboxDoc.md5);
      if (idx !== -1) {
        const nextIdx = idx + step;
        if (nextIdx >= 0 && nextIdx < sorted.length) {
          openGalleryLightbox(sorted[nextIdx].md5);
        }
      }
    }

    function closeGalleryLightbox() {
      const modal = document.getElementById('galleryLightboxModal');
      if (modal) modal.classList.add('hidden');
      const imgEl = document.getElementById('lightboxImageEl');
      if (imgEl) {
        imgEl.style.transform = '';
        imgEl.style.cursor = 'zoom-in';
      }
      lightboxZoomed = false;
      currentLightboxDoc = null;
      lightboxMode = 'gallery';
      currentLightboxDossiePage = 1;
    }

    function openLightboxDocInConference() {
      if (currentLightboxDoc && currentLightboxDoc.md5) {
        const md5 = currentLightboxDoc.md5;
        closeGalleryLightbox();
        openInConference(md5);
      }
    }

    // =========================================================================
    // MÓDULO DE BUSINESS INTELLIGENCE (BI) & ESTATÍSTICAS INTERATIVAS
    // =========================================================================
