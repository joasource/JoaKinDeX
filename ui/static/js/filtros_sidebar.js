    function loadAccordionsState() {}
    function saveAccordionsState() {}
    function toggleAccordion() {}
    function applyAccordionsState() {}

    // Identifica contexto e categorias das TAGs selecionadas para refinamento dinâmico e progressivo
    function getSelectedTagsCategoryContext() {
      const hasTags = selectedTipos.size > 0;
      if (!hasTags) {
        return { hasTags: false, isAcademic: false, isFinancial: false, isIdentity: false, isProfessional: false, isJuridico: false, isProcessual: false };
      }

      let isAcademic = false;
      let isFinancial = false;
      let isIdentity = false;
      let isProfessional = false;
      let isJuridico = false;
      let isProcessual = false;

      selectedTipos.forEach(tipo => {
        if (tipo === 'macro:produtos_academicos') {
          isAcademic = true;
          return;
        }
        if (tipo === 'macro:carreira_profissional') {
          isProfessional = true;
          return;
        }
        if (tipo === 'macro:identificacao_pessoal') {
          isIdentity = true;
          return;
        }
        if (tipo === 'macro:financeiro') {
          isFinancial = true;
          return;
        }
        if (tipo === 'macro:juridico_normativo') {
          isJuridico = true;
          return;
        }

        const cat = getTagCategory(tipo);
        if (cat === 'Produtos Acadêmicos') isAcademic = true;
        else if (cat === 'Carreira & Profissional') isProfessional = true;
        else if (cat === 'Identificação & Pessoal') isIdentity = true;
        else if (cat === 'Financeiro') isFinancial = true;
        else if (cat === 'Jurídico & Normativo') isJuridico = true;
        else if (cat === 'Processual & Administrativo') isProcessual = true;
      });

      return {
        hasTags: true,
        isAcademic,
        isFinancial,
        isIdentity,
        isProfessional,
        isJuridico,
        isProcessual
      };
    }

    // Atualiza estado visual e rótulos das Pílulas de Filtro Flutuantes (TAGs, Nível, Instituição, Pendentes, Limpar)
    function updateFilterPillsUI() {
      const tagCtx = getSelectedTagsCategoryContext();
      const shouldShowInstituicao = tagCtx.hasTags;
      const shouldShowNatureza = tagCtx.hasTags && tagCtx.isAcademic;

      // Limpar filtros dependentes caso suas facetas fiquem ocultas
      if (!shouldShowNatureza && selectedNaturezas.size > 0) {
        selectedNaturezas.clear();
      }
      if (!shouldShowInstituicao && selectedInstituicoes.size > 0) {
        selectedInstituicoes.clear();
      }

      // Fechar popovers se a pílula correspondente foi ocultada
      if (!shouldShowNatureza) {
        ['popoverNatureza', 'g-popoverNatureza'].forEach(id => {
          const el = document.getElementById(id);
          if (el) el.classList.add('hidden');
        });
      }
      if (!shouldShowInstituicao) {
        ['popoverInstituicao', 'g-popoverInstituicao'].forEach(id => {
          const el = document.getElementById(id);
          if (el) el.classList.add('hidden');
        });
      }

      // Configuração contextual do rótulo e ícone da pílula de Instituição / Emissor
      let instLabelDefault = 'Instituição';
      let instIconClass = 'fa-solid fa-building-columns text-amber-400 text-[10.5px]';
      let instTitleDefault = 'Filtrar por faculdade ou instituição emissora';
      let instHeaderTitle = 'Instituição / Emissor';
      let instSearchPlaceholder = 'Filtrar instituições...';

      if (tagCtx.isProfessional && !tagCtx.isAcademic && !tagCtx.isFinancial && !tagCtx.isIdentity && !tagCtx.isJuridico) {
        instLabelDefault = 'Empresa / Órgão';
        instIconClass = 'fa-solid fa-briefcase text-sky-400 text-[10.5px]';
        instTitleDefault = 'Filtrar por empresa, empregador ou órgão emissor';
        instHeaderTitle = 'Empresa / Empregador / Órgão';
        instSearchPlaceholder = 'Filtrar empresas...';
      } else if (tagCtx.isFinancial && !tagCtx.isAcademic && !tagCtx.isIdentity && !tagCtx.isProfessional && !tagCtx.isJuridico) {
        instLabelDefault = 'Banco';
        instIconClass = 'fa-solid fa-building-columns text-emerald-400 text-[10.5px]';
        instTitleDefault = 'Filtrar por banco ou emissor financeiro';
        instHeaderTitle = 'Banco / Emissor';
        instSearchPlaceholder = 'Filtrar bancos...';
      } else if (tagCtx.isIdentity && !tagCtx.isAcademic && !tagCtx.isFinancial && !tagCtx.isProfessional && !tagCtx.isJuridico) {
        instLabelDefault = 'Órgão / UF';
        instIconClass = 'fa-solid fa-id-card text-purple-400 text-[10.5px]';
        instTitleDefault = 'Filtrar por órgão emissor ou estado';
        instHeaderTitle = 'Órgão Emissor / UF';
        instSearchPlaceholder = 'Filtrar órgãos ou UFs...';
      } else if (tagCtx.isJuridico && !tagCtx.isAcademic && !tagCtx.isFinancial && !tagCtx.isIdentity && !tagCtx.isProfessional) {
        instLabelDefault = 'Cartório / Órgão';
        instIconClass = 'fa-solid fa-scale-balanced text-rose-400 text-[10.5px]';
        instTitleDefault = 'Filtrar por cartório, tribunal ou órgão';
        instHeaderTitle = 'Cartório / Tribunal / Órgão';
        instSearchPlaceholder = 'Filtrar cartórios ou órgãos...';
      } else if (tagCtx.isAcademic && !tagCtx.isFinancial && !tagCtx.isIdentity && !tagCtx.isProfessional && !tagCtx.isJuridico) {
        instLabelDefault = 'Faculdade';
        instIconClass = 'fa-solid fa-building-columns text-amber-400 text-[10.5px]';
        instTitleDefault = 'Filtrar por faculdade ou instituição de ensino';
        instHeaderTitle = 'Faculdade / Universidade';
        instSearchPlaceholder = 'Filtrar faculdades...';
      }

      ['popoverTitleInstituicao', 'g-popoverTitleInstituicao'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerText = instHeaderTitle;
      });
      ['popoverIconInstituicao', 'g-popoverIconInstituicao'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.className = instIconClass.replace('text-[10.5px]', 'text-[11px]');
      });
      ['inputSearchInst', 'g-inputSearchInst'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.placeholder = instSearchPlaceholder;
      });

      const prefixes = ['', 'g-'];

      prefixes.forEach(p => {
        // 1. Pílula: TAGs (Tipo de Documento)
        const pillTipo = document.getElementById(`${p}pillTipo`);
        const lblTipo = document.getElementById(`${p}labelPillTipo`);
        const chevTipo = document.getElementById(`${p}chevronPillTipo`);
        const clrTipo = document.getElementById(`${p}clearPillTipo`);
        if (pillTipo && lblTipo) {
          if (selectedTipos.size > 0) {
            pillTipo.className = "px-2.5 py-1 rounded-lg text-xs font-semibold border flex items-center gap-1.5 transition shrink-0 bg-teal-500/20 text-teal-300 border-teal-500/40 shadow-sm";
            if (selectedTipos.size === 1) {
              const tipoVal = Array.from(selectedTipos)[0];
              const macro = MACRO_TAGS.find(m => m.id === tipoVal || m.label === tipoVal);
              const displayLabel = macro ? (macro.shortLabel || macro.label) : tipoVal;
              const shortTipo = displayLabel.length > 15 ? displayLabel.substring(0, 13) + '...' : displayLabel;
              lblTipo.innerText = shortTipo;
              lblTipo.title = macro ? macro.label : tipoVal;
            } else {
              lblTipo.innerText = `TAGs (${selectedTipos.size})`;
              lblTipo.title = Array.from(selectedTipos).map(t => {
                const m = MACRO_TAGS.find(x => x.id === t || x.label === t);
                return m ? m.label : t;
              }).join(', ');
            }
            if (chevTipo) chevTipo.classList.add('hidden');
            if (clrTipo) clrTipo.classList.remove('hidden');
          } else {
            pillTipo.className = "px-2.5 py-1 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition shrink-0 bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-800";
            lblTipo.innerText = "TAGs";
            lblTipo.title = "Filtrar por TAGs (Tipo de Documento)";
            if (chevTipo) chevTipo.classList.remove('hidden');
            if (clrTipo) clrTipo.classList.add('hidden');
          }
        }

        // 2. Pílula: Nível / Natureza do Curso (Visível apenas com TAG acadêmica ativa)
        const contNat = document.getElementById(`${p}containerFilterNatureza`);
        if (contNat) {
          if (shouldShowNatureza) contNat.classList.remove('hidden');
          else contNat.classList.add('hidden');
        }
        const pillNat = document.getElementById(`${p}pillNatureza`);
        const lblNat = document.getElementById(`${p}labelPillNatureza`);
        const chevNat = document.getElementById(`${p}chevronPillNatureza`);
        const clrNat = document.getElementById(`${p}clearPillNatureza`);
        if (pillNat && lblNat) {
          if (selectedNaturezas.size > 0) {
            pillNat.className = "px-2.5 py-1 rounded-lg text-xs font-semibold border flex items-center gap-1.5 transition shrink-0 bg-indigo-500/20 text-indigo-300 border-indigo-500/40 shadow-sm";
            if (selectedNaturezas.size === 1) {
              const natVal = Array.from(selectedNaturezas)[0];
              lblNat.innerText = formatShortNature(natVal);
              lblNat.title = natVal;
            } else {
              lblNat.innerText = `Nível (${selectedNaturezas.size})`;
              lblNat.title = Array.from(selectedNaturezas).map(formatShortNature).join(', ');
            }
            if (chevNat) chevNat.classList.add('hidden');
            if (clrNat) clrNat.classList.remove('hidden');
          } else {
            pillNat.className = "px-2.5 py-1 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition shrink-0 bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-800";
            lblNat.innerText = "Nível";
            lblNat.title = "Filtrar por nível ou natureza acadêmica";
            if (chevNat) chevNat.classList.remove('hidden');
            if (clrNat) clrNat.classList.add('hidden');
          }
        }

        // 3. Pílula: Instituição / Emissor (Faculdade, Banco, Órgão - Visível após selecionar TAG)
        const contInst = document.getElementById(`${p}containerFilterInstituicao`);
        if (contInst) {
          if (shouldShowInstituicao) contInst.classList.remove('hidden');
          else contInst.classList.add('hidden');
        }
        const pillInst = document.getElementById(`${p}pillInstituicao`);
        const lblInst = document.getElementById(`${p}labelPillInstituicao`);
        const chevInst = document.getElementById(`${p}chevronPillInstituicao`);
        const clrInst = document.getElementById(`${p}clearPillInstituicao`);
        const iconInst = document.getElementById(`${p}iconPillInstituicao`);
        if (iconInst) {
          iconInst.className = instIconClass;
        }
        if (pillInst && lblInst) {
          if (selectedInstituicoes.size > 0) {
            pillInst.className = "px-2.5 py-1 rounded-lg text-xs font-semibold border flex items-center gap-1.5 transition shrink-0 bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm";
            if (selectedInstituicoes.size === 1) {
              const instVal = Array.from(selectedInstituicoes)[0];
              const shortName = instVal.length > 14 ? instVal.substring(0, 12) + '...' : instVal;
              lblInst.innerText = shortName;
              lblInst.title = instVal;
            } else {
              lblInst.innerText = `${instLabelDefault} (${selectedInstituicoes.size})`;
              lblInst.title = Array.from(selectedInstituicoes).join(', ');
            }
            if (chevInst) chevInst.classList.add('hidden');
            if (clrInst) clrInst.classList.remove('hidden');
          } else {
            pillInst.className = "px-2.5 py-1 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition shrink-0 bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-800";
            lblInst.innerText = instLabelDefault;
            lblInst.title = instTitleDefault;
            if (chevInst) chevInst.classList.remove('hidden');
            if (clrInst) clrInst.classList.add('hidden');
          }
        }

        // 4. Pílula: Pendentes / Status (antes de limpar)
        const pillStat = document.getElementById(`${p}pillStatus`);
        const lblStat = document.getElementById(`${p}labelPillStatus`);
        const chevStat = document.getElementById(`${p}chevronPillStatus`);
        const clrStat = document.getElementById(`${p}clearPillStatus`);
        if (pillStat && lblStat) {
          if (selectedStatus.size > 0) {
            pillStat.className = "px-2.5 py-1 rounded-lg text-xs font-semibold border flex items-center gap-1.5 transition shrink-0 bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm";
            if (selectedStatus.size === 1) {
              const stVal = Array.from(selectedStatus)[0];
              const sMap = { 'pendente': 'Pendentes', 'aprovado': 'Aprovados', 'dossies': 'Dossiês (+2)', 'nao_processado': 'Não Lidos' };
              lblStat.innerText = sMap[stVal] || stVal;
            } else {
              lblStat.innerText = `Pendentes (${selectedStatus.size})`;
            }
            if (chevStat) chevStat.classList.add('hidden');
            if (clrStat) clrStat.classList.remove('hidden');
          } else {
            pillStat.className = "px-2.5 py-1 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition shrink-0 bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-800";
            lblStat.innerText = "Pendentes";
            lblStat.title = "Filtrar por pendentes ou status de conferência";
            if (chevStat) chevStat.classList.remove('hidden');
            if (clrStat) clrStat.classList.add('hidden');
          }
        }

        // 5. Pílula: Formato (PDF, Word, Imagens, Texto)
        const pillFmt = document.getElementById(`${p}pillFormato`);
        const lblFmt = document.getElementById(`${p}labelPillFormato`);
        const chevFmt = document.getElementById(`${p}chevronPillFormato`);
        const clrFmt = document.getElementById(`${p}clearPillFormato`);
        if (pillFmt && lblFmt) {
          if (selectedFormatos.size > 0) {
            pillFmt.className = "px-2.5 py-1 rounded-lg text-xs font-semibold border flex items-center gap-1.5 transition shrink-0 bg-sky-500/20 text-sky-300 border-sky-500/40 shadow-sm";
            if (selectedFormatos.size === 1) {
              const fmtVal = Array.from(selectedFormatos)[0];
              const fMap = { 'pdf': 'PDF', 'word': 'Word / Docs', 'image': 'Imagens', 'text': 'Texto Puro' };
              lblFmt.innerText = fMap[fmtVal] || fmtVal;
            } else {
              lblFmt.innerText = `Formato (${selectedFormatos.size})`;
            }
            if (chevFmt) chevFmt.classList.add('hidden');
            if (clrFmt) clrFmt.classList.remove('hidden');
          } else {
            pillFmt.className = "px-2.5 py-1 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition shrink-0 bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-800";
            lblFmt.innerText = "Formato";
            lblFmt.title = "Filtrar por formato do arquivo";
            if (chevFmt) chevFmt.classList.remove('hidden');
            if (clrFmt) clrFmt.classList.add('hidden');
          }
        }

        // 6. Botão Limpar Tudo (aparece se houver algum filtro ativo)
        const btnClearAll = document.getElementById(`${p}btnClearAllFilters`);
        if (btnClearAll) {
          const hasAnyActive = (
            selectedDominios.size > 0 ||
            selectedInstituicoes.size > 0 ||
            selectedTipos.size > 0 ||
            selectedNaturezas.size > 0 ||
            selectedStatus.size > 0 ||
            selectedFormatos.size > 0
          );
          if (hasAnyActive) {
            btnClearAll.classList.remove('hidden');
            btnClearAll.classList.add('flex');
          } else {
            btnClearAll.classList.add('hidden');
            btnClearAll.classList.remove('flex');
          }
        }
      });
    }

    function updateAccordionBadges() {
      updateFilterPillsUI();
    }

    // Visões Rápidas (Quick Views)
    function setQuickView(viewName) {
      activeQuickView = viewName;
      updateQuickViewUI();

      if (viewName === 'todos') {
        resetAllFilters();
        return;
      }
      if (viewName === 'dossies') {
        applyFilter(true);
        return;
      }
      if (viewName === 'pendentes') {
        selectedStatus.clear();
        selectedStatus.add('pendente');
        syncActiveFilterVars();
        applyFilter(true);
        return;
      }
      if (viewName === 'cursos') {
        selectedDominios.clear();
        selectedDominios.add('academico');
        syncActiveFilterVars();
        applyFilter(true);
        return;
      }
      if (viewName === 'financeiro') {
        selectedDominios.clear();
        selectedDominios.add('financeiro');
        syncActiveFilterVars();
        applyFilter(true);
        return;
      }
      if (viewName === 'identificacao') {
        selectedDominios.clear();
        selectedDominios.add('identificacao');
        syncActiveFilterVars();
        applyFilter(true);
        return;
      }
      if (viewName === 'nao_processado') {
        selectedStatus.clear();
        selectedStatus.add('nao_processado');
        syncActiveFilterVars();
        applyFilter(true);
        return;
      }
    }

    function updateQuickViewUI() {
      const qvIds = ['todos', 'dossies', 'pendentes', 'cursos', 'financeiro', 'identificacao', 'nao_processado'];
      qvIds.forEach(id => {
        ['qv-', 'gqv-'].forEach(prefix => {
          const btn = document.getElementById(`${prefix}${id}`);
          if (!btn) return;
          if (id === activeQuickView) {
            btn.className = "px-2.5 py-1 rounded-full font-medium shrink-0 transition flex items-center gap-1 border bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm";
          } else {
            btn.className = "px-2.5 py-1 rounded-full font-medium shrink-0 transition flex items-center gap-1 border bg-slate-900 hover:bg-slate-800 text-slate-400 border-slate-800";
          }
        });
      });
    }

    // Verificação unificada de filtros para consistência de facetas e seleção
    function docMatchesFilters(doc, rawSearch = '', exclude = '') {
      if (activeQuickView === 'dossies' && exclude !== 'status') {
        const pgs = Array.isArray(doc.dossie_paginas) ? doc.dossie_paginas.length : 0;
        const tipos = Array.isArray(doc.todos_tipos) ? doc.todos_tipos.length : 0;
        if (pgs < 2 && tipos < 2) return false;
      }

      if (exclude !== 'status' && selectedStatus.size > 0) {
        const isUnproc = isDocumentUnprocessed(doc);
        const isAppr = !isUnproc && safeString(doc.status_conferencia || 'pendente').toLowerCase() === 'aprovado';
        const isPend = !isUnproc && !isAppr;
        const pgs = Array.isArray(doc.dossie_paginas) ? doc.dossie_paginas.length : 0;
        const tipos = Array.isArray(doc.todos_tipos) ? doc.todos_tipos.length : 0;
        const isDossie = (pgs >= 2 || tipos >= 2);

        let match = false;
        if (selectedStatus.has('nao_processado') && isUnproc) match = true;
        if (selectedStatus.has('pendente') && isPend) match = true;
        if (selectedStatus.has('aprovado') && isAppr) match = true;
        if (selectedStatus.has('dossies') && isDossie) match = true;
        if (!match) return false;
      }

      if (exclude !== 'instituicao' && selectedInstituicoes.size > 0) {
        const fac = safeString(doc.faculdade).trim().toLowerCase();
        if (!Array.from(selectedInstituicoes).some(s => s.toLowerCase() === fac)) return false;
      }

      if (exclude !== 'tipo' && selectedTipos.size > 0) {
        const tipos = getDocAllTiposSet(doc);
        const tiposLower = new Set(Array.from(tipos).map(t => t.toLowerCase()));

        const matchesAnyTag = Array.from(selectedTipos).some(st => {
          const macro = MACRO_TAGS.find(m => m.id === st || m.label.toLowerCase() === st.toLowerCase());
          if (macro) {
            return macro.matchDoc(doc, tipos);
          }
          return tiposLower.has(st.toLowerCase());
        });

        if (!matchesAnyTag) return false;
      }

      if (exclude !== 'natureza' && selectedNaturezas.size > 0) {
        const docNat = safeString(doc.natureza_curso).trim();
        if (!Array.from(selectedNaturezas).some(sn => docNat === sn || classifyNatureza(docNat) === sn)) return false;
      }

      if (exclude !== 'formato' && selectedFormatos.size > 0) {
        const fmt = getDocFormatMeta(doc);
        if (!selectedFormatos.has(fmt.type)) return false;
      }

      return matchDocumentSearch(doc, rawSearch);
    }

    // Filtro de Instituição / Emissor (Multi-seleção por Tags)
    function updateInstituicaoFilterOptions() {
      const rawSearch = (document.getElementById('searchInput').value || '').trim();
      const instSearch = (document.getElementById('inputSearchInst') ? document.getElementById('inputSearchInst').value : '').trim().toLowerCase();

      const baseDocs = documents.filter(doc => docMatchesFilters(doc, rawSearch, 'instituicao'));

      const counts = {};
      baseDocs.forEach(d => {
        const fac = safeString(d.faculdade).trim();
        if (fac) counts[fac] = (counts[fac] || 0) + 1;
      });

      const sorted = Object.keys(counts).sort((a, b) => {
        const diff = counts[b] - counts[a];
        if (diff !== 0) return diff;
        return a.localeCompare(b);
      });

      // Assegura que instituições já selecionadas apareçam na lista mesmo se com count 0
      selectedInstituicoes.forEach(selFac => {
        if (!sorted.includes(selFac)) sorted.push(selFac);
      });

      const select = document.getElementById('selectInstituicaoFilter');
      if (select) {
        select.innerHTML = `<option value="">Todas as Instituições (${baseDocs.length})</option>`;
        sorted.forEach(fac => {
          if (!instSearch || fac.toLowerCase().includes(instSearch)) {
            const opt = document.createElement('option');
            opt.value = fac;
            opt.innerText = `${fac} (${counts[fac] || 0})`;
            select.appendChild(opt);
          }
        });
        select.value = selectedInstituicoes.size === 1 ? Array.from(selectedInstituicoes)[0] : '';
      }

      const inpInst1 = document.getElementById('inputSearchInst');
      const inpInst2 = document.getElementById('g-inputSearchInst');
      const instSearch1 = inpInst1 ? inpInst1.value.trim().toLowerCase() : '';
      const instSearch2 = inpInst2 ? inpInst2.value.trim().toLowerCase() : '';

      // Nuvem de tags/chips no Popover
      ['instituicaoChips', 'g-instituicaoChips'].forEach(cid => {
        const chipsContainer = document.getElementById(cid);
        if (!chipsContainer) return;
        chipsContainer.innerHTML = '';
        const localSearch = cid === 'g-instituicaoChips' ? (instSearch2 || instSearch1) : (instSearch1 || instSearch2);
        let filteredFacs = sorted;
        if (localSearch) {
          filteredFacs = sorted.filter(fac => fac.toLowerCase().includes(localSearch));
        }

        if (filteredFacs.length === 0) {
          chipsContainer.innerHTML = '<span class="text-[11px] text-slate-500 italic p-2">Nenhuma instituição encontrada com este termo</span>';
        } else {
          filteredFacs.forEach(fac => {
            const isSelected = selectedInstituicoes.has(fac);
            const count = counts[fac] || 0;
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = `px-2 py-0.5 rounded-md text-[10.5px] font-medium border transition flex items-center gap-1.5 truncate max-w-[220px] ${
              isSelected
                ? 'bg-amber-600 text-white border-amber-500 font-semibold ring-1 ring-amber-400/50 shadow-sm'
                : (count === 0 
                    ? 'bg-slate-950/40 text-slate-500 border-slate-900/60 opacity-60 hover:opacity-90 hover:text-slate-300' 
                    : 'bg-slate-950/70 text-slate-300 border-slate-800 hover:bg-slate-800/80 hover:text-amber-300')
            }`;
            chip.title = `${fac} (${count} documentos)`;
            chip.innerHTML = `
              <span class="truncate">${fac}</span>
              <span class="text-[9.5px] px-1.5 py-0.2 rounded-full font-mono shrink-0 ${isSelected ? 'bg-amber-950/70 text-amber-200' : 'bg-slate-800 text-slate-400'}">${count}</span>
            `;
            chip.onclick = () => {
              toggleInstituicaoFilter(fac);
            };
            chipsContainer.appendChild(chip);
          });
        }
      });

      ['btnClearInstituicao', 'g-btnClearInstituicao'].forEach(bid => {
        const btnClear = document.getElementById(bid);
        if (btnClear) {
          if (selectedInstituicoes.size > 0) btnClear.classList.remove('hidden');
          else btnClear.classList.add('hidden');
        }
      });
    }

    function toggleInstituicaoFilter(fac) {
      if (selectedInstituicoes.has(fac)) {
        selectedInstituicoes.delete(fac);
      } else {
        selectedInstituicoes.add(fac);
      }
      syncActiveFilterVars();
      applyFilter(false);
    }

    function setInstituicaoFilter(inst) {
      selectedInstituicoes.clear();
      if (inst) selectedInstituicoes.add(inst);
      syncActiveFilterVars();
      applyFilter(false);
    }

    function resetInstituicaoFilter() {
      selectedInstituicoes.clear();
      syncActiveFilterVars();
      ['inputSearchInst', 'g-inputSearchInst'].forEach(id => {
        const input = document.getElementById(id);
        if (input) input.value = '';
      });
      applyFilter(false);
    }

    function onInstituicaoSelectChange() {
      const val = (document.getElementById('selectInstituicaoFilter').value || '').trim();
      setInstituicaoFilter(val);
    }

    function onInstSearchInput() {
      updateInstituicaoFilterOptions();
    }

    // Seleção Múltipla & Ações em Lote (Bulk Actions)
    function toggleSelectDoc(md5, isChecked) {
      if (isChecked) {
        selectedMd5s.add(md5);
      } else {
        selectedMd5s.delete(md5);
      }
      updateBulkUI();
      updateSidebarSelection();
    }

    function toggleSelectAllFiltered(isChecked) {
      if (isChecked) {
        filteredDocs.forEach(d => {
          if (d && d.md5) selectedMd5s.add(d.md5);
        });
      } else {
        filteredDocs.forEach(d => {
          if (d && d.md5) selectedMd5s.delete(d.md5);
        });
      }
      updateBulkUI();
      renderSidebar();
    }

    function clearBulkSelection() {
      selectedMd5s.clear();
      updateBulkUI();
      renderSidebar();
    }

    function updateBulkUI() {
      const count = selectedMd5s.size;
      const bar = document.getElementById('floatingBulkBar');
      const countEl = document.getElementById('bulkCountSelected');
      const chkMaster = document.getElementById('chkSelectAllFiltered');

      if (countEl) countEl.innerText = count;

      if (bar) {
        if (count > 0) {
          bar.classList.remove('hidden');
        } else {
          bar.classList.add('hidden');
        }
      }

      if (chkMaster) {
        const totalVisible = filteredDocs.length;
        if (totalVisible === 0) {
          chkMaster.checked = false;
          chkMaster.indeterminate = false;
        } else {
          const visibleSelectedCount = filteredDocs.filter(d => selectedMd5s.has(d.md5)).length;
          if (visibleSelectedCount === totalVisible) {
            chkMaster.checked = true;
            chkMaster.indeterminate = false;
          } else if (visibleSelectedCount > 0) {
            chkMaster.checked = false;
            chkMaster.indeterminate = true;
          } else {
            chkMaster.checked = false;
            chkMaster.indeterminate = false;
          }
        }
      }
    }

