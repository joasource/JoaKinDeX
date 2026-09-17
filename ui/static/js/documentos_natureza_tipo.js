    async function loadDocuments() {
      try {
        // Carrega metadados de pastas do servidor
        fetch('/api/info')
          .then(r => {
            if (!r.ok) throw new Error(`Status ${r.status}`);
            return r.json();
          })
          .then(info => {
            if (!info) return;
            const badgeEl = document.getElementById('serverInfoBadge');
            const textEl = document.getElementById('serverInfoText');
            if (badgeEl && textEl) {
              const shortPdf = info.pdf_dir.length > 24 ? '...' + info.pdf_dir.slice(-21) : info.pdf_dir;
              textEl.innerText = `${shortPdf} (${info.pdf_count} PDFs) • ${info.json_name}`;
              badgeEl.title = `PDFs: ${info.pdf_dir} (${info.pdf_count} indexados)\nJSON: ${info.json_path}`;
            }
          })
          .catch(err => {
            console.warn('Metadados /api/info não puderam ser carregados:', err);
            const textEl = document.getElementById('serverInfoText');
            if (textEl) textEl.innerText = 'Servidor Local Conectado';
          });

        const response = await fetch('/api/documentos');
        const rawDocs = await response.json();
        documents = (rawDocs || []).map(doc => {
          if (doc && typeof doc === 'object') {
            delete doc.data_criacao;
            if (!doc.dominio) doc.dominio = 'academico';
            if (!doc.todos_tipos || !Array.isArray(doc.todos_tipos)) {
              doc.todos_tipos = doc.tipo_documento ? [doc.tipo_documento] : [];
            }
            if (!doc.todos_dominios || !Array.isArray(doc.todos_dominios)) {
              doc.todos_dominios = doc.dominio ? [doc.dominio] : [];
            }
            if (!doc.dossie_paginas || !Array.isArray(doc.dossie_paginas)) {
              doc.dossie_paginas = [];
            }
          }
          return doc;
        });
        
        initMasterFilterLists();
        applyFilter(false);
        if (typeof currentMainTab !== 'undefined' && currentMainTab === 'bi') {
          renderBIDashboard();
        }
      } catch (err) {
        console.error('Erro ao carregar documentos:', err);
        showToast('Erro ao carregar documentos: ' + err.message, 'error');
        const textEl = document.getElementById('serverInfoText');
        if (textEl) textEl.innerText = 'Falha ao conectar ao servidor';

        const listEl = document.getElementById('docList');
        if (listEl) {
          listEl.innerHTML = `
            <div class="text-center py-10 px-4 text-xs text-rose-400 space-y-2">
              <i class="fa-solid fa-triangle-exclamation text-2xl text-rose-500"></i>
              <p class="font-semibold text-slate-200">Erro ao carregar os documentos</p>
              <p class="text-[11px] text-slate-400">${err.message}</p>
              <div class="pt-2">
                <button onclick="loadDocuments()" class="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs transition">
                  Tentar novamente
                </button>
              </div>
            </div>
          `;
        }
      }
    }

    // Listas mestres com todas as opções presentes no dataset
    let allUniqueNaturezas = [];
    let allUniqueTipos = [];

    function initMasterFilterLists() {
      const natSet = new Set();
      const tipoSet = new Set();
      const instSet = new Set();

      documents.forEach(d => {
        const nat = safeString(d.natureza_curso).trim();
        natSet.add(nat || 'Não identificada');

        const fac = safeString(d.faculdade).trim();
        if (fac) instSet.add(fac);

        if (!Array.isArray(d.todos_tipos)) d.todos_tipos = [];
        const mainTipo = safeString(d.tipo_documento).trim();
        if (mainTipo) {
          tipoSet.add(mainTipo);
          if (!d.todos_tipos.includes(mainTipo)) d.todos_tipos.push(mainTipo);
        }

        d.todos_tipos.forEach(t => {
          const cleanT = safeString(t).trim();
          if (cleanT) tipoSet.add(cleanT);
        });

        if (Array.isArray(d.dossie_paginas)) {
          d.dossie_paginas.forEach(p => {
            const cleanT = safeString(p.tipo).trim();
            if (cleanT) {
              tipoSet.add(cleanT);
              if (!d.todos_tipos.includes(cleanT)) d.todos_tipos.push(cleanT);
            }
          });
        }
      });

      if (tipoSet.size === 0) tipoSet.add('Não identificado');

      allUniqueNaturezas = Array.from(natSet);
      allUniqueTipos = Array.from(tipoSet).sort((a, b) => a.localeCompare(b));
      allUniqueInstituicoes = Array.from(instSet).sort((a, b) => a.localeCompare(b));
    }

    function updateFacetFilters() {
      updateInstituicaoFilterOptions();
      updateTipoFilterOptions();
      updateNaturezaFilterOptions();
      updateStatusFilterOptions();
      updateFormatoFilterOptions();
      updateFilterPillsUI();
    }

    // Calcula e atualiza dinamicamente as opções e tags de Natureza do Curso (Multi-seleção)
    function updateNaturezaFilterOptions() {
      const rawSearch = (document.getElementById('searchInput').value || '').trim();
      const baseDocs = documents.filter(doc => docMatchesFilters(doc, rawSearch, 'natureza'));

      const counts = {};
      baseDocs.forEach(d => {
        const nat = safeString(d.natureza_curso).trim() || 'Não identificada';
        counts[nat] = (counts[nat] || 0) + 1;
      });

      const totalMatching = baseDocs.length;

      const select = document.getElementById('selectNaturezaFilter');
      if (select) {
        select.innerHTML = `<option value="">Todas as Naturezas (${totalMatching})</option>`;
        const sortedNats = [...allUniqueNaturezas].sort((a, b) => {
          const diff = (counts[b] || 0) - (counts[a] || 0);
          if (diff !== 0) return diff;
          return a.localeCompare(b);
        });

        sortedNats.forEach(nat => {
          const count = counts[nat] || 0;
          const opt = document.createElement('option');
          opt.value = nat;
          opt.innerText = `${nat} (${count})`;
          select.appendChild(opt);
        });
        select.value = selectedNaturezas.size === 1 ? Array.from(selectedNaturezas)[0] : '';
      }

      // Nuvem de tags/chips no Popover de Natureza
      ['naturezaChips', 'g-naturezaChips'].forEach(cid => {
        const chipsContainer = document.getElementById(cid);
        if (!chipsContainer) return;
        chipsContainer.innerHTML = '';
        const sortedNats = [...allUniqueNaturezas].sort((a, b) => {
          const diff = (counts[b] || 0) - (counts[a] || 0);
          if (diff !== 0) return diff;
          return a.localeCompare(b);
        });

        selectedNaturezas.forEach(selNat => {
          if (!sortedNats.includes(selNat)) sortedNats.push(selNat);
        });

        sortedNats.forEach(nat => {
          const count = counts[nat] || 0;
          const isSelected = selectedNaturezas.has(nat);
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.className = `px-2 py-0.5 rounded-md text-[10.5px] font-medium border transition flex items-center gap-1.5 truncate max-w-[210px] ${
            isSelected
              ? 'bg-indigo-600 text-white border-indigo-500 font-semibold ring-1 ring-indigo-400/50 shadow-sm'
              : (count === 0 
                  ? 'bg-slate-950/40 text-slate-500 border-slate-900/60 opacity-60 hover:opacity-90 hover:text-slate-300' 
                  : 'bg-slate-950/70 text-slate-300 border-slate-800 hover:bg-slate-800/80 hover:text-indigo-300')
          }`;
          chip.title = `${nat} (${count} documentos)`;
          chip.innerHTML = `
            <span class="truncate">${formatShortNature(nat)}</span>
            <span class="text-[9.5px] px-1.5 py-0.2 rounded-full font-mono shrink-0 ${isSelected ? 'bg-indigo-950/70 text-indigo-200' : 'bg-slate-800 text-slate-400'}">${count}</span>
          `;
          chip.onclick = () => {
            toggleNaturezaFilter(nat);
          };
          chipsContainer.appendChild(chip);
        });
      });

      ['btnClearNatureza', 'g-btnClearNatureza'].forEach(bid => {
        const btnClear = document.getElementById(bid);
        if (btnClear) {
          if (selectedNaturezas.size > 0) btnClear.classList.remove('hidden');
          else btnClear.classList.add('hidden');
        }
      });
    }

    function toggleNaturezaFilter(nat) {
      if (selectedNaturezas.has(nat)) {
        selectedNaturezas.delete(nat);
      } else {
        selectedNaturezas.add(nat);
      }
      syncActiveFilterVars();
      applyFilter(false);
    }

    function setNaturezaFilter(nat) {
      selectedNaturezas.clear();
      if (nat) selectedNaturezas.add(nat);
      syncActiveFilterVars();
      applyFilter(false);
    }

    function resetNaturezaFilter() {
      selectedNaturezas.clear();
      syncActiveFilterVars();
      applyFilter(false);
    }

    function formatShortNature(nat) {
      const s = safeString(nat);
      if (s.includes('Pós-Graduação Lato Sensu')) return 'Pós Lato Sensu';
      if (s.includes('Pós-Graduação Stricto Sensu')) return 'Pós Stricto Sensu';
      if (s.includes('Graduação')) return 'Graduação';
      if (s.includes('Técnico')) return 'Curso Técnico';
      if (s.includes('Extensão')) return 'Extensão';
      return s || 'Não identificada';
    }

    function getChipColorClass(nat, isActive, count = 1) {
      if (isActive) {
        return 'bg-indigo-600 text-white border-indigo-500 shadow-sm font-semibold ring-1 ring-indigo-400/50';
      }
      if (count === 0) {
        return 'bg-slate-950/40 text-slate-500 border-slate-900/60 opacity-50 hover:opacity-90 hover:text-slate-300';
      }
      const n = normalizeText(nat);
      if (n.includes('graduacao') || n.includes('superior')) {
        return 'bg-purple-950/40 text-purple-300 border-purple-800/60 hover:bg-purple-900/50';
      }
      if (n.includes('lato sensu') || n.includes('especializacao')) {
        return 'bg-sky-950/40 text-sky-300 border-sky-800/60 hover:bg-sky-900/50';
      }
      if (n.includes('stricto sensu') || n.includes('mestrado')) {
        return 'bg-emerald-950/40 text-emerald-300 border-emerald-800/60 hover:bg-emerald-900/50';
      }
      if (n.includes('tecnico')) {
        return 'bg-amber-950/40 text-amber-300 border-amber-800/60 hover:bg-amber-900/50';
      }
      return 'bg-slate-900 text-slate-300 border-slate-800 hover:bg-slate-800';
    }

    function onNaturezaSelectChange() {
      const val = document.getElementById('selectNaturezaFilter').value;
      setNaturezaFilter(val);
    }

    // Helper para metadados visuais das TAGs (Ícones, Cores semânticas e Categorias unificadas)
    function getTagMeta(tipo) {
      if (!tipo) {
        return { 
          icon: 'fa-solid fa-tag', 
          color: 'text-slate-400', 
          bg: 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800 hover:border-slate-700', 
          activeBg: 'bg-teal-600 border-teal-400 text-white', 
          category: 'Outros' 
        };
      }

      // 1. Verificação de Macro-TAGs
      const macro = MACRO_TAGS.find(m => m.id === tipo || m.label.toLowerCase() === tipo.toLowerCase());
      if (macro) {
        return {
          icon: macro.icon,
          color: `text-${macro.color}-400`,
          bg: macro.bg,
          activeBg: macro.activeBg,
          category: macro.category
        };
      }

      const t = normalizeText(tipo || '');

      // 2. CNPJ / Comprovante de Inscrição e Situação Cadastral (Receita Federal)
      if (t.includes('cnpj') || t.includes('situacao cadastral') || t.includes('receita federal') || t.includes('cartao cnpj') || t.includes('inscricao cadastral')) {
        return {
          icon: 'fa-solid fa-building',
          color: 'text-teal-400',
          bg: 'bg-teal-950/40 border-teal-800/70 text-teal-200 hover:bg-teal-900/50 hover:border-teal-500',
          activeBg: 'bg-teal-600 border-teal-400 text-white',
          category: 'Carreira & Profissional'
        };
      }

      // 3. Carreira & Profissional (Currículo, Lattes, Experiência, Carteira de Trabalho)
      if (t.includes('curriculo') || t.includes('experiencia profissional') || t.includes('lattes') || t.includes('carteira de trabalho') || t.includes('ctps') || t.includes('registro profissional')) {
        return {
          icon: 'fa-solid fa-briefcase',
          color: 'text-sky-400',
          bg: 'bg-sky-950/40 border-sky-800/70 text-sky-200 hover:bg-sky-900/50 hover:border-sky-500',
          activeBg: 'bg-sky-600 border-sky-400 text-white',
          category: 'Carreira & Profissional'
        };
      }

      // 3. PIX
      if (t.includes('pix')) {
        return { 
          icon: 'fa-brands fa-pix', 
          color: 'text-emerald-400', 
          bg: 'bg-emerald-950/40 border-emerald-800/70 text-emerald-200 hover:bg-emerald-900/50 hover:border-emerald-500', 
          activeBg: 'bg-emerald-600 border-emerald-400 text-white', 
          category: 'Financeiro' 
        };
      }

      // 3.1 Cheque / Talão de Cheques
      if (t.includes('cheque') || t.includes('talao')) {
        return { 
          icon: 'fa-solid fa-money-check-dollar', 
          color: 'text-emerald-400', 
          bg: 'bg-emerald-950/40 border-emerald-800/70 text-emerald-200 hover:bg-emerald-900/50 hover:border-emerald-500', 
          activeBg: 'bg-emerald-600 border-emerald-400 text-white', 
          category: 'Financeiro' 
        };
      }

      // 3.2 Imposto de Renda / IRPF / Declaração de Ajuste Anual / Recibo de Entrega
      if (t.includes('imposto de renda') || t.includes('irpf') || t.includes('ajuste anual') || (t.includes('recibo') && t.includes('entrega'))) {
        return { 
          icon: 'fa-solid fa-file-invoice-dollar', 
          color: 'text-emerald-400', 
          bg: 'bg-emerald-950/40 border-emerald-800/70 text-emerald-200 hover:bg-emerald-900/50 hover:border-emerald-500', 
          activeBg: 'bg-emerald-600 border-emerald-400 text-white', 
          category: 'Financeiro' 
        };
      }

      // 3.3 Informe de Rendimentos Financeiros
      if (t.includes('informe de rendimentos') || t.includes('comprovante de rendimentos') || t.includes('rendimentos financeiros')) {
        return { 
          icon: 'fa-solid fa-chart-line', 
          color: 'text-emerald-400', 
          bg: 'bg-emerald-950/40 border-emerald-800/70 text-emerald-200 hover:bg-emerald-900/50 hover:border-emerald-500', 
          activeBg: 'bg-emerald-600 border-emerald-400 text-white', 
          category: 'Financeiro' 
        };
      }

      // 4. Financeiro (Recibo, Comprovante, Boleto, Pagamento, Transferência, Extrato, Nota Fiscal)
      if (t.includes('recibo') || t.includes('comprovante') || t.includes('boleto') || t.includes('pagamento') || t.includes('financeir') || t.includes('banc') || t.includes('extrato') || t.includes('nota fiscal') || t.includes('fatura')) {
        return { 
          icon: 'fa-solid fa-receipt', 
          color: 'text-emerald-400', 
          bg: 'bg-emerald-950/40 border-emerald-800/70 text-emerald-200 hover:bg-emerald-900/50 hover:border-emerald-500', 
          activeBg: 'bg-emerald-600 border-emerald-400 text-white', 
          category: 'Financeiro' 
        };
      }

      // 5. Identidade / Pessoal (RG, CNH, CPF, Certidão, Título, Passaporte, Carteira)
      if (t === 'rg' || t === 'cpf' || t === 'cnh' || t.includes('rg') || t.includes('cnh') || t.includes('cpf') || t.includes('identidad') || t.includes('certidao') || t.includes('passaporte') || t.includes('titulo') || t.includes('eleitor') || t.includes('civis') || t.includes('reservista') || t.includes('habilitacao') || t.includes('nascimento')) {
        return { 
          icon: 'fa-solid fa-id-card', 
          color: 'text-purple-400', 
          bg: 'bg-purple-950/40 border-purple-800/70 text-purple-200 hover:bg-purple-900/50 hover:border-purple-500', 
          activeBg: 'bg-purple-600 border-purple-400 text-white', 
          category: 'Identificação & Pessoal' 
        };
      }

      // 6. Diploma
      if (t.includes('diploma')) {
        return { 
          icon: 'fa-solid fa-graduation-cap', 
          color: 'text-cyan-400', 
          bg: 'bg-cyan-950/40 border-cyan-800/70 text-cyan-200 hover:bg-cyan-900/50 hover:border-cyan-500', 
          activeBg: 'bg-cyan-600 border-cyan-400 text-white', 
          category: 'Produtos Acadêmicos' 
        };
      }

      // 7. Certificado
      if (t.includes('certificado')) {
        return { 
          icon: 'fa-solid fa-award', 
          color: 'text-teal-400', 
          bg: 'bg-teal-950/40 border-teal-800/70 text-teal-200 hover:bg-teal-900/50 hover:border-teal-500', 
          activeBg: 'bg-teal-600 border-teal-400 text-white', 
          category: 'Produtos Acadêmicos' 
        };
      }

      // 8. Histórico escolar / universitário
      if (t.includes('historico')) {
        return { 
          icon: 'fa-solid fa-book-open', 
          color: 'text-blue-400', 
          bg: 'bg-blue-950/40 border-blue-800/70 text-blue-200 hover:bg-blue-900/50 hover:border-blue-500', 
          activeBg: 'bg-blue-600 border-blue-400 text-white', 
          category: 'Produtos Acadêmicos' 
        };
      }

      // 9. Declaração / Atestado / Matrícula
      if (t.includes('declaracao') || t.includes('atestado') || t.includes('matricula') || t.includes('frequencia') || t.includes('conclusao')) {
        return { 
          icon: 'fa-solid fa-file-lines', 
          color: 'text-sky-400', 
          bg: 'bg-sky-950/40 border-sky-800/70 text-sky-200 hover:bg-sky-900/50 hover:border-sky-500', 
          activeBg: 'bg-sky-600 border-sky-400 text-white', 
          category: 'Produtos Acadêmicos' 
        };
      }

      // 10. Dissertação / Livro / Publicação
      if (t.includes('dissertacao') || t.includes('livro') || t.includes('publicacao') || t.includes('artigo') || t.includes('tcc') || t.includes('tese')) {
        return {
          icon: 'fa-solid fa-book-bookmark',
          color: 'text-amber-400',
          bg: 'bg-amber-950/40 border-amber-800/70 text-amber-200 hover:bg-amber-900/50 hover:border-amber-500',
          activeBg: 'bg-amber-600 border-amber-400 text-white',
          category: 'Produtos Acadêmicos'
        };
      }

      // 11. Ementa / Conteúdo / Material Didático / Módulo Instrucional
      if (t.includes('ementa') || t.includes('conteudo') || t.includes('grade') || t.includes('plano') || t.includes('didatico') || t.includes('instrucional') || t.includes('modulo')) {
        return { 
          icon: 'fa-solid fa-list-check', 
          color: 'text-indigo-400', 
          bg: 'bg-indigo-950/40 border-indigo-800/70 text-indigo-200 hover:bg-indigo-900/50 hover:border-indigo-500', 
          activeBg: 'bg-indigo-600 border-indigo-400 text-white', 
          category: 'Produtos Acadêmicos' 
        };
      }

      // 12. Jurídico / Contrato / Portaria / Procuração / Resolução
      if (t.includes('contrat') || t.includes('convenio') || t.includes('responsabilidade') || t.includes('portaria') || t.includes('resolucao') || t.includes('diario oficial') || t.includes('procuracao') || t.includes('termo') || t.includes('estatuto')) {
        return { 
          icon: 'fa-solid fa-file-signature', 
          color: 'text-rose-400', 
          bg: 'bg-rose-950/40 border-rose-800/70 text-rose-200 hover:bg-rose-900/50 hover:border-rose-500', 
          activeBg: 'bg-rose-600 border-rose-400 text-white', 
          category: 'Jurídico & Normativo' 
        };
      }

      // 13. Processual / Administrativo (Recurso, Relatório, Cadastro)
      if (t.includes('recurso') || t.includes('relatorio') || t.includes('cadastro') || t.includes('preparatorio') || t.includes('promocional') || t.includes('processual') || t.includes('oficio') || t.includes('memorando')) {
        return { 
          icon: 'fa-solid fa-file-invoice', 
          color: 'text-indigo-400', 
          bg: 'bg-indigo-950/40 border-indigo-800/70 text-indigo-200 hover:bg-indigo-900/50 hover:border-indigo-500', 
          activeBg: 'bg-indigo-600 border-indigo-400 text-white', 
          category: 'Processual & Administrativo' 
        };
      }

      // 14. Dossiê / Multi-página
      if (t.includes('dossie') || t.includes('multi')) {
        return { 
          icon: 'fa-solid fa-folder-open', 
          color: 'text-cyan-400', 
          bg: 'bg-cyan-950/40 border-cyan-800/70 text-cyan-200 hover:bg-cyan-900/50 hover:border-cyan-500', 
          activeBg: 'bg-cyan-600 border-cyan-400 text-white', 
          category: 'Dossiê' 
        };
      }

      // Geral / Outros
      return { 
        icon: 'fa-solid fa-tag', 
        color: 'text-slate-400', 
        bg: 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800 hover:border-slate-700', 
        activeBg: 'bg-teal-600 border-teal-400 text-white', 
        category: getTagCategory(tipo) 
      };
    }

    // Extrai subtags contextuais (atributos filhos) da Tag Principal
    function getPrimaryTagSubtags(doc, primaryTag, docDom) {
      if (!doc) return [];
      const normTag = normalizeText(primaryTag || '');
      const subtags = [];
      const de = doc.dados_extras || {};

      const isCnpjDoc = normTag.includes('cnpj') || normTag.includes('cadastral') || Boolean(doc.cnpj || de.cnpj);
      if (isCnpjDoc && (docDom === 'profissional' || normTag.includes('cnpj') || normTag.includes('cadastral'))) {
        const cnpjVal = safeString(doc.cnpj || de.cnpj).trim();
        if (cnpjVal) subtags.push({ label: `CNPJ: ${cnpjVal}`, title: 'CNPJ', icon: 'fa-solid fa-id-card text-emerald-400' });

        const sit = safeString(de.situacao_cadastral || doc.situacao_cadastral).trim().toUpperCase();
        if (sit) {
          const isAtiva = sit.includes('ATIVA');
          const sitIcon = isAtiva ? 'fa-solid fa-circle-check text-emerald-400' : 'fa-solid fa-circle-xmark text-rose-400';
          subtags.push({ label: sit, title: `Situação: ${sit}`, icon: sitIcon });
        }

        const fantasia = safeString(de.nome_fantasia || doc.nome_fantasia).trim();
        if (fantasia) subtags.push({ label: fantasia, title: 'Nome Fantasia', icon: 'fa-solid fa-store text-sky-400' });

        const cnae = safeString(de.cnae_principal || doc.cnae_principal).trim();
        if (cnae) {
          const cnaeShort = cnae.length > 28 ? cnae.substring(0, 25) + '...' : cnae;
          subtags.push({ label: cnaeShort, title: `CNAE: ${cnae}`, icon: 'fa-solid fa-industry text-indigo-400' });
        }

        const end = safeString(de.endereco_completo || doc.endereco_completo).trim();
        if (end) {
          const mUf = end.match(/([A-ZÀ-Ú\s]+)\s*[-/]\s*([A-Z]{2})\b/i);
          const loc = mUf ? `${mUf[1].trim()} - ${mUf[2].toUpperCase()}` : (end.length > 24 ? end.substring(0, 21) + '...' : end);
          subtags.push({ label: loc, title: `Localização: ${end}`, icon: 'fa-solid fa-location-dot text-amber-400' });
        }
      } else if (docDom === 'profissional' || normTag.includes('curriculo') || normTag.includes('experiencia profissional')) {
        const cargo = safeString(doc.curso || doc.cargo || de.cargo || de.funcao).trim();
        if (cargo) subtags.push({ label: cargo, title: 'Cargo / Especialidade', icon: 'fa-solid fa-briefcase text-sky-400' });
        const empresa = safeString(doc.faculdade || doc.empresa || de.empresa).trim();
        if (empresa) subtags.push({ label: empresa, title: 'Empresa / Órgão', icon: 'fa-solid fa-building-user text-slate-400' });
      } else if (docDom === 'financeiro' || normTag.includes('pix') || normTag.includes('recibo') || normTag.includes('pagamento') || normTag.includes('boleto') || normTag.includes('cheque') || normTag.includes('talao')) {
        const val = safeString(doc.valor_monetario).trim();
        if (val) subtags.push({ label: val, title: 'Valor', icon: 'fa-solid fa-money-bill-wave text-emerald-400' });
        const numCheque = safeString(de.numero_cheque || doc.numero_cheque).trim();
        if (numCheque) subtags.push({ label: `Cheque Nº ${numCheque}`, title: 'Número do Cheque', icon: 'fa-solid fa-money-check-dollar text-cyan-400' });
        const banco = safeString(doc.faculdade || doc.pix_pagador_banco || de.pix_pagador_banco || de.banco_cheque).trim();
        if (banco) subtags.push({ label: banco, title: 'Instituição / Banco', icon: 'fa-solid fa-building-columns text-slate-400' });
        const conta = safeString(de.conta_corrente).trim();
        if (conta) subtags.push({ label: `C/C: ${conta}`, title: 'Conta Corrente', icon: 'fa-solid fa-wallet text-slate-400' });
        const serie = safeString(de.serie_cheque).trim();
        if (serie) subtags.push({ label: `Série: ${serie}`, title: 'Série do Cheque', icon: 'fa-solid fa-tag text-slate-400' });
        const chave = safeString(doc.pix_chave || de.pix_chave).trim();
        if (chave) subtags.push({ label: chave, title: 'Chave PIX', icon: 'fa-solid fa-key text-amber-400' });
      } else if (docDom === 'veicular' || normTag.includes('crv') || normTag.includes('crlv') || normTag.includes('atpv') || normTag.includes('veicular') || normTag.includes('veiculo') || normTag.includes('vistoria') || normTag.includes('remocao') || normTag.includes('arrematacao')) {
        const placa = safeString(doc.placa || de.placa).trim();
        if (placa) subtags.push({ label: `Placa: ${placa}`, title: 'Placa do Veículo', icon: 'fa-solid fa-car text-orange-400' });
        const renavam = safeString(doc.renavam || de.renavam).trim();
        if (renavam) subtags.push({ label: `Renavam: ${renavam}`, title: 'Código Renavam', icon: 'fa-solid fa-barcode text-amber-400' });
        const chassi = safeString(doc.chassi || de.chassi).trim();
        if (chassi) subtags.push({ label: `Chassi: ${chassi}`, title: 'Chassi do Veículo', icon: 'fa-solid fa-hashtag text-slate-400' });
        const mm = safeString(doc.curso || de.marca_modelo).trim();
        if (mm) subtags.push({ label: mm, title: 'Marca / Modelo', icon: 'fa-solid fa-car-side text-cyan-400' });
        const emissor = safeString(doc.faculdade || de.orgao_transito).trim();
        if (emissor) subtags.push({ label: emissor, title: 'Órgão de Trânsito', icon: 'fa-solid fa-shield-halved text-teal-400' });
      } else if (docDom === 'identificacao' || normTag.includes('cnh') || normTag.includes('rg') || normTag.includes('cpf') || normTag.includes('identidad') || normTag.includes('certidao')) {
        const emissor = safeString(doc.faculdade || doc.orgao_emissor).trim();
        if (emissor) subtags.push({ label: emissor, title: 'Órgão Emissor', icon: 'fa-solid fa-building-shield text-cyan-400' });
        const rg = safeString(doc.rg).trim();
        if (rg) subtags.push({ label: `RG: ${rg}`, title: 'RG', icon: 'fa-regular fa-id-card text-slate-400' });
        const cpf = safeString(doc.cpf).trim();
        if (cpf) subtags.push({ label: `CPF: ${cpf}`, title: 'CPF', icon: 'fa-solid fa-fingerprint text-slate-400' });
      } else if (docDom === 'juridico' || normTag.includes('contrato') || normTag.includes('procuracao') || normTag.includes('termo')) {
        const obj = safeString(doc.curso || doc.natureza_curso).trim();
        if (obj) subtags.push({ label: obj, title: 'Objeto / Tipo', icon: 'fa-solid fa-file-signature text-amber-400' });
        const emissor = safeString(doc.faculdade || doc.cartorio || doc.vara).trim();
        if (emissor) subtags.push({ label: emissor, title: 'Órgão / Cartório / Empresa', icon: 'fa-solid fa-scale-balanced text-purple-400' });
      } else {
        // Acadêmico (Diplomas, Certificados, Cursos)
        const curso = safeString(doc.curso).trim();
        if (curso) subtags.push({ label: curso, title: 'Curso', icon: 'fa-solid fa-book-open text-cyan-400' });
        const nat = safeString(doc.natureza_curso).trim();
        if (nat) subtags.push({ label: formatShortNature(nat), title: `Nível: ${nat}`, icon: 'fa-solid fa-award text-amber-400' });
        const fac = safeString(doc.faculdade).trim();
        if (fac) subtags.push({ label: fac, title: 'Instituição de Ensino', icon: 'fa-solid fa-building-columns text-slate-400' });
        const ch = safeString(doc.carga_horaria).trim();
        if (ch) subtags.push({ label: ch, title: 'Carga Horária', icon: 'fa-regular fa-clock text-slate-400' });
      }

      return subtags;
    }

    // Calcula e atualiza dinamicamente as opções e tags de Tipo de Documento (Multi-seleção e Macro-TAGs)
    function updateTipoFilterOptions() {
      const rawSearch = (document.getElementById('searchInput').value || '').trim();
      const baseDocs = documents.filter(doc => docMatchesFilters(doc, rawSearch, 'tipo'));

      // 1. Contagem para cada TAG específica mapeada
      const counts = {};
      baseDocs.forEach(d => {
        const seenInDoc = getDocAllTiposSet(d);
        seenInDoc.forEach(t => {
          counts[t] = (counts[t] || 0) + 1;
        });
      });

      // 2. Contagem para cada Macro-TAG
      const macroCounts = {};
      MACRO_TAGS.forEach(m => {
        macroCounts[m.id] = baseDocs.filter(d => {
          const tipos = getDocAllTiposSet(d);
          return m.matchDoc(d, tipos);
        }).length;
      });

      // 3. Renderizar Macro-TAGs (Guarda-Chuva)
      ['macroTipoChips', 'g-macroTipoChips'].forEach(cid => {
        const container = document.getElementById(cid);
        if (!container) return;
        container.innerHTML = '';
        MACRO_TAGS.forEach(m => {
          const count = macroCounts[m.id] || 0;
          const isSelected = selectedTipos.has(m.id) || selectedTipos.has(m.label);
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = `px-2.5 py-1.5 rounded-lg text-xs font-semibold border transition flex items-center gap-1.5 shrink-0 ${
            isSelected
              ? `${m.activeBg} ring-2 ring-${m.color}-400/50 shadow-md`
              : (count === 0
                  ? 'bg-slate-950/40 text-slate-500 border-slate-900/60 opacity-60 hover:opacity-90'
                  : `${m.bg} shadow-sm`)
          }`;
          btn.title = `${m.label}: ${m.description} (${count} documentos)`;
          btn.innerHTML = `
            <i class="${m.icon} ${isSelected ? 'text-white' : 'text-' + m.color + '-400'} text-[11px]"></i>
            <span>${escapeHtml(m.label)}</span>
            <span class="text-[9.5px] px-1.5 py-0.2 rounded-full font-mono ${
              isSelected ? 'bg-black/30 text-white font-bold' : 'bg-slate-800/90 text-slate-300'
            }">${count}</span>
          `;
          btn.onclick = () => {
            toggleTipoFilter(m.id);
          };
          container.appendChild(btn);
        });
      });

      const totalMatching = baseDocs.length;

      const select = document.getElementById('selectTipoFilter');
      if (select) {
        select.innerHTML = `<option value="">Todos os Tipos (${totalMatching})</option>`;
        const sortedTipos = [...allUniqueTipos].sort((a, b) => {
          const diff = (counts[b] || 0) - (counts[a] || 0);
          if (diff !== 0) return diff;
          return a.localeCompare(b);
        });

        sortedTipos.forEach(tipo => {
          const count = counts[tipo] || 0;
          const opt = document.createElement('option');
          opt.value = tipo;
          opt.innerText = `${tipo} (${count})`;
          select.appendChild(opt);
        });
        select.value = selectedTipos.size === 1 ? Array.from(selectedTipos)[0] : '';
      }

      const inpTipo1 = document.getElementById('inputSearchTipo');
      const inpTipo2 = document.getElementById('g-inputSearchTipo');
      const tipoSearch1 = inpTipo1 ? inpTipo1.value.trim().toLowerCase() : '';
      const tipoSearch2 = inpTipo2 ? inpTipo2.value.trim().toLowerCase() : '';

      const CATEGORY_ORDER = [
        { name: 'Produtos Acadêmicos', icon: 'fa-solid fa-graduation-cap', color: 'text-amber-400' },
        { name: 'Carreira & Profissional', icon: 'fa-solid fa-briefcase', color: 'text-sky-400' },
        { name: 'Identificação & Pessoal', icon: 'fa-solid fa-id-card', color: 'text-purple-400' },
        { name: 'Financeiro', icon: 'fa-solid fa-receipt', color: 'text-emerald-400' },
        { name: 'Jurídico & Normativo', icon: 'fa-solid fa-scale-balanced', color: 'text-rose-400' },
        { name: 'Processual & Administrativo', icon: 'fa-solid fa-file-invoice', color: 'text-indigo-400' },
        { name: 'Outros', icon: 'fa-solid fa-tags', color: 'text-slate-400' }
      ];

      // 4. Renderizar Nuvem de TAGs agrupadas por categoria
      ['tipoChips', 'g-tipoChips'].forEach(cid => {
        const chipsContainer = document.getElementById(cid);
        if (!chipsContainer) return;
        chipsContainer.innerHTML = '';

        const isGallery = cid === 'g-tipoChips';
        const localSearch = isGallery ? (tipoSearch2 || tipoSearch1) : (tipoSearch1 || tipoSearch2);

        const sortedTipos = [...allUniqueTipos].sort((a, b) => {
          const diff = (counts[b] || 0) - (counts[a] || 0);
          if (diff !== 0) return diff;
          return a.localeCompare(b);
        });

        // Garantir que selecionados estejam presentes
        selectedTipos.forEach(selTipo => {
          if (!selTipo.startsWith('macro:') && !sortedTipos.includes(selTipo)) {
            sortedTipos.push(selTipo);
          }
        });

        const grouped = {};
        CATEGORY_ORDER.forEach(c => { grouped[c.name] = []; });

        let totalMatchingTags = 0;
        sortedTipos.forEach(tipo => {
          if (tipo.startsWith('macro:')) return;
          if (localSearch && !tipo.toLowerCase().includes(localSearch)) return;

          const cat = getTagCategory(tipo);
          if (!grouped[cat]) grouped[cat] = [];
          grouped[cat].push(tipo);
          totalMatchingTags++;
        });

        const badgeId = isGallery ? 'g-tipoCountBadge' : 'tipoCountBadge';
        const badgeEl = document.getElementById(badgeId);
        if (badgeEl) {
          badgeEl.innerText = `${totalMatchingTags} TAGs`;
        }

        if (totalMatchingTags === 0) {
          chipsContainer.innerHTML = '<span class="text-[11px] text-slate-500 italic p-2 block text-center">Nenhuma TAG encontrada com este termo</span>';
        } else {
          CATEGORY_ORDER.forEach(catDef => {
            const catTags = grouped[catDef.name] || [];
            if (catTags.length === 0) return;

            const groupWrapper = document.createElement('div');
            groupWrapper.className = 'bg-slate-950/40 rounded-lg p-2 border border-slate-800/60';

            const header = document.createElement('div');
            header.className = 'text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center justify-between select-none';
            header.innerHTML = `
              <span class="flex items-center gap-1.5">
                <i class="${catDef.icon} ${catDef.color} text-[10px]"></i>
                <span>${catDef.name}</span>
              </span>
              <span class="text-[9px] text-slate-500 font-mono">${catTags.length}</span>
            `;
            groupWrapper.appendChild(header);

            const tagsGrid = document.createElement('div');
            tagsGrid.className = 'flex flex-wrap gap-1.5';

            catTags.forEach(tipo => {
              const count = counts[tipo] || 0;
              const isSelected = selectedTipos.has(tipo);
              const meta = getTagMeta(tipo);
              const chip = document.createElement('button');
              chip.type = 'button';
              chip.className = `px-2.5 py-1 rounded-lg text-xs font-medium border transition flex items-center gap-1.5 truncate max-w-[240px] ${
                isSelected
                  ? `${meta.activeBg} font-semibold ring-1 ring-teal-400/50 shadow-sm`
                  : (count === 0 
                      ? 'bg-slate-950/40 text-slate-500 border-slate-900/60 opacity-60 hover:opacity-90 hover:text-slate-300' 
                      : `${meta.bg} shadow-sm`)
              }`;
              chip.title = `${tipo} (${count} documento${count === 1 ? '' : 's'}) - ${catDef.name}`;
              chip.innerHTML = `
                <i class="${meta.icon} ${isSelected ? 'text-white' : meta.color} text-[11px] shrink-0"></i>
                <span class="truncate">${escapeHtml(tipo)}</span>
                <span class="text-[9.5px] px-1.5 py-0.2 rounded-full font-mono shrink-0 ${
                  isSelected ? 'bg-black/30 text-white font-bold' : 'bg-slate-800 text-slate-400'
                }">${count}</span>
              `;
              chip.onclick = () => {
                toggleTipoFilter(tipo);
              };
              tagsGrid.appendChild(chip);
            });

            groupWrapper.appendChild(tagsGrid);
            chipsContainer.appendChild(groupWrapper);
          });
        }
      });

      ['btnClearTipo', 'g-btnClearTipo'].forEach(bid => {
        const btnClear = document.getElementById(bid);
        if (btnClear) {
          if (selectedTipos.size > 0) btnClear.classList.remove('hidden');
          else btnClear.classList.add('hidden');
        }
      });
    }

    function toggleTipoFilter(tipo) {
      if (selectedTipos.has(tipo)) {
        selectedTipos.delete(tipo);
      } else {
        selectedTipos.add(tipo);
      }
      if (selectedTipos.size === 0) {
        selectedInstituicoes.clear();
        selectedNaturezas.clear();
      }
      syncActiveFilterVars();
      applyFilter(false);
    }

    function setTipoFilter(tipo) {
      selectedTipos.clear();
      if (tipo) {
        selectedTipos.add(tipo);
      } else {
        selectedInstituicoes.clear();
        selectedNaturezas.clear();
      }
      syncActiveFilterVars();
      applyFilter(false);
    }

    function resetTipoFilter() {
      selectedTipos.clear();
      selectedInstituicoes.clear();
      selectedNaturezas.clear();
      syncActiveFilterVars();
      ['inputSearchTipo', 'g-inputSearchTipo'].forEach(id => {
        const inp = document.getElementById(id);
        if (inp) inp.value = '';
      });
      applyFilter(false);
    }

    function onTipoSearchInput() {
      updateTipoFilterOptions();
    }

    function onTipoSelectChange() {
      const val = document.getElementById('selectTipoFilter').value;
      setTipoFilter(val);
    }

    // --- Busca Inteligente Multi-Campos e Insensível a Acentos/Pontuação ---
