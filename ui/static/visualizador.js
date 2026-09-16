    let documents = [];
    let filteredDocs = [];
    let currentIndex = 0;
    let currentSelectedMd5 = null;
    let isDirty = false;
    let activeStatusFilter = 'todos';
    let activeDomainFilter = 'todos';
    let activeNaturezaFilter = ''; // Vazio = todas
    let activeTipoFilter = ''; // Vazio = todos
    let activeInstituicaoFilter = ''; // Vazio = todas
    let activeQuickView = 'todos';
    const selectedMd5s = new Set();
    const selectedDominios = new Set();
    const selectedInstituicoes = new Set();
    const selectedTipos = new Set();
    const selectedNaturezas = new Set();
    const selectedStatus = new Set();
    const selectedFormatos = new Set();
    let allUniqueInstituicoes = [];
    let openFilterPopoverId = null;

    function syncActiveFilterVars() {
      activeDomainFilter = selectedDominios.size === 1 ? Array.from(selectedDominios)[0] : (selectedDominios.size === 0 ? 'todos' : 'multiplo');
      activeInstituicaoFilter = selectedInstituicoes.size === 1 ? Array.from(selectedInstituicoes)[0] : '';
      activeTipoFilter = selectedTipos.size === 1 ? Array.from(selectedTipos)[0] : '';
      activeNaturezaFilter = selectedNaturezas.size === 1 ? Array.from(selectedNaturezas)[0] : '';
      activeStatusFilter = selectedStatus.size === 1 ? Array.from(selectedStatus)[0] : (selectedStatus.size === 0 ? 'todos' : 'multiplo');
      activeFormatoFilter = selectedFormatos.size === 1 ? Array.from(selectedFormatos)[0] : '';
    }

    // =========================================================================
    // DEFINIÇÃO DE MACRO-TAGS E CATEGORIZAÇÃO UNIVERSAL DE TAGS
    // =========================================================================
    function getDocAllTiposSet(doc) {
      const s = new Set();
      if (!doc) return s;
      const main = safeString(doc.tipo_documento).trim();
      if (main) s.add(main);
      if (Array.isArray(doc.todos_tipos)) {
        doc.todos_tipos.forEach(t => {
          const clean = safeString(t).trim();
          if (clean) s.add(clean);
        });
      }
      if (Array.isArray(doc.dossie_paginas)) {
        doc.dossie_paginas.forEach(p => {
          const clean = safeString(p.tipo).trim();
          if (clean) s.add(clean);
        });
      }
      if (s.size === 0) s.add('Não identificado');
      return s;
    }

    function getTagCategory(tipo) {
      const t = normalizeText(tipo || '');
      if (!t || t === 'nao identificado' || t === 'outro' || t === 'documento diverso') {
        return 'Outros';
      }
      // Carreira & Profissional
      if (t.includes('curriculo') || t.includes('experiencia profissional') || t.includes('lattes') || t.includes('carteira de trabalho') || t.includes('ctps') || t.includes('situacao cadastral') || t.includes('registro profissional')) {
        return 'Carreira & Profissional';
      }
      // Identificação & Pessoal
      if (t === 'rg' || t === 'cpf' || t === 'cnh' || t.includes('rg') || t.includes('cnh') || t.includes('cpf') || t.includes('identidade') || t.includes('habilitacao') || t.includes('certidao') || t.includes('eleitoral') || t.includes('passaporte') || t.includes('nascimento') || t.includes('casamento') || t.includes('reservista')) {
        return 'Identificação & Pessoal';
      }
      // Financeiro
      if (t.includes('pix') || t.includes('pagamento') || t.includes('extrato') || t.includes('banco') || t.includes('bancario') || t.includes('nota fiscal') || t.includes('fatura') || t.includes('recibo') || t.includes('boleto')) {
        return 'Financeiro';
      }
      // Jurídico & Normativo
      if (t.includes('contrat') || t.includes('convenio') || t.includes('responsabilidade') || t.includes('portaria') || t.includes('resolucao') || t.includes('diario oficial') || t.includes('termo') || t.includes('procuracao') || t.includes('estatuto')) {
        return 'Jurídico & Normativo';
      }
      // Processual & Administrativo
      if (t.includes('recurso') || t.includes('relatorio') || t.includes('cadastro') || t.includes('preparatorio') || t.includes('promocional') || t.includes('processual') || t.includes('oficio') || t.includes('memorando')) {
        return 'Processual & Administrativo';
      }
      // Acadêmico
      if (t.includes('diploma') || t.includes('certificado') || t.includes('historico') || t.includes('declaracao') || t.includes('ementa') || t.includes('dissertacao') || t.includes('livro') || t.includes('publicacao') || t.includes('didatico') || t.includes('instrucional') || t.includes('biblioteca') || t.includes('aluno') || t.includes('ensino') || t.includes('academico') || t.includes('curso') || t.includes('graduacao') || t.includes('pos-graduacao') || t.includes('modulo') || t.includes('desenvolvimento institucional')) {
        return 'Produtos Acadêmicos';
      }
      return 'Outros';
    }

    const MACRO_TAGS = [
      {
        id: 'macro:produtos_academicos',
        label: 'Produtos Acadêmicos',
        shortLabel: 'Acadêmicos',
        icon: 'fa-solid fa-graduation-cap',
        color: 'amber',
        bg: 'bg-amber-950/40 border-amber-800/70 text-amber-200 hover:bg-amber-900/50 hover:border-amber-500',
        activeBg: 'bg-amber-600 border-amber-400 text-white',
        category: 'Produtos Acadêmicos',
        description: 'Diplomas, Certificados, Históricos, Declarações, Ementas, Dissertações, etc.',
        matchDoc: (doc, tiposSet) => {
          const dom = safeString(doc.dominio_documento).trim().toLowerCase();
          if (dom === 'academico') return true;
          const academicKeywords = [
            'diploma', 'certificado', 'historico escolar', 'declaracao', 'ementa',
            'conteudo programatico', 'dissertacao', 'livro', 'publicacao', 'didatico',
            'instrucional', 'biblioteca', 'aluno', 'ensino', 'academico', 'curso',
            'graduacao', 'pos-graduacao', 'modulo', 'plano de desenvolvimento'
          ];
          for (const t of tiposSet) {
            const tl = normalizeText(t);
            if (academicKeywords.some(kw => tl.includes(kw))) return true;
          }
          return false;
        }
      },
      {
        id: 'macro:carreira_profissional',
        label: 'Carreira & Profissional',
        shortLabel: 'Profissional',
        icon: 'fa-solid fa-briefcase',
        color: 'sky',
        bg: 'bg-sky-950/40 border-sky-800/70 text-sky-200 hover:bg-sky-900/50 hover:border-sky-500',
        activeBg: 'bg-sky-600 border-sky-400 text-white',
        category: 'Carreira & Profissional',
        description: 'Currículos, Lattes, Experiência Profissional, Registros de Classe',
        matchDoc: (doc, tiposSet) => {
          const dom = safeString(doc.dominio_documento).trim().toLowerCase();
          if (dom === 'profissional') return true;
          if (doc.cnpj || (doc.dados_extras && doc.dados_extras.cnpj)) return true;
          const profKeywords = ['curriculo', 'experiencia profissional', 'lattes', 'carteira de trabalho', 'ctps', 'situacao cadastral', 'cnpj', 'cartao cnpj', 'receita federal', 'registro profissional', 'crf', 'crm', 'oab', 'crea'];
          for (const t of tiposSet) {
            const tl = normalizeText(t);
            if (profKeywords.some(kw => tl.includes(kw))) return true;
          }
          return false;
        }
      },
      {
        id: 'macro:identificacao_pessoal',
        label: 'Identificação & Pessoal',
        shortLabel: 'Identificação',
        icon: 'fa-solid fa-id-card',
        color: 'purple',
        bg: 'bg-purple-950/40 border-purple-800/70 text-purple-200 hover:bg-purple-900/50 hover:border-purple-500',
        activeBg: 'bg-purple-600 border-purple-400 text-white',
        category: 'Identificação & Pessoal',
        description: 'RG, CPF, CNH, Certidões, Título de Eleitor, Passaporte',
        matchDoc: (doc, tiposSet) => {
          const dom = safeString(doc.dominio_documento).trim().toLowerCase();
          if (dom === 'identificacao' || dom === 'pessoal') return true;
          const idKeywords = ['rg', 'cpf', 'cnh', 'identidade', 'habilitacao', 'certidao', 'eleitoral', 'passaporte', 'nascimento', 'casamento', 'reservista', 'residencia'];
          for (const t of tiposSet) {
            const tl = normalizeText(t);
            if (idKeywords.some(kw => tl === kw || tl.includes(kw))) return true;
          }
          return false;
        }
      },
      {
        id: 'macro:financeiro',
        label: 'Financeiro',
        shortLabel: 'Financeiro',
        icon: 'fa-solid fa-receipt',
        color: 'emerald',
        bg: 'bg-emerald-950/40 border-emerald-800/70 text-emerald-200 hover:bg-emerald-900/50 hover:border-emerald-500',
        activeBg: 'bg-emerald-600 border-emerald-400 text-white',
        category: 'Financeiro',
        description: 'PIX, Comprovantes de Pagamento, Boletos, Recibos, Extratos',
        matchDoc: (doc, tiposSet) => {
          const dom = safeString(doc.dominio_documento).trim().toLowerCase();
          if (dom === 'financeiro') return true;
          const finKeywords = ['pix', 'pagamento', 'extrato', 'banco', 'bancario', 'nota fiscal', 'fatura', 'recibo', 'boleto'];
          for (const t of tiposSet) {
            const tl = normalizeText(t);
            if (finKeywords.some(kw => tl.includes(kw))) return true;
          }
          return false;
        }
      },
      {
        id: 'macro:juridico_normativo',
        label: 'Jurídico & Normativo',
        shortLabel: 'Jurídico',
        icon: 'fa-solid fa-scale-balanced',
        color: 'rose',
        bg: 'bg-rose-950/40 border-rose-800/70 text-rose-200 hover:bg-rose-900/50 hover:border-rose-500',
        activeBg: 'bg-rose-600 border-rose-400 text-white',
        category: 'Jurídico & Normativo',
        description: 'Contratos, Portarias, Resoluções, Diário Oficial, Termos',
        matchDoc: (doc, tiposSet) => {
          const dom = safeString(doc.dominio_documento).trim().toLowerCase();
          if (dom === 'juridico' || dom === 'normativo' || dom === 'legal') return true;
          const jurKeywords = ['contrat', 'convenio', 'responsabilidade', 'portaria', 'resolucao', 'diario oficial', 'termo', 'procuracao', 'estatuto', 'parecer'];
          for (const t of tiposSet) {
            const tl = normalizeText(t);
            if (jurKeywords.some(kw => tl.includes(kw))) return true;
          }
          return false;
        }
      }
    ];

    // Gerenciamento de Menus Flutuantes (Filter Popovers)
    function toggleFilterPopover(id) {
      if (openFilterPopoverId === id) {
        closeAllFilterPopovers();
      } else {
        closeAllFilterPopovers();
        const pop = document.getElementById(id);
        if (pop) {
          pop.classList.remove('hidden');
          openFilterPopoverId = id;
          const input = pop.querySelector('input[type="text"]');
          if (input) {
            setTimeout(() => {
              input.focus();
              input.select();
            }, 60);
          }
        }
      }
    }

    function closeAllFilterPopovers() {
      ['popoverInstituicao', 'popoverTipo', 'popoverNatureza', 'popoverStatus', 'popoverDominio', 'popoverFormato',
       'g-popoverInstituicao', 'g-popoverTipo', 'g-popoverNatureza', 'g-popoverStatus', 'g-popoverDominio', 'g-popoverFormato'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
      });
      openFilterPopoverId = null;
    }

    // =========================================================================
    // GERENCIAMENTO DE TEMA (CLARO / ESCURO / SISTEMA)
    // =========================================================================
    let currentThemeSetting = localStorage.getItem('joakindex_theme') || 'system';

    function getSystemTheme() {
      return (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
    }

    function getEffectiveTheme(setting = currentThemeSetting) {
      if (setting === 'system') return getSystemTheme();
      return setting === 'light' ? 'light' : 'dark';
    }

    function setTheme(setting, save = true) {
      if (!['light', 'dark', 'system'].includes(setting)) setting = 'system';
      currentThemeSetting = setting;
      if (save) {
        try {
          localStorage.setItem('joakindex_theme', setting);
        } catch (e) {
          console.warn('Erro ao salvar tema no localStorage:', e);
        }
      }

      const effective = getEffectiveTheme(setting);
      const html = document.documentElement;

      if (effective === 'light') {
        html.classList.add('theme-light', 'light');
        html.classList.remove('theme-dark', 'dark');
        html.setAttribute('data-theme', 'light');
      } else {
        html.classList.add('theme-dark', 'dark');
        html.classList.remove('theme-light', 'light');
        html.setAttribute('data-theme', 'dark');
      }

      updateThemeUI();
      closeThemeDropdown();

      // Se o painel de BI estiver ativo, re-renderiza gráficos para ajustar paletas
      if (typeof currentMainTab !== 'undefined' && currentMainTab === 'bi') {
        renderBIDashboard();
      }
    }

    function updateThemeUI() {
      const iconEl = document.getElementById('themeCurrentIcon');
      const labelEl = document.getElementById('themeCurrentLabel');
      const effective = getEffectiveTheme(currentThemeSetting);

      if (iconEl && labelEl) {
        if (currentThemeSetting === 'light') {
          iconEl.className = 'fa-solid fa-sun text-amber-400 text-xs';
          labelEl.innerText = 'Claro';
        } else if (currentThemeSetting === 'dark') {
          iconEl.className = 'fa-solid fa-moon text-indigo-400 text-xs';
          labelEl.innerText = 'Escuro';
        } else {
          iconEl.className = 'fa-solid fa-circle-half-stroke text-sky-400 text-xs';
          labelEl.innerText = `Sistema (${effective === 'dark' ? 'Escuro' : 'Claro'})`;
        }
      }

      // Sincroniza itens do menu dropdown no header
      ['light', 'dark', 'system'].forEach(opt => {
        const item = document.getElementById(`themeItem-${opt}`);
        if (item) {
          const check = item.querySelector('.theme-check');
          if (opt === currentThemeSetting) {
            item.classList.add('bg-emerald-500/10', 'text-emerald-400', 'font-semibold');
            if (check) check.classList.remove('hidden');
          } else {
            item.classList.remove('bg-emerald-500/10', 'text-emerald-400', 'font-semibold');
            if (check) check.classList.add('hidden');
          }
        }

        // Sincroniza botões de tema no modal de configurações
        const cfgBtn = document.getElementById(`cfgThemeBtn-${opt}`);
        if (cfgBtn) {
          if (opt === currentThemeSetting) {
            cfgBtn.className = 'px-3 py-1.5 rounded-lg border text-xs font-semibold flex items-center gap-1.5 transition bg-emerald-600 text-white border-emerald-500 shadow-sm';
          } else {
            cfgBtn.className = 'px-3 py-1.5 rounded-lg border text-xs font-medium flex items-center gap-1.5 transition bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-700';
          }
        }
      });
    }

    function toggleThemeDropdown(event) {
      if (event) event.stopPropagation();
      const menu = document.getElementById('themeDropdownMenu');
      if (!menu) return;
      const isHidden = menu.classList.contains('hidden');
      closeAllFilterPopovers();
      closeMobileActionsMenu();
      if (isHidden) {
        menu.classList.remove('hidden');
      } else {
        menu.classList.add('hidden');
      }
    }

    function closeThemeDropdown() {
      const menu = document.getElementById('themeDropdownMenu');
      if (menu && !menu.classList.contains('hidden')) {
        menu.classList.add('hidden');
      }
    }

    // =========================================================================
    // RESPONSIVIDADE & GERENCIAMENTO MOBILE JOAKINDEX
    // =========================================================================
    let currentMobileConfView = 'lista';
    let isSidebarCollapsedDesktop = false;

    function toggleMobileActionsMenu(event) {
      if (event) event.stopPropagation();
      const menu = document.getElementById('mobileActionsDropdownMenu');
      if (!menu) return;
      const isHidden = menu.classList.contains('hidden');
      closeAllFilterPopovers();
      closeThemeDropdown();
      if (isHidden) {
        menu.classList.remove('hidden');
      } else {
        menu.classList.add('hidden');
      }
    }

    function closeMobileActionsMenu() {
      const menu = document.getElementById('mobileActionsDropdownMenu');
      if (menu && !menu.classList.contains('hidden')) {
        menu.classList.add('hidden');
      }
    }

    function toggleSidebarDesktop() {
      isSidebarCollapsedDesktop = !isSidebarCollapsedDesktop;
      const sidebar = document.getElementById('sidebar');
      const btn = document.getElementById('btnToggleSidebar');
      const label = document.getElementById('labelToggleSidebar');
      const icon = document.getElementById('iconToggleSidebar');
      if (sidebar) {
        sidebar.style.display = isSidebarCollapsedDesktop ? 'none' : 'flex';
      }
      if (btn) {
        if (isSidebarCollapsedDesktop) {
          btn.classList.add('bg-emerald-900/40', 'border-emerald-500/50', 'text-emerald-300');
          if (label) label.innerText = 'Mostrar Lista';
          if (icon) icon.className = 'fa-solid fa-list text-emerald-400';
        } else {
          btn.classList.remove('bg-emerald-900/40', 'border-emerald-500/50', 'text-emerald-300');
          if (label) label.innerText = 'Lista';
          if (icon) icon.className = 'fa-solid fa-bars-staggered text-emerald-400';
        }
      }
    }

    function setMobileConferenceView(view) {
      currentMobileConfView = view;
      const isMobile = window.innerWidth < 768;
      const sidebar = document.getElementById('sidebar');
      const pdfPane = document.getElementById('pdfViewerPane');
      const inspector = document.getElementById('inspectorPane');
      const btnLista = document.getElementById('btnMobSegLista');
      const btnDoc = document.getElementById('btnMobSegDoc');
      const btnDados = document.getElementById('btnMobSegDados');

      if (!isMobile) {
        if (sidebar) sidebar.style.display = isSidebarCollapsedDesktop ? 'none' : 'flex';
        if (pdfPane) pdfPane.style.display = 'flex';
        if (inspector) inspector.style.display = 'flex';
        return;
      }

      [btnLista, btnDoc, btnDados].forEach(b => {
        if (b) {
          b.classList.remove('bg-emerald-600', 'text-white', 'shadow-sm');
          b.classList.add('text-slate-400');
        }
      });

      if (view === 'lista') {
        if (btnLista) {
          btnLista.classList.add('bg-emerald-600', 'text-white', 'shadow-sm');
          btnLista.classList.remove('text-slate-400');
        }
        if (sidebar) sidebar.style.display = 'flex';
        if (pdfPane) pdfPane.style.display = 'none';
        if (inspector) inspector.style.display = 'none';
      } else if (view === 'doc') {
        if (btnDoc) {
          btnDoc.classList.add('bg-emerald-600', 'text-white', 'shadow-sm');
          btnDoc.classList.remove('text-slate-400');
        }
        if (sidebar) sidebar.style.display = 'none';
        if (pdfPane) pdfPane.style.display = 'flex';
        if (inspector) inspector.style.display = 'none';
      } else if (view === 'dados') {
        if (btnDados) {
          btnDados.classList.add('bg-emerald-600', 'text-white', 'shadow-sm');
          btnDados.classList.remove('text-slate-400');
        }
        if (sidebar) sidebar.style.display = 'none';
        if (pdfPane) pdfPane.style.display = 'none';
        if (inspector) inspector.style.display = 'flex';
      }
    }

    window.addEventListener('resize', () => {
      if (typeof currentMainTab !== 'undefined' && currentMainTab === 'conferencia') {
        if (window.innerWidth >= 768) {
          const sidebar = document.getElementById('sidebar');
          const pdfPane = document.getElementById('pdfViewerPane');
          const inspector = document.getElementById('inspectorPane');
          if (sidebar) sidebar.style.display = isSidebarCollapsedDesktop ? 'none' : 'flex';
          if (pdfPane) pdfPane.style.display = 'flex';
          if (inspector) inspector.style.display = 'flex';
        } else {
          setMobileConferenceView(currentMobileConfView);
        }
      }
    });

    function initTheme() {
      currentThemeSetting = localStorage.getItem('joakindex_theme') || 'system';
      setTheme(currentThemeSetting, false);

      // Ouvinte para mudanças em tempo real no SO quando em modo "sistema"
      if (window.matchMedia) {
        try {
          window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            if (currentThemeSetting === 'system') {
              setTheme('system', false);
            }
          });
        } catch (e) {}
      }
    }

    // Fecha popovers e dropdowns ao clicar fora ou ao pressionar Escape
    document.addEventListener('click', (e) => {
      if (openFilterPopoverId) {
        const bar1 = document.getElementById('filterPopoversBar');
        const bar2 = document.getElementById('galleryFilterPopoversBar');
        const clickedInside = (bar1 && bar1.contains(e.target)) || (bar2 && bar2.contains(e.target));
        if (!clickedInside) {
          closeAllFilterPopovers();
        }
      }
      const themeContainer = document.getElementById('themeDropdownContainer');
      if (themeContainer && !themeContainer.contains(e.target)) {
        closeThemeDropdown();
      }
      const mobileContainer = document.getElementById('mobileActionsContainer');
      if (mobileContainer && !mobileContainer.contains(e.target)) {
        closeMobileActionsMenu();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (openFilterPopoverId) closeAllFilterPopovers();
        closeThemeDropdown();
        closeMobileActionsMenu();
      }
    });

    // Funções de compatibilidade no-op (legado de acordeões)
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

    async function executeBulkApprove() {
      const count = selectedMd5s.size;
      if (count === 0) return;

      if (!confirm(`Deseja aprovar a conferência humana de ${count} documento(s) selecionado(s)?`)) {
        return;
      }

      const md5s = Array.from(selectedMd5s);
      try {
        const res = await fetch('/api/batch/aprovar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ md5s })
        });
        const data = await res.json();
        if (res.ok && data.status === 'sucesso') {
          const nowIso = new Date().toISOString();
          documents.forEach(d => {
            if (selectedMd5s.has(d.md5)) {
              d.status_conferencia = 'aprovado';
              d.conferido_em = nowIso;
            }
          });
          clearBulkSelection();
          applyFilter(true);
          showToast(`${data.count || count} documento(s) aprovado(s) com sucesso!`, 'success');
        } else {
          alert(`Erro ao aprovar documentos em lote: ${data.mensagem || 'Falha na requisição'}`);
        }
      } catch (err) {
        alert(`Erro de conexão ao aprovar lote: ${err.message}`);
      }
    }

    async function executeBulkExportZip() {
      const count = selectedMd5s.size;
      if (count === 0) return;

      const btn = document.getElementById('btnBulkZip');
      const origHtml = btn ? btn.innerHTML : '';
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-[11px]"></i><span>Gerando...</span>`;
      }

      const md5s = Array.from(selectedMd5s);
      try {
        const res = await fetch('/api/batch/exportar-zip', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ md5s })
        });

        if (!res.ok) {
          throw new Error(`Servidor retornou erro ${res.status}`);
        }

        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `joakindex_lote_${count}_arquivos_${new Date().toISOString().slice(0, 10)}.zip`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        showToast(`Arquivo ZIP com ${count} documento(s) baixado com sucesso!`, 'success');
      } catch (err) {
        alert(`Erro ao exportar ZIP em lote: ${err.message}`);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = origHtml;
        }
      }
    }

    function openBulkTagModal() {
      const count = selectedMd5s.size;
      if (count === 0) return;

      document.getElementById('modalBulkTagCount').innerText = count;
      document.getElementById('bulkInputDominio').value = '';
      document.getElementById('bulkInputTipo').value = '';
      document.getElementById('bulkInputFaculdade').value = '';
      document.getElementById('bulkInputStatusConf').value = '';

      const dlTipos = document.getElementById('bulkDatalistTipos');
      if (dlTipos) {
        dlTipos.innerHTML = allUniqueTipos.map(t => `<option value="${t}">`).join('');
      }
      const dlFacs = document.getElementById('bulkDatalistFaculdades');
      if (dlFacs) {
        dlFacs.innerHTML = allUniqueInstituicoes.map(f => `<option value="${f}">`).join('');
      }

      document.getElementById('modalBulkTag').classList.remove('hidden');
    }

    function closeBulkTagModal() {
      document.getElementById('modalBulkTag').classList.add('hidden');
    }

    async function confirmBulkTagApply() {
      const count = selectedMd5s.size;
      if (count === 0) return;

      const dom = document.getElementById('bulkInputDominio').value.trim();
      const tipo = document.getElementById('bulkInputTipo').value.trim();
      const fac = document.getElementById('bulkInputFaculdade').value.trim();
      const statusConf = document.getElementById('bulkInputStatusConf').value.trim();

      if (!dom && !tipo && !fac && !statusConf) {
        alert('Selecione ou preencha pelo menos um campo para alterar.');
        return;
      }

      const payload = {
        md5s: Array.from(selectedMd5s),
        dominio: dom || null,
        tipo_documento: tipo || null,
        faculdade: fac || null,
        status_conferencia: statusConf || null
      };

      try {
        const res = await fetch('/api/batch/alterar-tipo', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && data.status === 'sucesso') {
          const nowIso = new Date().toISOString();
          documents.forEach(d => {
            if (selectedMd5s.has(d.md5)) {
              if (dom) {
                d.dominio = dom;
                d.todos_dominios = [dom];
              }
              if (tipo) {
                d.tipo_documento = tipo;
                d.todos_tipos = [tipo];
              }
              if (fac) {
                d.faculdade = fac;
              }
              if (statusConf) {
                d.status_conferencia = statusConf;
                if (statusConf === 'aprovado') d.conferido_em = nowIso;
              }
              d.revisado_em = nowIso;
            }
          });
          closeBulkTagModal();
          clearBulkSelection();
          initMasterFilterLists();
          applyFilter(true);
          showToast(`${data.count || count} documento(s) atualizado(s) com sucesso!`, 'success');
        } else {
          alert(`Erro ao atualizar lote: ${data.mensagem || 'Falha na requisição'}`);
        }
      } catch (err) {
        alert(`Erro de conexão ao atualizar lote: ${err.message}`);
      }
    }

    let bulkClassifyAborted = false;

    async function executeBulkClassify() {
      const count = selectedMd5s.size;
      if (count === 0) return;

      if (!confirm(`Deseja executar a leitura com IA e OCR para ${count} documento(s) selecionado(s)?`)) {
        return;
      }

      bulkClassifyAborted = false;
      const modal = document.getElementById('modalBulkClassifyProgress');
      const msgEl = document.getElementById('bulkClassifyStatusMsg');
      const barEl = document.getElementById('bulkClassifyProgressBar');
      const counterEl = document.getElementById('bulkClassifyCounter');
      const percentEl = document.getElementById('bulkClassifyPercent');

      modal.classList.remove('hidden');
      const md5s = Array.from(selectedMd5s);
      let done = 0;

      for (let i = 0; i < md5s.length; i++) {
        if (bulkClassifyAborted) break;

        const m = md5s[i];
        const docObj = documents.find(d => d.md5 === m);
        const fname = docObj ? (docObj.nome_arquivo || m.substring(0, 8)) : m.substring(0, 8);
        msgEl.innerText = `Processando ${fname}...`;
        counterEl.innerText = `${i + 1} / ${md5s.length}`;
        const pct = Math.round(((i + 1) / md5s.length) * 100);
        barEl.style.width = `${pct}%`;
        percentEl.innerText = `${pct}%`;

        const isBulkHybrid = !!(document.getElementById('cfgHybridMode')?.checked ?? systemConfig?.visualizador?.hybrid ?? false);
        const bulkHybridModel = (document.getElementById('cfgHybridCloudModel')?.value || systemConfig?.visualizador?.hybrid_cloud_model || 'gpt-4o-mini').trim();
        const bulkHybridKey = (document.getElementById('cfgHybridOpenaiKey')?.value || document.getElementById('cfgOpenaiKey')?.value || '').trim();

        try {
          const res = await fetch('/api/processar-documento', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              md5: m,
              hybrid: isBulkHybrid,
              hybrid_cloud_model: bulkHybridModel,
              openai_key: bulkHybridKey || undefined
            })
          });
          const data = await res.json();
          if (res.ok && data.status === 'sucesso' && data.documento) {
            const idx = documents.findIndex(d => d.md5 === m);
            if (idx !== -1) {
              documents[idx] = Object.assign({}, documents[idx], data.documento);
            }
            done++;
          }
        } catch (e) {
          console.error(`Erro ao processar ${m}:`, e);
        }
      }

      modal.classList.add('hidden');
      clearBulkSelection();
      initMasterFilterLists();
      applyFilter(true);
      showToast(`${done} de ${md5s.length} documento(s) classificado(s) com sucesso!`, 'success');
    }

    function abortBulkClassify() {
      bulkClassifyAborted = true;
      const msgEl = document.getElementById('bulkClassifyStatusMsg');
      if (msgEl) msgEl.innerText = 'Interrompendo após o documento atual...';
    }

    // Modo de Exibição do Sidebar (Miniaturas vs Compacto)
    let sidebarViewMode = localStorage.getItem('joakindex_sidebar_view_mode') || 'thumbnails';

    // Inspetor 4 Abas & Cache de Texto OCR
    let currentInspectorTab = 'dados';
    let currentDocRawText = '';
    const docTextCache = {};

    function toggleThumbnailView() {
      sidebarViewMode = (sidebarViewMode === 'thumbnails' ? 'compact' : 'thumbnails');
      try {
        localStorage.setItem('joakindex_sidebar_view_mode', sidebarViewMode);
      } catch (e) {}
      updateThumbnailToggleUI();
      renderSidebar();
    }

    function updateThumbnailToggleUI() {
      const btn = document.getElementById('btnToggleThumbnailView');
      const icon = document.getElementById('iconToggleThumbnail');
      const label = document.getElementById('labelToggleThumbnail');
      if (!btn || !icon || !label) return;
      if (sidebarViewMode === 'thumbnails') {
        icon.className = 'fa-solid fa-table-cells-large text-emerald-400';
        label.innerText = 'Miniaturas';
        btn.title = 'Visualização com Miniaturas ativa. Clique para alternar para Modo Compacto.';
      } else {
        icon.className = 'fa-solid fa-bars text-slate-400';
        label.innerText = 'Compacto';
        btn.title = 'Modo Compacto ativo. Clique para alternar para Visualização com Miniaturas.';
      }
    }

    // Controle de Zoom e Rotação do Visualizador de Imagens
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

    function markDirty() {
      isDirty = true;
      updateJsonView();
    }

    function getCurrentFormValues() {
      if (currentIndex < 0 || !filteredDocs || currentIndex >= filteredDocs.length) {
        return null;
      }
      const doc = filteredDocs[currentIndex];
      const selectDom = document.getElementById('select_dominio');
      const dominio = selectDom ? selectDom.value : (doc.dominio || 'academico');

      const inputValor = document.getElementById('input_valor_monetario');
      const valorMonetario = inputValor ? inputValor.value.trim() : (doc.valor_monetario || null);

      const dadosExtras = { ...(doc.dados_extras || {}) };

      const getVal = (id) => {
        const el = document.getElementById(id);
        return el ? el.value.trim() : '';
      };

      const pixPagadorNome = getVal('input_pix_pagador_nome');
      const pixPagadorCpfCnpj = getVal('input_pix_pagador_cpf_cnpj');
      const pixPagadorBanco = getVal('input_pix_pagador_banco');
      const pixRecebedorNome = getVal('input_pix_recebedor_nome_preview') || getVal('input_beneficiario');
      const pixRecebedorCpfCnpj = getVal('input_pix_recebedor_cpf_preview') || getVal('input_cpf');
      const pixRecebedorBanco = getVal('input_pix_recebedor_banco');
      const pixChave = getVal('input_pix_chave');
      const pixE2eId = getVal('input_pix_e2e_id');
      const pixAutenticacao = getVal('input_pix_autenticacao');

      const cnpjVal = getVal('input_doc_cnpj') || getVal('input_cnpj') || null;
      const cnpjRazao = getVal('input_cnpj_razao_social') || null;
      const cnpjFantasia = getVal('input_cnpj_nome_fantasia') || null;
      const cnpjSituacao = getVal('input_cnpj_situacao') || null;
      const cnpjDataAbertura = getVal('input_cnpj_data_abertura') || null;
      const cnpjCnae = getVal('input_cnpj_cnae') || null;
      const cnpjNatureza = getVal('input_cnpj_natureza_juridica') || null;
      const cnpjEndereco = getVal('input_doc_endereco') || getVal('input_cnpj_endereco') || null;
      const cnpjTelefone = getVal('input_cnpj_telefone') || null;
      const cnpjEmail = getVal('input_cnpj_email') || null;

      if (cnpjVal || cnpjRazao || cnpjFantasia || cnpjSituacao || cnpjCnae || cnpjEndereco) {
        if (cnpjVal) {
          dadosExtras.cnpj = cnpjVal;
          if (dominio === 'academico') {
            dadosExtras.cnpj_instituicao = cnpjVal;
          }
        }
        if (cnpjRazao) dadosExtras.razao_social = cnpjRazao;
        if (cnpjFantasia) dadosExtras.nome_fantasia = cnpjFantasia;
        if (cnpjSituacao) dadosExtras.situacao_cadastral = cnpjSituacao;
        if (cnpjDataAbertura) dadosExtras.data_abertura = cnpjDataAbertura;
        if (cnpjCnae) dadosExtras.cnae_principal = cnpjCnae;
        if (cnpjNatureza) dadosExtras.natureza_juridica = cnpjNatureza;
        if (cnpjEndereco) dadosExtras.endereco_completo = cnpjEndereco;
        if (cnpjTelefone) dadosExtras.telefone = cnpjTelefone;
        if (cnpjEmail) dadosExtras.email = cnpjEmail;
      }

      const primaryTipo = document.getElementById('select_tipo_documento').value || null;
      let todosTipos = Array.isArray(doc.todos_tipos) ? [...doc.todos_tipos] : [];
      if (primaryTipo && !todosTipos.some(t => t.toLowerCase() === primaryTipo.toLowerCase())) {
        todosTipos.unshift(primaryTipo);
      }

      const isFinancial = (dominio === 'financeiro') || todosTipos.some(t => {
        const tl = safeString(t).toLowerCase();
        return tl.includes('pix') || tl.includes('pagamento') || tl.includes('recibo') || tl.includes('boleto');
      });

      if (isFinancial) {
        dadosExtras.pix_pagador_nome = pixPagadorNome || null;
        dadosExtras.pix_pagador_cpf_cnpj = pixPagadorCpfCnpj || null;
        dadosExtras.pix_pagador_banco = pixPagadorBanco || null;
        dadosExtras.pix_recebedor_nome = pixRecebedorNome || null;
        dadosExtras.pix_recebedor_cpf_cnpj = pixRecebedorCpfCnpj || null;
        dadosExtras.pix_recebedor_banco = pixRecebedorBanco || null;
        dadosExtras.pix_chave = pixChave || null;
        dadosExtras.pix_e2e_id = pixE2eId || null;
        dadosExtras.pix_autenticacao = pixAutenticacao || null;
      } else {
        delete dadosExtras.pix_pagador_nome;
        delete dadosExtras.pix_pagador_cpf_cnpj;
        delete dadosExtras.pix_pagador_banco;
        delete dadosExtras.pix_recebedor_nome;
        delete dadosExtras.pix_recebedor_cpf_cnpj;
        delete dadosExtras.pix_recebedor_banco;
        delete dadosExtras.pix_chave;
        delete dadosExtras.pix_e2e_id;
        delete dadosExtras.pix_autenticacao;
      }

      // Recalcula lista limpa de domínios
      const domsSet = new Set();
      if (dominio) domsSet.add(dominio);
      todosTipos.forEach(t => {
        const tLower = safeString(t).toLowerCase();
        if (tLower.includes('crv') || tLower.includes('crlv') || tLower.includes('atpv') || tLower.includes('veicular') || tLower.includes('veiculo') || tLower.includes('vistoria') || tLower.includes('detran') || tLower.includes('senatran') || tLower.includes('denatran') || tLower.includes('remocao') || tLower.includes('remoção') || tLower.includes('arrematacao') || tLower.includes('arrematação')) {
          domsSet.add('veicular');
        } else if (tLower.includes('pix') || tLower.includes('pagamento') || tLower.includes('recibo') || tLower.includes('boleto') || tLower.includes('extrato') || tLower.includes('nota fiscal')) {
          domsSet.add('financeiro');
        } else if (tLower.includes('rg') || tLower.includes('cnh') || tLower.includes('cpf') || tLower.includes('certid') || tLower.includes('passaporte') || tLower.includes('eleitor')) {
          domsSet.add('identificacao');
        } else if (tLower.includes('procur') || tLower.includes('contrato') || tLower.includes('posse')) {
          domsSet.add('juridico');
        } else if (tLower.includes('cnpj') || tLower.includes('cadastral') || tLower.includes('trabalho') || tLower.includes('ctps') || tLower.includes('lattes') || tLower.includes('curriculo') || tLower.includes('registro profissional')) {
          domsSet.add('profissional');
        } else if (tLower.includes('diploma') || tLower.includes('certificado') || tLower.includes('histórico') || tLower.includes('declar') || tLower.includes('ementa')) {
          domsSet.add('academico');
        }
      });
      const todosDominios = Array.from(domsSet);

      // Coleta valores de todos os campos renderizados dinamicamente via [data-dynamic-key]
      const dynamicInputs = document.querySelectorAll('[data-dynamic-key]');
      dynamicInputs.forEach(input => {
        const key = input.getAttribute('data-dynamic-key');
        const val = input.value.trim();
        if (val) {
          dadosExtras[key] = val;
        } else {
          delete dadosExtras[key];
        }
      });

      const getFieldVal = (id, key) => {
        const el = document.getElementById(id) || document.querySelector(`[data-dynamic-key="${key}"]`);
        if (el) {
          const v = el.value.trim();
          return v || null;
        }
        return doc[key] || dadosExtras[key] || null;
      };

      const res = {
        ...doc,
        dominio: dominio,
        todos_dominios: todosDominios,
        todos_tipos: todosTipos,
        dossie_paginas: doc.dossie_paginas || [],
        valor_monetario: getFieldVal('input_valor_monetario', 'valor_monetario'),
        beneficiario: getFieldVal('input_beneficiario', 'beneficiario'),
        cpf: getFieldVal('input_cpf', 'cpf'),
        rg: getFieldVal('input_rg', 'rg'),
        cnpj: cnpjVal || getFieldVal('input_cnpj', 'cnpj') || getFieldVal('input_doc_cnpj', 'cnpj'),
        natureza_curso: document.getElementById('select_natureza_curso')?.value || getFieldVal('input_natureza_curso', 'natureza_curso'),
        curso: getFieldVal('input_curso', 'curso'),
        carga_horaria: getFieldVal('input_carga_horaria', 'carga_horaria'),
        data: getFieldVal('input_data', 'data'),
        faculdade: getFieldVal('input_faculdade', 'faculdade'),
        tipo_documento: primaryTipo,
        observacoes_conferencia: document.getElementById('input_obs')?.value.trim() || null,
        dados_extras: dadosExtras
      };

      const hasPix = isFinancial && (pixChave || pixE2eId || dadosExtras.pix_chave || dadosExtras.pix_e2e_id);
      if (hasPix) {
        res.pix_pagador_nome = pixPagadorNome || dadosExtras.pix_pagador_nome || null;
        res.pix_pagador_cpf_cnpj = pixPagadorCpfCnpj || dadosExtras.pix_pagador_cpf_cnpj || null;
        res.pix_pagador_banco = pixPagadorBanco || dadosExtras.pix_pagador_banco || null;
        res.pix_recebedor_nome = pixRecebedorNome || dadosExtras.pix_recebedor_nome || null;
        res.pix_recebedor_cpf_cnpj = pixRecebedorCpfCnpj || dadosExtras.pix_recebedor_cpf_cnpj || null;
        res.pix_recebedor_banco = pixRecebedorBanco || dadosExtras.pix_recebedor_banco || null;
        res.pix_chave = pixChave || dadosExtras.pix_chave || null;
        res.pix_e2e_id = pixE2eId || dadosExtras.pix_e2e_id || null;
        res.pix_autenticacao = pixAutenticacao || dadosExtras.pix_autenticacao || null;
      } else {
        res.pix_pagador_nome = null;
        res.pix_pagador_cpf_cnpj = null;
        res.pix_pagador_banco = null;
        res.pix_recebedor_nome = null;
        res.pix_recebedor_cpf_cnpj = null;
        res.pix_recebedor_banco = null;
        res.pix_chave = null;
        res.pix_e2e_id = null;
        res.pix_autenticacao = null;
      }

      delete res.data_criacao;
      return res;
    }

    function updateJsonView() {
      const current = getCurrentFormValues();
      document.getElementById('jsonViewer').innerText = JSON.stringify(current, null, 2);
    }

    async function saveCurrentDoc() {
      const updated = getCurrentFormValues();
      if (!updated) {
        showToast('Nenhum documento selecionado para salvar.', 'info');
        return;
      }
      const chkAprender = document.getElementById('chkAprenderRegra');
      const aprenderRegra = chkAprender ? chkAprender.checked : true;

      try {
        const resp = await fetch('/api/salvar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item: updated, aprender_regra: aprenderRegra })
        });
        if (!resp.ok) throw new Error('Erro ao salvar no servidor');

        const mainIdx = documents.findIndex(d => d.md5 === updated.md5);
        if (mainIdx !== -1) documents[mainIdx] = updated;
        filteredDocs[currentIndex] = updated;

        isDirty = false;
        showToast('Documento salvo com sucesso!', 'success');
        initMasterFilterLists();
        updateFacetFilters();
        updateCounters();
        renderSidebar();
        loadLearnedRulesCount();
      } catch (err) {
        showToast('Falha ao salvar: ' + err.message, 'error');
      }
    }

    async function approveAndNext() {
      const updated = getCurrentFormValues();
      if (!updated) {
        showToast('Nenhum documento selecionado para aprovar.', 'info');
        return;
      }
      updated.status_conferencia = 'aprovado';
      const chkAprender = document.getElementById('chkAprenderRegra');
      const aprenderRegra = chkAprender ? chkAprender.checked : true;
      
      try {
        const resp = await fetch('/api/salvar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item: updated, aprender_regra: aprenderRegra })
        });
        if (!resp.ok) throw new Error('Erro ao salvar aprovação');

        const mainIdx = documents.findIndex(d => d.md5 === updated.md5);
        if (mainIdx !== -1) documents[mainIdx] = updated;
        filteredDocs[currentIndex] = updated;

        showToast('Documento conferido e aprovado!', 'success');
        updateCounters();
        loadLearnedRulesCount();

        if (currentIndex < filteredDocs.length - 1) {
          selectDocument(currentIndex + 1);
        } else {
          renderSidebar();
          selectDocument(currentIndex);
        }
      } catch (err) {
        showToast('Falha ao aprovar: ' + err.message, 'error');
      }
    }

    // Gerenciamento do Modal de Regras Aprendidas da IA
    async function loadLearnedRulesCount() {
      try {
        const resp = await fetch('/api/regras-aprendidas');
        if (!resp.ok) return;
        const regras = await resp.json();
        const badge = document.getElementById('learnedRulesCount');
        if (badge) {
          badge.innerText = Array.isArray(regras) ? regras.length : 0;
        }
      } catch (e) {
        console.warn('Erro ao carregar contagem de regras:', e);
      }
    }

    async function openLearnedRulesModal() {
      const modal = document.getElementById('modalLearnedRules');
      if (!modal) return;
      modal.classList.remove('hidden');
      const container = document.getElementById('learnedRulesListContainer');
      if (container) {
        container.innerHTML = '<div class="text-center py-6 text-slate-400 text-xs italic"><i class="fa-solid fa-spinner fa-spin text-teal-400 mr-2"></i> Carregando regras aprendidas...</div>';
      }
      
      try {
        const resp = await fetch('/api/regras-aprendidas');
        if (!resp.ok) throw new Error('Falha ao obter regras');
        const regras = await resp.json();
        renderLearnedRulesList(regras);
      } catch (err) {
        if (container) {
          container.innerHTML = `<div class="p-3 text-center text-rose-400 text-xs">Erro ao carregar regras: ${err.message}</div>`;
        }
      }
    }

    function closeLearnedRulesModal() {
      const modal = document.getElementById('modalLearnedRules');
      if (modal) modal.classList.add('hidden');
    }

    function renderLearnedRulesList(regras) {
      const container = document.getElementById('learnedRulesListContainer');
      if (!container) return;
      const countEl = document.getElementById('learnedRulesCount');
      if (countEl) countEl.innerText = Array.isArray(regras) ? regras.length : 0;

      if (!Array.isArray(regras) || regras.length === 0) {
        container.innerHTML = `
          <div class="text-center py-8 px-4 bg-slate-950/40 rounded-lg border border-slate-800/80">
            <i class="fa-solid fa-brain text-slate-600 text-3xl mb-2"></i>
            <p class="text-slate-300 font-medium text-xs">Nenhuma regra aprendida no momento</p>
            <p class="text-slate-500 text-[11px] mt-1 max-w-sm mx-auto">
              Ao conferir ou aprovar documentos com a opção "Aprender com esta conferência" marcada, os novos padrões identificados serão listados aqui.
            </p>
          </div>
        `;
        return;
      }

      let html = '<div class="divide-y divide-slate-800/80">';
      regras.forEach(r => {
        const domBadgeColor = r.dominio === 'financeiro' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' :
                             r.dominio === 'veicular' ? 'bg-orange-500/20 text-orange-300 border-orange-500/30' :
                             r.dominio === 'profissional' ? 'bg-sky-500/20 text-sky-300 border-sky-500/30' :
                             r.dominio === 'identificacao' ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' :
                             r.dominio === 'juridico' ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                             'bg-indigo-500/20 text-indigo-300 border-indigo-500/30';
        
        html += `
          <div class="py-2.5 flex items-center justify-between gap-3 hover:bg-slate-800/30 px-2 rounded-lg transition">
            <div class="space-y-0.5 flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-mono text-teal-300 font-semibold text-xs truncate" title="${r.termo_chave || ''}">
                  <i class="fa-solid fa-key text-[10px] text-teal-500 mr-1"></i>"${r.termo_chave || ''}"
                </span>
                <i class="fa-solid fa-arrow-right text-[10px] text-slate-500"></i>
                <span class="text-slate-200 font-medium text-xs truncate">
                  ${r.valor_atribuido || ''}
                </span>
              </div>
              <div class="flex items-center gap-2 text-[10.5px] text-slate-400">
                <span class="px-1.5 py-0.2 rounded border font-mono ${domBadgeColor}">${r.dominio || 'academico'}</span>
                ${r.remover_pix ? '<span class="text-rose-400 flex items-center gap-0.5"><i class="fa-solid fa-ban text-[9px]"></i> Sem PIX</span>' : ''}
                <span class="text-slate-500">Confiança: ${Math.round((r.confianca || 1.0) * 100)}%</span>
                <span class="text-slate-600 font-mono text-[9px]">${r.criado_em ? r.criado_em.split('T')[0] : ''}</span>
              </div>
            </div>
            <button type="button" onclick="deleteLearnedRule(${r.id})"
                    class="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition"
                    title="Excluir regra aprendida">
              <i class="fa-regular fa-trash-can text-xs"></i>
            </button>
          </div>
        `;
      });
      html += '</div>';
      container.innerHTML = html;
    }

    async function deleteLearnedRule(ruleId) {
      if (!confirm('Deseja realmente remover esta regra aprendida da memória da IA?')) return;
      try {
        const resp = await fetch('/api/regras-aprendidas', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ acao: 'remover', id: ruleId })
        });
        const res = await resp.json();
        if (res.status === 'sucesso') {
          showToast('Regra removida com sucesso!', 'success');
          openLearnedRulesModal();
          loadLearnedRulesCount();
        } else {
          showToast('Erro ao remover regra.', 'error');
        }
      } catch (err) {
        showToast('Falha na comunicação: ' + err.message, 'error');
      }
    }

    function resetDocChanges() {
      if (currentIndex >= 0 && currentIndex < filteredDocs.length) {
        selectDocument(currentIndex);
        showToast('Alterações descartadas.', 'info');
      }
    }

    function updateClassificationButtonsState() {
      const btn1 = document.getElementById('btnProcessarDoc') || document.getElementById('btnOcrLlm');
      const btn2 = document.getElementById('btnProcessarDocHeader') || document.getElementById('btnOcrLlmHeader');
      if (!btn1 && !btn2) return;

      const doc = (filteredDocs && currentIndex >= 0 && currentIndex < filteredDocs.length) ? filteredDocs[currentIndex] : null;
      const isUnproc = isDocumentUnprocessed(doc);

      const prov = (currentAiProvider || systemConfig?.visualizador?.provider || 'ollama').toLowerCase();

      let modelName = '';
      if (prov === 'openai') {
        const sel = document.getElementById('cfgOpenaiModelSelect');
        const custom = document.getElementById('cfgOpenaiModelCustom');
        modelName = (sel && sel.value === 'custom' ? custom?.value : sel?.value) || systemConfig?.visualizador?.model || 'gpt-4o-mini';
      } else {
        const sel = document.getElementById('cfgOllamaModelSelect');
        const custom = document.getElementById('cfgOllamaModelCustom');
        modelName = (sel && sel.value === '__custom__' ? custom?.value : sel?.value) || systemConfig?.visualizador?.model || 'gemma4:e4b';
      }

      const shortModel = modelName.length > 14 ? modelName.substring(0, 12) + '..' : modelName;

      if (prov === 'openai') {
        if (btn2) {
          btn2.className = "px-2.5 py-1 bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 hover:text-cyan-200 border border-cyan-500/30 rounded text-xs font-medium flex items-center gap-1.5 transition shadow-sm";
          if (isUnproc) {
            btn2.title = `Classificar este documento pela primeira vez com OCR visual via OpenAI API (${modelName})`;
            btn2.innerHTML = `<i class="fa-solid fa-cloud text-cyan-400"></i> <span>Classificar (${shortModel})</span>`;
          } else {
            btn2.title = `Re-executar leitura e classificação completa deste documento com OCR visual via OpenAI API (${modelName})`;
            btn2.innerHTML = `<i class="fa-solid fa-cloud text-cyan-400"></i> <span>Reclassificar (${shortModel})</span>`;
          }
        }
        if (btn1) {
          btn1.className = "py-1.5 px-3 bg-cyan-600/15 hover:bg-cyan-600/25 text-cyan-300 hover:text-cyan-200 border border-cyan-500/30 rounded text-xs font-medium flex items-center justify-center gap-1.5 transition shadow-sm shrink-0";
          if (isUnproc) {
            btn1.title = `Ler texto e classificar este documento pela primeira vez com OCR visual via OpenAI API (${modelName})`;
            btn1.innerHTML = `<i class="fa-solid fa-cloud text-cyan-400"></i> <span>Ler e Classificar (OpenAI)</span>`;
          } else {
            btn1.title = `Re-executar leitura de texto e classificação completa deste documento com OCR visual via OpenAI API (${modelName})`;
            btn1.innerHTML = `<i class="fa-solid fa-cloud text-cyan-400"></i> <span>Reclassificar com OCR (OpenAI)</span>`;
          }
        }
      } else {
        if (btn2) {
          btn2.className = "px-2.5 py-1 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 hover:text-purple-200 border border-purple-500/30 rounded text-xs font-medium flex items-center gap-1.5 transition shadow-sm";
          if (isUnproc) {
            btn2.title = `Ler e classificar este documento pela primeira vez com OCR multimodal via Ollama Local (${modelName})`;
            btn2.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles text-purple-400"></i> <span>Ler e Classificar (${shortModel})</span>`;
          } else {
            btn2.title = `Re-executar leitura e classificação completa deste documento com OCR multimodal via Ollama Local (${modelName})`;
            btn2.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles text-purple-400"></i> <span>Reclassificar (${shortModel})</span>`;
          }
        }
        if (btn1) {
          btn1.className = "py-1.5 px-3 bg-purple-600/15 hover:bg-purple-600/25 text-purple-300 hover:text-purple-200 border border-purple-500/30 rounded text-xs font-medium flex items-center justify-center gap-1.5 transition shadow-sm shrink-0";
          if (isUnproc) {
            btn1.title = `Ler texto e classificar este documento pela primeira vez com OCR multimodal via Ollama Local (${modelName})`;
            btn1.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles text-purple-400"></i> <span>Ler e Classificar (OCR)</span>`;
          } else {
            btn1.title = `Re-executar leitura de texto e classificação completa deste documento com OCR multimodal via Ollama Local (${modelName})`;
            btn1.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles text-purple-400"></i> <span>Reclassificar com OCR</span>`;
          }
        }
      }
    }

    async function triggerProcessarDocumento() {
      if (!filteredDocs || filteredDocs.length === 0 || currentIndex < 0 || currentIndex >= filteredDocs.length) {
        showToast('Nenhum documento selecionado para classificação.', 'error');
        return;
      }
      const doc = filteredDocs[currentIndex];
      const targetMd5 = doc.md5;
      const isUnproc = isDocumentUnprocessed(doc);

      const prov = (currentAiProvider || systemConfig?.visualizador?.provider || 'ollama').toLowerCase();

      let modelName = '';
      if (prov === 'openai') {
        const sel = document.getElementById('cfgOpenaiModelSelect');
        const custom = document.getElementById('cfgOpenaiModelCustom');
        modelName = (sel && sel.value === 'custom' ? custom?.value : sel?.value) || systemConfig?.visualizador?.model || 'gpt-4o-mini';
      } else {
        const sel = document.getElementById('cfgOllamaModelSelect');
        const custom = document.getElementById('cfgOllamaModelCustom');
        modelName = (sel && sel.value === '__custom__' ? custom?.value : sel?.value) || systemConfig?.visualizador?.model || 'gemma4:e4b';
      }

      const openaiKeyInput = (document.getElementById('cfgOpenaiKey')?.value || '').trim();
      const hasKey = systemConfig?.visualizador?.has_openai_key || systemConfig?.classificador?.has_openai_key;

      if (prov === 'openai' && !openaiKeyInput && !hasKey) {
        showToast('Chave da API da OpenAI não detectada! Abra as Configurações (aba IA) para informá-la.', 'error');
        openConfigModal('ai');
        return;
      }

      const btn1 = document.getElementById('btnProcessarDoc') || document.getElementById('btnOcrLlm');
      const btn2 = document.getElementById('btnProcessarDocHeader') || document.getElementById('btnOcrLlmHeader');
      const originalHtml1 = btn1 ? btn1.innerHTML : '';
      const originalHtml2 = btn2 ? btn2.innerHTML : '';

      const spinColor = prov === 'openai' ? 'text-cyan-400' : 'text-purple-400';
      const provLabel = prov === 'openai' ? 'OpenAI API' : 'Ollama';
      const actionVerb = isUnproc ? 'Lendo e Classificando' : 'Relendo e Classificando';

      if (btn1) {
        btn1.disabled = true;
        btn1.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin ${spinColor}"></i> ${actionVerb} (${provLabel})...`;
        btn1.classList.add('opacity-75', 'cursor-not-allowed');
      }
      if (btn2) {
        btn2.disabled = true;
        btn2.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin ${spinColor}"></i> <span>${actionVerb}...</span>`;
        btn2.classList.add('opacity-75', 'cursor-not-allowed');
      }

      showToast(`Executando leitura integral e classificação com OCR via ${provLabel} (${modelName})...`, 'info');

      try {
        const isHybrid = !!(document.getElementById('cfgHybridMode')?.checked ?? systemConfig?.visualizador?.hybrid ?? systemConfig?.classificador?.hybrid ?? false);
        const hybridCloudModel = (document.getElementById('cfgHybridCloudModel')?.value || systemConfig?.visualizador?.hybrid_cloud_model || 'gpt-4o-mini').trim();
        const hybridKey = (document.getElementById('cfgHybridOpenaiKey')?.value || openaiKeyInput || '').trim();

        const payload = {
          md5: targetMd5,
          nome_arquivo: doc.nome_arquivo,
          provider: prov,
          model: modelName,
          force_ocr: true,
          hybrid: isHybrid,
          hybrid_cloud_model: hybridCloudModel
        };
        if (openaiKeyInput || hybridKey) {
          payload.openai_key = openaiKeyInput || hybridKey;
        }
        const customBaseUrl = (document.getElementById('cfgOpenaiBaseUrl')?.value || '').trim();
        if (customBaseUrl) {
          payload.openai_base_url = customBaseUrl;
        }
        const customOllamaUrl = (document.getElementById('cfgOllamaUrl')?.value || '').trim();
        if (customOllamaUrl) {
          payload.ollama_url = customOllamaUrl;
        }

        const resp = await fetch('/api/processar-documento', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const resData = await resp.json();
        if (!resp.ok || resData.status !== 'sucesso') {
          throw new Error(resData.mensagem || resData.erro || `Falha ao processar documento via ${provLabel}.`);
        }

        const novoItem = resData.item;
        // Atualiza no array principal documents
        const idxDocs = documents.findIndex(d => d.md5 === targetMd5);
        if (idxDocs !== -1) {
          documents[idxDocs] = novoItem;
        } else {
          documents.push(novoItem);
        }
        // Atualiza no array filtrado
        filteredDocs[currentIndex] = novoItem;

        // Atualiza formulário e JSON viewer com os dados atualizados
        selectDocument(currentIndex, true);
        applyFilter(true);

        // Invalida cache de texto do documento e recarrega a aba de OCR com a nova leitura integral
        if (docTextCache[targetMd5]) {
          delete docTextCache[targetMd5];
        }
        loadDocumentText(targetMd5, true);

        showToast(resData.mensagem || `Documento lido e classificado com sucesso via ${provLabel}!`, 'success');
      } catch (err) {
        console.error(`Erro na classificação via ${provLabel}:`, err);
        showToast(`Erro ao classificar: ${err.message}`, 'error');
      } finally {
        if (btn1) {
          btn1.disabled = false;
          btn1.innerHTML = originalHtml1;
          btn1.classList.remove('opacity-75', 'cursor-not-allowed');
        }
        if (btn2) {
          btn2.disabled = false;
          btn2.innerHTML = originalHtml2;
          btn2.classList.remove('opacity-75', 'cursor-not-allowed');
        }
        updateClassificationButtonsState();
      }
    }

    // Aliases para compatibilidade reversa
    const triggerOcrLlm = triggerProcessarDocumento;
    const updateOcrButtonsState = updateClassificationButtonsState;

    function navigateDoc(direction) {
      if (!filteredDocs || filteredDocs.length === 0) return;
      const target = currentIndex + direction;
      if (target >= 0 && target < filteredDocs.length) {
        selectDocument(target);
      }
    }

    function reloadPdf() {
      const doc = filteredDocs[currentIndex];
      if (!doc) return;
      loadMediaForDocument(doc, true);
      showToast('Visualizador recarregado.', 'info');
    }

    // -----------------------------------------------------------------------
    // Painel do Inspetor: 4 Abas Modernas (Dados, Dossiê, Texto OCR, Ficha)
    // -----------------------------------------------------------------------
    function switchInspectorTab(tab) {
      if (tab === 'form') tab = 'dados';
      if (tab === 'json') tab = 'ficha';

      currentInspectorTab = tab;

      const tabs = ['dados', 'dossie', 'texto', 'ficha'];
      tabs.forEach(t => {
        const btnId = `tabBtn${t.charAt(0).toUpperCase() + t.slice(1)}`;
        const viewId = `viewTab${t.charAt(0).toUpperCase() + t.slice(1)}`;
        const btn = document.getElementById(btnId);
        const view = document.getElementById(viewId);
        const isActive = (t === tab);

        if (btn) {
          if (isActive) {
            btn.className = "flex-1 min-w-[95px] px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 text-emerald-400 border border-slate-700/80 transition flex items-center justify-center gap-1.5 shadow-sm";
          } else {
            btn.className = "flex-1 min-w-[95px] px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition flex items-center justify-center gap-1.5";
          }
        }

        if (view) {
          if (isActive) {
            view.classList.remove('hidden');
          } else {
            view.classList.add('hidden');
          }
        }
      });

      const curDoc = (filteredDocs && currentIndex >= 0 && currentIndex < filteredDocs.length) ? filteredDocs[currentIndex] : null;

      if (tab === 'dossie') {
        renderDossierPagesGrid(curDoc);
      } else if (tab === 'texto') {
        if (curDoc && curDoc.md5) {
          loadDocumentText(curDoc.md5);
        }
      } else if (tab === 'ficha') {
        updateFichaTecnica(curDoc);
        updateJsonView();
      }
    }

    function switchTab(tab) {
      switchInspectorTab(tab);
    }

    // =========================================================================
    // ESTADO E CONTROLES DA ABA DOSSIÊ (SELEÇÃO DIRETA E RECLASSIFICAÇÃO)
    // =========================================================================
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

    function showToast(msg, type = 'success') {
      const toast = document.getElementById('toast');
      const toastMsg = document.getElementById('toastMsg');
      const toastIcon = document.getElementById('toastIcon');

      toastMsg.innerText = msg;
      if (type === 'error') {
        toastIcon.className = "fa-solid fa-triangle-exclamation text-rose-400 text-sm";
      } else if (type === 'info') {
        toastIcon.className = "fa-solid fa-circle-info text-blue-400 text-sm";
      } else {
        toastIcon.className = "fa-solid fa-circle-check text-emerald-400 text-sm";
      }

      toast.classList.remove('translate-y-20', 'opacity-0');
      toast.classList.add('translate-y-0', 'opacity-100');

      setTimeout(() => {
        toast.classList.remove('translate-y-0', 'opacity-100');
        toast.classList.add('translate-y-20', 'opacity-0');
      }, 3000);
    }

    function setupKeyboardShortcuts() {
      window.addEventListener('keydown', (e) => {
        const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);

        if (e.key === 'Escape') {
          const lbModal = document.getElementById('galleryLightboxModal');
          if (lbModal && !lbModal.classList.contains('hidden')) {
            closeGalleryLightbox();
            return;
          }
          if (openFilterPopoverId) {
            closeAllFilterPopovers();
            return;
          }
          const picker = document.getElementById('folderPickerModal');
          if (picker && !picker.classList.contains('hidden')) {
            closeFolderPicker();
            return;
          }
          const modal = document.getElementById('configModal');
          if (modal && !modal.classList.contains('hidden')) {
            closeConfigModal();
            return;
          }
          const bulkModal = document.getElementById('modalBulkTag');
          if (bulkModal && !bulkModal.classList.contains('hidden')) {
            closeBulkTagModal();
            return;
          }
          if (selectedMd5s.size > 0) {
            clearBulkSelection();
            return;
          }
        }

        if (e.ctrlKey && e.key === 'Enter') {
          e.preventDefault();
          approveAndNext();
        } else if (e.ctrlKey && e.key === 's') {
          e.preventDefault();
          saveCurrentDoc();
        } else if (!isInput) {
          const lbModal = document.getElementById('galleryLightboxModal');
          const isLightboxOpen = lbModal && !lbModal.classList.contains('hidden');

          if (isLightboxOpen) {
            if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
              e.preventDefault();
              navigateLightbox(-1);
            } else if (e.key === 'ArrowRight' || e.key === 'PageDown') {
              e.preventDefault();
              navigateLightbox(1);
            }
          } else if (typeof currentMainTab !== 'undefined' && currentMainTab === 'galeria') {
            const sorted = getSortedGalleryDocs();
            const totalPages = Math.ceil(sorted.length / galleryPageSize) || 1;
            if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
              if (galleryCurrentPage > 1) {
                e.preventDefault();
                changeGalleryPage(galleryCurrentPage - 1);
              }
            } else if (e.key === 'ArrowRight' || e.key === 'PageDown') {
              if (galleryCurrentPage < totalPages) {
                e.preventDefault();
                changeGalleryPage(galleryCurrentPage + 1);
              }
            }
          } else {
            if (e.key === 'ArrowLeft' || e.key === '[') {
              navigateDoc(-1);
            } else if (e.key === 'ArrowRight' || e.key === ']') {
              navigateDoc(1);
            }
          }
        }
      });
    }

    // =========================================================================
    // GERENCIAMENTO DE CONFIGURAÇÃO & PROCESSAMENTO EM LOTE
    // =========================================================================
    let systemConfig = null;
    let detectedEnvironments = [];
    let activeBatchPolling = null;
    let lastBatchStatus = null;
    let isBatchRunning = false;
    let currentAiProvider = 'ollama';

    function openConfigModal(initialTab = 'folders') {
      const modal = document.getElementById('configModal');
      if (modal) {
        modal.classList.remove('hidden');
        switchConfigTab(initialTab);
        loadSystemConfig();
        startBatchPolling();
      }
    }

    function closeConfigModal() {
      const modal = document.getElementById('configModal');
      if (modal) {
        modal.classList.add('hidden');
        if (!isBatchRunning) {
          stopBatchPolling();
        }
      }
    }

    function switchConfigTab(tabName) {
      const tabs = ['folders', 'ai', 'batch'];
      tabs.forEach(t => {
        const btn = document.getElementById('tabBtn' + t.charAt(0).toUpperCase() + t.slice(1));
        const content = document.getElementById('tabContent' + t.charAt(0).toUpperCase() + t.slice(1));
        if (t === tabName) {
          if (btn) {
            btn.className = "px-4 py-2 border-b-2 border-emerald-500 text-emerald-400 font-semibold flex items-center gap-2 transition";
          }
          if (content) content.classList.remove('hidden');
        } else {
          if (btn) {
            btn.className = "px-4 py-2 border-b-2 border-transparent text-slate-400 hover:text-slate-200 flex items-center gap-2 transition";
          }
          if (content) content.classList.add('hidden');
        }
      });
    }

    function setAiProvider(provider) {
      currentAiProvider = provider;
      const btnOllama = document.getElementById('btnProviderOllama');
      const btnOpenai = document.getElementById('btnProviderOpenai');
      const secOllama = document.getElementById('sectionOllama');
      const secOpenai = document.getElementById('sectionOpenai');

      if (provider === 'ollama') {
        if (btnOllama) {
          btnOllama.className = "flex items-center justify-center gap-2.5 p-3 rounded-lg border border-emerald-500/50 bg-emerald-500/10 text-emerald-300 font-medium text-xs transition";
        }
        if (btnOpenai) {
          btnOpenai.className = "flex items-center justify-center gap-2.5 p-3 rounded-lg border border-slate-800 bg-slate-950/60 text-slate-400 font-medium text-xs transition hover:border-slate-700";
        }
        if (secOllama) secOllama.classList.remove('hidden');
        if (secOpenai) secOpenai.classList.add('hidden');
      } else {
        if (btnOllama) {
          btnOllama.className = "flex items-center justify-center gap-2.5 p-3 rounded-lg border border-slate-800 bg-slate-950/60 text-slate-400 font-medium text-xs transition hover:border-slate-700";
        }
        if (btnOpenai) {
          btnOpenai.className = "flex items-center justify-center gap-2.5 p-3 rounded-lg border border-cyan-500/50 bg-cyan-500/10 text-cyan-300 font-medium text-xs transition";
        }
        if (secOllama) secOllama.classList.add('hidden');
        if (secOpenai) secOpenai.classList.remove('hidden');
      }
      updateOcrButtonsState();
    }

    function togglePasswordVisibility(inputId, btn) {
      const input = document.getElementById(inputId);
      if (!input) return;
      if (input.type === 'password') {
        input.type = 'text';
        btn.innerHTML = '<i class="fa-solid fa-eye-slash"></i>';
      } else {
        input.type = 'password';
        btn.innerHTML = '<i class="fa-solid fa-eye"></i>';
      }
    }

    function toggleHybridOptions() {
      const isChecked = !!document.getElementById('cfgHybridMode')?.checked;
      const container = document.getElementById('hybridOptionsContainer');
      if (container) {
        if (isChecked) container.classList.remove('hidden');
        else container.classList.add('hidden');
      }
      const batchToggle = document.getElementById('cfgBatchHybridToggle');
      if (batchToggle && batchToggle.checked !== isChecked) {
        batchToggle.checked = isChecked;
      }
      const batchStatus = document.getElementById('cfgBatchHybridStatusBadge');
      if (batchStatus) {
        batchStatus.innerText = isChecked ? 'Ativado (Ollama ➔ Nuvem)' : 'Desligado';
        batchStatus.className = isChecked 
          ? 'text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full border border-amber-500/40 font-semibold'
          : 'text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full border border-slate-700 font-normal';
      }
    }

    function syncHybridFromBatch(checked) {
      const hybridCheck = document.getElementById('cfgHybridMode');
      if (hybridCheck) {
        hybridCheck.checked = checked;
        toggleHybridOptions();
      }
    }

    async function loadSystemConfig() {
      try {
        const res = await fetch('/api/config');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        systemConfig = data;

        const classif = data.classificador || {};
        const vis = data.visualizador || {};

        // 1. Pastas
        const inPdf = document.getElementById('cfgInputPdfDir');
        if (inPdf) inPdf.value = classif.input || vis.pdf_dir || './pdf';

        const inJson = document.getElementById('cfgInputJsonPath');
        if (inJson) inJson.value = vis.json_path || classif.output_dir || './saida/joakindex.json';

        const countP = document.getElementById('cfgCountPdfs');
        if (countP) countP.innerText = data.pdf_count ?? (data.current_pdf_count ?? 0);

        const countD = document.getElementById('cfgCountDocs');
        if (countD) countD.innerText = data.doc_count ?? (data.current_doc_count ?? 0);

        // 2. Provedor de IA
        const prov = vis.provider || classif.provider || 'ollama';
        setAiProvider(prov);

        // Ollama URL
        const inOllamaUrl = document.getElementById('cfgOllamaUrl');
        if (inOllamaUrl) inOllamaUrl.value = vis.ollama_url || classif.ollama_url || 'http://localhost:11434';

        // Ambientes Ollama
        detectedEnvironments = data.environments || [];
        populateOllamaEnvironments(classif.docker, vis.model || classif.model);

        // OpenAI
        const inOpenaiKey = document.getElementById('cfgOpenaiKey');
        const keyStatus = document.getElementById('cfgOpenaiKeyStatus');
        const hasOpenaiKey = vis.has_openai_key || classif.has_openai_key;
        const maskedKey = vis.openai_key_masked || classif.openai_key_masked;

        if (hasOpenaiKey) {
          if (keyStatus) keyStatus.innerHTML = '<span class="text-emerald-400 font-semibold"><i class="fa-solid fa-check"></i> Chave detectada</span>';
          if (inOpenaiKey && maskedKey) inOpenaiKey.placeholder = maskedKey;
        } else {
          if (keyStatus) keyStatus.innerHTML = '<span class="text-slate-500">Nenhuma chave detectada</span>';
          if (inOpenaiKey) inOpenaiKey.placeholder = 'sk-...';
        }

        const inOpenaiBaseUrl = document.getElementById('cfgOpenaiBaseUrl');
        if (inOpenaiBaseUrl) inOpenaiBaseUrl.value = vis.openai_base_url || classif.openai_base_url || '';

        const selOpenaiModel = document.getElementById('cfgOpenaiModelSelect');
        const customOpenaiModel = document.getElementById('cfgOpenaiModelCustom');
        const currentOpenaiModel = (prov === 'openai' ? (vis.model || classif.model) : classif.model) || 'gpt-4o-mini';
        if (selOpenaiModel) {
          const known = ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'o3-mini'];
          if (known.includes(currentOpenaiModel)) {
            selOpenaiModel.value = currentOpenaiModel;
            if (customOpenaiModel) customOpenaiModel.style.display = 'none';
          } else {
            selOpenaiModel.value = 'custom';
            if (customOpenaiModel) {
              customOpenaiModel.style.display = 'block';
              customOpenaiModel.value = currentOpenaiModel;
            }
          }
        }

        // Atualiza estado visual e títulos dos botões de OCR
        updateOcrButtonsState();

        // 3. Execução em Lote
        const workers = classif.workers || 1;
        const wRange = document.getElementById('cfgWorkersRange');
        const wVal = document.getElementById('cfgWorkersVal');
        if (wRange) wRange.value = workers;
        if (wVal) wVal.innerText = workers;

        const maxP = document.getElementById('cfgMaxPages');
        if (maxP) maxP.value = classif.max_pages || 4;

        const skipO = document.getElementById('cfgSkipOcr');
        if (skipO) skipO.checked = !!classif.skip_ocr;

        // 4. Modo Híbrido em Cascata (Ollama ➔ OpenAI)
        const isHybrid = !!(classif.hybrid ?? vis.hybrid ?? false);
        const hybridCheck = document.getElementById('cfgHybridMode');
        if (hybridCheck) hybridCheck.checked = isHybrid;
        const hybridModel = classif.hybrid_cloud_model || vis.hybrid_cloud_model || 'gpt-4o-mini';
        const inHybridModel = document.getElementById('cfgHybridCloudModel');
        if (inHybridModel) inHybridModel.value = hybridModel;
        toggleHybridOptions();

        // Atualiza estado do lote
        if (data.batch_status) {
          updateBatchUI(data.batch_status);
        }

      } catch (err) {
        console.error('Erro ao carregar configurações /api/config:', err);
      }
    }

    function populateOllamaEnvironments(currentDocker = null, currentModel = null) {
      const select = document.getElementById('cfgOllamaEnvSelect');
      if (!select) return;

      select.innerHTML = '';
      if (!detectedEnvironments || detectedEnvironments.length === 0) {
        const opt = document.createElement('option');
        opt.value = '__default__';
        opt.innerText = 'Ollama Padrão (http://localhost:11434)';
        select.appendChild(opt);
      } else {
        detectedEnvironments.forEach((env, idx) => {
          const opt = document.createElement('option');
          opt.value = String(idx);
          let label = env.name || env.type;
          if (env.models && env.models.length > 0) {
            label += ` (${env.models.length} modelo${env.models.length > 1 ? 's' : ''})`;
          }
          opt.innerText = label;
          if (currentDocker && env.container === currentDocker) {
            opt.selected = true;
          }
          select.appendChild(opt);
        });
      }

      const optCustom = document.createElement('option');
      optCustom.value = '__custom__';
      optCustom.innerText = '⚙️ Outro / URL Personalizada...';
      select.appendChild(optCustom);

      onOllamaEnvChanged(currentModel);
    }

    function onOllamaEnvChanged(desiredModel = null) {
      const select = document.getElementById('cfgOllamaEnvSelect');
      const descEl = document.getElementById('cfgOllamaEnvDesc');
      const modelSelect = document.getElementById('cfgOllamaModelSelect');
      const modelCustom = document.getElementById('cfgOllamaModelCustom');
      const urlInput = document.getElementById('cfgOllamaUrl');
      if (!select || !modelSelect) return;

      const val = select.value;
      let env = null;

      if (val !== '__default__' && val !== '__custom__' && detectedEnvironments[parseInt(val, 10)]) {
        env = detectedEnvironments[parseInt(val, 10)];
      }

      if (env) {
        if (descEl) descEl.innerText = env.description || '';
        if (urlInput && env.base_url) urlInput.value = env.base_url;

        modelSelect.innerHTML = '';
        const models = env.models || [];
        const modelsDisplay = env.models_display || [];

        if (models.length > 0) {
          models.forEach((m, i) => {
            const mOpt = document.createElement('option');
            mOpt.value = m;
            mOpt.innerText = modelsDisplay[i] || m;
            if (desiredModel && m === desiredModel) mOpt.selected = true;
            modelSelect.appendChild(mOpt);
          });
        } else {
          const mOpt = document.createElement('option');
          mOpt.value = 'gemma4:e4b';
          mOpt.innerText = 'gemma4:e4b (Padrão sugerido)';
          modelSelect.appendChild(mOpt);
        }

        const mOptCustom = document.createElement('option');
        mOptCustom.value = '__custom__';
        mOptCustom.innerText = 'Digitar outro modelo...';
        modelSelect.appendChild(mOptCustom);

      } else {
        if (descEl) descEl.innerText = 'Ambiente HTTP direto ou personalizado.';
        modelSelect.innerHTML = `
          <option value="gemma4:e4b">gemma4:e4b (Padrão)</option>
          <option value="__custom__">Digitar outro modelo...</option>
        `;
      }

      onOllamaModelSelectChanged(desiredModel);
    }

    function onOllamaModelSelectChanged(desiredModel = null) {
      const modelSelect = document.getElementById('cfgOllamaModelSelect');
      const modelCustom = document.getElementById('cfgOllamaModelCustom');
      if (!modelSelect || !modelCustom) return;

      if (modelSelect.value === '__custom__') {
        modelCustom.style.display = 'block';
        if (desiredModel && desiredModel !== '__custom__') modelCustom.value = desiredModel;
      } else {
        modelCustom.style.display = 'none';
      }
      updateOcrButtonsState();
    }

    function onOpenaiModelChanged() {
      const sel = document.getElementById('cfgOpenaiModelSelect');
      const custom = document.getElementById('cfgOpenaiModelCustom');
      if (!sel || !custom) return;
      if (sel.value === 'custom') {
        custom.style.display = 'block';
      } else {
        custom.style.display = 'none';
      }
      updateOcrButtonsState();
    }

    async function detectEnvironments() {
      showToast('Detectando ambientes Ollama...', 'info');
      try {
        const res = await fetch('/api/environments');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        detectedEnvironments = await res.json();
        populateOllamaEnvironments();
        showToast('Detecção de ambientes concluída!', 'success');
      } catch (err) {
        showToast('Falha ao detectar ambientes: ' + err.message, 'error');
      }
    }

    function collectConfigPayload() {
      const pdfDir = (document.getElementById('cfgInputPdfDir')?.value || '').trim();
      const jsonPath = (document.getElementById('cfgInputJsonPath')?.value || '').trim();
      const workers = parseInt(document.getElementById('cfgWorkersRange')?.value || '1', 10);
      const maxPages = parseInt(document.getElementById('cfgMaxPages')?.value || '4', 10);
      const skipOcr = !!document.getElementById('cfgSkipOcr')?.checked;

      let model = '';
      let docker = null;
      let ollamaUrl = (document.getElementById('cfgOllamaUrl')?.value || '').trim() || 'http://localhost:11434';
      let openaiKey = (document.getElementById('cfgOpenaiKey')?.value || '').trim();
      let openaiBaseUrl = (document.getElementById('cfgOpenaiBaseUrl')?.value || '').trim();

      if (currentAiProvider === 'ollama') {
        const envSelect = document.getElementById('cfgOllamaEnvSelect');
        if (envSelect && envSelect.value !== '__default__' && envSelect.value !== '__custom__') {
          const env = detectedEnvironments[parseInt(envSelect.value, 10)];
          if (env && env.container) {
            docker = env.container;
          }
        }
        const mSel = document.getElementById('cfgOllamaModelSelect');
        if (mSel && mSel.value === '__custom__') {
          model = (document.getElementById('cfgOllamaModelCustom')?.value || '').trim();
        } else if (mSel) {
          model = mSel.value;
        }
        if (!model) model = 'gemma4:e4b';
      } else {
        const mSel = document.getElementById('cfgOpenaiModelSelect');
        if (mSel && mSel.value === 'custom') {
          model = (document.getElementById('cfgOpenaiModelCustom')?.value || '').trim();
        } else if (mSel) {
          model = mSel.value;
        }
        if (!model) model = 'gpt-4o-mini';
      }

      const hybrid = !!document.getElementById('cfgHybridMode')?.checked;
      const hybridCloudModel = (document.getElementById('cfgHybridCloudModel')?.value || 'gpt-4o-mini').trim();
      const hybridKey = (document.getElementById('cfgHybridOpenaiKey')?.value || '').trim();
      if (!openaiKey && hybridKey) {
        openaiKey = hybridKey;
      }

      return {
        classificador: {
          input: pdfDir,
          output_dir: jsonPath,
          provider: currentAiProvider,
          model: model,
          docker: docker,
          ollama_url: ollamaUrl,
          openai_key: openaiKey || undefined,
          openai_base_url: openaiBaseUrl || undefined,
          workers: workers,
          max_pages: maxPages,
          skip_ocr: skipOcr,
          hybrid: hybrid,
          hybrid_cloud_model: hybridCloudModel
        },
        visualizador: {
          pdf_dir: pdfDir,
          json_path: jsonPath,
          provider: currentAiProvider,
          model: model,
          ollama_url: ollamaUrl,
          openai_key: openaiKey || undefined,
          openai_base_url: openaiBaseUrl || undefined,
          hybrid: hybrid,
          hybrid_cloud_model: hybridCloudModel
        }
      };
    }

    async function saveConfiguration(notifyUser = true) {
      const payload = collectConfigPayload();
      try {
        const res = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();

        const countP = document.getElementById('cfgCountPdfs');
        if (countP && result.pdf_count !== undefined) countP.innerText = result.pdf_count;
        const countD = document.getElementById('cfgCountDocs');
        if (countD && result.doc_count !== undefined) countD.innerText = result.doc_count;

        if (result.provider) {
          if (!systemConfig) systemConfig = {};
          if (!systemConfig.visualizador) systemConfig.visualizador = {};
          systemConfig.visualizador.provider = result.provider;
          systemConfig.visualizador.model = result.model;
        }
        updateOcrButtonsState();

        loadDocuments();

        if (notifyUser) {
          showToast(result.mensagem || 'Configurações salvas com sucesso!', 'success');
        }
        return true;
      } catch (err) {
        showToast('Erro ao salvar configurações: ' + err.message, 'error');
        return false;
      }
    }

    async function testAndRefreshFolders() {
      showToast('Verificando pastas e indexando...', 'info');
      await saveConfiguration(false);
      await loadSystemConfig();
      showToast('Pastas verificadas e contagens atualizadas!', 'success');
    }

    async function resetToFactoryDefaults() {
      const ok = confirm(
        'Deseja realmente restaurar todas as configurações para os padrões de fábrica neutros (./pdf e ./saida)?\n\nIsso limpará personalizações de caminhos e modelos.'
      );
      if (!ok) return;

      try {
        const res = await fetch('/api/config/reset', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const result = await res.json();
        showToast('Padrões de fábrica restaurados com sucesso!', 'info');
        await loadSystemConfig();
        await loadDocuments();
      } catch (err) {
        showToast('Erro ao restaurar padrões: ' + err.message, 'error');
      }
    }

    async function startBatch() {
      const saved = await saveConfiguration(false);
      if (!saved) return;

      const modeRadio = document.querySelector('input[name="batchMode"]:checked');
      const mode = modeRadio ? modeRadio.value : 'incremental';

      const payload = collectConfigPayload().classificador;
      payload.reprocess_ocr = (mode === 'reprocess_ocr');
      payload.force = (mode === 'force');

      try {
        const res = await fetch('/api/batch/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (!res.ok || result.status === 'erro') {
          showToast(result.mensagem || 'Falha ao iniciar lote.', 'error');
          return;
        }

        showToast(result.mensagem || 'Processamento em lote iniciado!', 'success');
        switchConfigTab('batch');
        startBatchPolling();
      } catch (err) {
        showToast('Erro ao conectar ao servidor: ' + err.message, 'error');
      }
    }

    async function stopBatch() {
      const ok = confirm('Deseja realmente interromper o processamento em lote?\nO progresso atual será salvo com segurança.');
      if (!ok) return;

      try {
        const res = await fetch('/api/batch/stop', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const result = await res.json();
        showToast(result.mensagem || 'Sinal de interrupção enviado.', 'info');
      } catch (err) {
        showToast('Erro ao solicitar parada: ' + err.message, 'error');
      }
    }

    function clearBatchLogs() {
      const logContainer = document.getElementById('batchTerminalLogs');
      if (logContainer) logContainer.innerHTML = '<div class="text-slate-500 italic">Logs limpos.</div>';
    }

    function startBatchPolling() {
      if (activeBatchPolling) return;
      pollBatchStatus();
      activeBatchPolling = setInterval(pollBatchStatus, 1500);
    }

    function stopBatchPolling() {
      if (activeBatchPolling) {
        clearInterval(activeBatchPolling);
        activeBatchPolling = null;
      }
    }

    async function checkBatchStatusOnLoad() {
      try {
        const res = await fetch('/api/batch/status');
        if (!res.ok) return;
        const status = await res.json();
        updateBatchUI(status);
        if (status.is_running) {
          startBatchPolling();
        }
      } catch (err) {
        // Servidor iniciando ou offline
      }
    }

    async function pollBatchStatus() {
      try {
        const res = await fetch('/api/batch/status');
        if (!res.ok) return;
        const status = await res.json();
        updateBatchUI(status);
      } catch (err) {
        console.warn('Erro ao consultar /api/batch/status:', err);
      }
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function formatTime(seconds) {
      if (!seconds || isNaN(seconds)) return '00:00';
      const m = Math.floor(seconds / 60);
      const s = seconds % 60;
      return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }

    function updateBatchUI(status) {
      if (!status) return;
      const wasRunning = isBatchRunning;
      isBatchRunning = !!status.is_running;

      // 1. Badge animado no topo
      const headerBadge = document.getElementById('batchHeaderBadge');
      const headerBadgeText = document.getElementById('batchHeaderBadgeText');
      const batchTabBadge = document.getElementById('batchTabBadge');

      if (headerBadge) {
        if (isBatchRunning) {
          headerBadge.style.display = 'flex';
          const toProc = status.to_process_count || 0;
          const proc = status.processed_count || 0;
          if (headerBadgeText) {
            headerBadgeText.innerText = `Lote: ${status.percentage || 0}% (${proc}/${toProc})`;
          }
        } else {
          headerBadge.style.display = 'none';
        }
      }

      if (batchTabBadge) {
        if (isBatchRunning) batchTabBadge.classList.remove('hidden');
        else batchTabBadge.classList.add('hidden');
      }

      // 2. Botões Iniciar / Interromper
      const btnStart = document.getElementById('btnBatchStart');
      const btnStop = document.getElementById('btnBatchStop');

      if (btnStart) {
        btnStart.disabled = isBatchRunning;
        if (isBatchRunning) {
          btnStart.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
          btnStart.classList.remove('opacity-50', 'cursor-not-allowed');
        }
      }

      if (btnStop) {
        btnStop.style.display = isBatchRunning ? 'flex' : 'none';
      }

      // 3. Status Pill & Mensagens
      const pill = document.getElementById('batchModalStatusPill');
      const statusIcon = document.getElementById('batchLiveStatusIcon');
      const statusTitle = document.getElementById('batchLiveStatusTitle');
      const liveMsg = document.getElementById('batchLiveMessage');
      const livePct = document.getElementById('batchLivePercent');
      const liveBar = document.getElementById('batchLiveBar');
      const liveTime = document.getElementById('batchLiveTime');

      const st = status.status || 'idle';
      let pillText = 'Pronto';
      let pillClass = 'text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full border border-slate-700 font-normal';
      let iconColor = 'bg-slate-500';

      if (st === 'running' || st === 'indexing') {
        pillText = st === 'indexing' ? 'Indexando' : 'Executando';
        pillClass = 'text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full border border-amber-500/40 font-semibold animate-pulse';
        iconColor = 'bg-amber-400 animate-ping';
      } else if (st === 'completed') {
        pillText = 'Concluído';
        pillClass = 'text-[10px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-500/40 font-semibold';
        iconColor = 'bg-emerald-400';
      } else if (st === 'stopped') {
        pillText = 'Interrompido';
        pillClass = 'text-[10px] bg-rose-500/20 text-rose-300 px-2 py-0.5 rounded-full border border-rose-500/40 font-semibold';
        iconColor = 'bg-rose-400';
      } else if (st === 'error') {
        pillText = 'Erro';
        pillClass = 'text-[10px] bg-rose-600/30 text-rose-300 px-2 py-0.5 rounded-full border border-rose-500/50 font-semibold';
        iconColor = 'bg-rose-500';
      }

      if (pill) {
        pill.innerText = pillText;
        pill.className = pillClass;
      }
      if (statusIcon) statusIcon.className = `w-2.5 h-2.5 rounded-full ${iconColor}`;
      if (statusTitle) statusTitle.innerText = `Status: ${pillText}`;
      if (liveMsg) liveMsg.innerText = status.message || 'Aguardando tarefas.';
      if (livePct) livePct.innerText = `${status.percentage || 0}%`;
      if (liveBar) liveBar.style.width = `${status.percentage || 0}%`;
      if (liveTime) liveTime.innerText = formatTime(status.elapsed_seconds || 0);

      // 4. Métricas Numéricas
      const statToProc = document.getElementById('batchStatToProcess');
      const statProc = document.getElementById('batchStatProcessed');
      const statSucc = document.getElementById('batchStatSuccess');
      const statErr = document.getElementById('batchStatErrors');

      if (statToProc) statToProc.innerText = status.to_process_count || 0;
      if (statProc) statProc.innerText = status.processed_count || 0;
      if (statSucc) statSucc.innerText = status.success_count || 0;
      if (statErr) statErr.innerText = status.error_count || 0;

      // 5. Console de Logs
      const logsContainer = document.getElementById('batchTerminalLogs');
      if (logsContainer && status.logs && status.logs.length > 0) {
        logsContainer.innerHTML = status.logs.map(l => {
          let lineClass = 'text-slate-300';
          if (l.includes('[✓]')) lineClass = 'text-emerald-400';
          else if (l.includes('[✗]') || l.includes('❌') || l.includes('Erro')) lineClass = 'text-rose-400 font-semibold';
          else if (l.includes('🛑') || l.includes('ℹ️')) lineClass = 'text-amber-300';
          return `<div class="${lineClass}">${escapeHtml(l)}</div>`;
        }).join('');
        logsContainer.scrollTop = logsContainer.scrollHeight;
      }

      // 6. Transição de Lote Concluído / Interrompido
      if (wasRunning && !isBatchRunning) {
        loadDocuments();
        if (st === 'completed') {
          showToast('Processamento em lote concluído com sucesso!', 'success');
        } else if (st === 'stopped') {
          showToast('Processamento em lote interrompido. Progresso salvo!', 'info');
        }
      }

      lastBatchStatus = status;
    }

    // =========================================================================
    // SELETOR DE PASTAS / EXPLORADOR DE DIRETÓRIOS (CAIXA SELECIONÁVEL)
    // =========================================================================
    let folderPickerTarget = 'pdf'; // 'pdf' | 'json'
    let folderPickerCurrentPath = '';
    let folderPickerSelectedPath = '';
    let folderPickerParentPath = null;
    let folderPickerDirs = [];

    function openFolderPicker(target = 'pdf') {
      folderPickerTarget = target;
      const modal = document.getElementById('folderPickerModal');
      const titleEl = document.getElementById('folderPickerTitle');
      const subTitleEl = document.getElementById('folderPickerSubtitle');

      if (target === 'pdf') {
        if (titleEl) titleEl.innerHTML = '<i class="fa-solid fa-folder-open text-amber-400 mr-1.5"></i> Selecionar Pasta dos PDFs de Entrada';
        if (subTitleEl) subTitleEl.innerText = 'Navegue pelas pastas onde estão os arquivos PDF para classificar e visualizar.';
      } else {
        if (titleEl) titleEl.innerHTML = '<i class="fa-solid fa-folder-open text-amber-400 mr-1.5"></i> Selecionar Pasta de Saída / Arquivo JSON';
        if (subTitleEl) subTitleEl.innerText = 'Navegue até a pasta onde deseja salvar os arquivos JSON consolidados e individuais.';
      }

      let startPath = '';
      if (target === 'pdf') {
        startPath = (document.getElementById('cfgInputPdfDir')?.value || '').trim();
      } else {
        startPath = (document.getElementById('cfgInputJsonPath')?.value || '').trim();
      }

      if (modal) modal.classList.remove('hidden');
      const filterInput = document.getElementById('folderPickerFilterInput');
      if (filterInput) filterInput.value = '';

      fetchFolderList(startPath);
    }

    function closeFolderPicker() {
      const modal = document.getElementById('folderPickerModal');
      if (modal) modal.classList.add('hidden');
    }

    async function fetchFolderList(targetPath = '') {
      const listContainer = document.getElementById('folderPickerList');
      if (listContainer) {
        listContainer.innerHTML = `
          <div class="flex flex-col items-center justify-center p-8 text-slate-400 space-y-2">
            <i class="fa-solid fa-circle-notch fa-spin text-emerald-400 text-xl"></i>
            <span class="text-xs">Carregando diretórios...</span>
          </div>
        `;
      }

      try {
        const query = new URLSearchParams();
        if (targetPath) query.set('path', targetPath);
        query.set('mode', folderPickerTarget);

        const res = await fetch(`/api/browse/dirs?${query.toString()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        folderPickerCurrentPath = data.current_path || '';
        folderPickerParentPath = data.parent_path || null;
        folderPickerSelectedPath = data.current_path || '';
        folderPickerDirs = data.directories || [];

        // Atualiza barra de caminho
        const pathInput = document.getElementById('folderPickerCurrentPathInput');
        if (pathInput) pathInput.value = folderPickerCurrentPath;

        // Botão subir
        const btnUp = document.getElementById('btnFolderPickerUp');
        if (btnUp) {
          btnUp.disabled = !folderPickerParentPath;
          if (!folderPickerParentPath) {
            btnUp.classList.add('opacity-40', 'cursor-not-allowed');
          } else {
            btnUp.classList.remove('opacity-40', 'cursor-not-allowed');
          }
        }

        // Atalhos rápidos
        renderFolderPickerQuickAccess(data.quick_access || []);

        // Botão Nativo Zenity
        const btnNative = document.getElementById('btnFolderPickerNative');
        if (btnNative) {
          if (data.zenity_available) {
            btnNative.classList.remove('hidden');
          } else {
            btnNative.classList.add('hidden');
          }
        }

        // Renderiza lista
        renderFolderList();
        updateFolderPickerPreview(folderPickerCurrentPath);

      } catch (err) {
        if (listContainer) {
          listContainer.innerHTML = `
            <div class="p-6 text-center text-rose-400 text-xs bg-rose-950/20 border border-rose-900/40 rounded-lg">
              <i class="fa-solid fa-triangle-exclamation text-base mb-1 block"></i>
              Erro ao carregar diretório: ${escapeHtml(err.message)}
            </div>
          `;
        }
      }
    }

    function renderFolderPickerQuickAccess(shortcuts) {
      const container = document.getElementById('folderPickerQuickAccess');
      if (!container) return;

      container.innerHTML = shortcuts.map(s => {
        const safePath = escapeHtml(s.path.replace(/\\/g, '\\\\'));
        return `
          <button type="button" onclick="navigateToFolder('${safePath}')"
                  class="px-2.5 py-1 bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white rounded border border-slate-800 hover:border-slate-700 text-[11px] flex items-center gap-1.5 transition">
            <i class="fa-solid ${s.icon || 'fa-folder'} text-amber-400/90 text-xs"></i>
            <span>${escapeHtml(s.name)}</span>
          </button>
        `;
      }).join('');
    }

    function renderFolderList() {
      const listContainer = document.getElementById('folderPickerList');
      const countLabel = document.getElementById('folderPickerCountLabel');
      const filterInput = document.getElementById('folderPickerFilterInput');
      const query = (filterInput?.value || '').trim().toLowerCase();

      if (!listContainer) return;

      const filtered = folderPickerDirs.filter(d => {
        if (!query) return true;
        return d.name.toLowerCase().includes(query);
      });

      if (countLabel) {
        countLabel.innerText = `${filtered.length} pasta${filtered.length !== 1 ? 's' : ''}`;
      }

      if (filtered.length === 0) {
        listContainer.innerHTML = `
          <div class="p-8 text-center text-slate-400 text-xs border border-dashed border-slate-800 rounded-lg space-y-2">
            <i class="fa-regular fa-folder-open text-2xl text-slate-600"></i>
            <div>Nenhuma subpasta encontrada aqui.</div>
            <div class="text-[11px] text-slate-500">
              Você pode clicar em <strong class="text-emerald-400">"Confirmar e Usar Esta Pasta"</strong> abaixo para selecionar este local, ou criar uma nova subpasta.
            </div>
          </div>
        `;
        return;
      }

      listContainer.innerHTML = filtered.map(d => {
        const isSelected = (folderPickerSelectedPath === d.path);
        const activeClass = isSelected
          ? 'bg-emerald-500/15 border-emerald-500/60 text-white shadow-sm'
          : 'bg-slate-950/50 hover:bg-slate-800/80 border-slate-800/80 text-slate-200';

        let badge = '';
        if (folderPickerTarget === 'pdf' && d.pdf_count > 0) {
          badge = `<span class="text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800/60 px-1.5 py-0.5 rounded font-mono font-medium">${d.pdf_count} PDFs</span>`;
        }

        const safePath = escapeHtml(d.path.replace(/\\/g, '\\\\'));
        return `
          <div onclick="selectFolderItem('${safePath}')" ondblclick="navigateToFolder('${safePath}')"
               class="group flex items-center justify-between px-3 py-2 rounded-lg border ${activeClass} transition cursor-pointer text-xs">
            <div class="flex items-center gap-2.5 min-w-0 flex-1">
              <i class="fa-solid fa-folder text-amber-400 text-sm group-hover:scale-110 transition shrink-0"></i>
              <span class="font-medium truncate">${escapeHtml(d.name)}</span>
              ${badge}
            </div>
            <div class="flex items-center gap-1 shrink-0 ml-2">
              <button type="button" onclick="event.stopPropagation(); navigateToFolder('${safePath}')" title="Entrar nesta pasta"
                      class="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded border border-slate-700 text-[11px] flex items-center gap-1 transition">
                <span>Abrir</span>
                <i class="fa-solid fa-arrow-right text-[10px] text-slate-400"></i>
              </button>
            </div>
          </div>
        `;
      }).join('');
    }

    function selectFolderItem(pathStr) {
      folderPickerSelectedPath = pathStr;
      renderFolderList();
      updateFolderPickerPreview(pathStr);
    }

    function navigateToFolder(pathStr) {
      if (!pathStr) return;
      fetchFolderList(pathStr);
    }

    function folderPickerGoUp() {
      if (folderPickerParentPath) {
        fetchFolderList(folderPickerParentPath);
      }
    }

    function refreshFolderPicker() {
      fetchFolderList(folderPickerCurrentPath);
    }

    function filterFolderList() {
      renderFolderList();
    }

    function updateFolderPickerPreview(pathStr) {
      const previewEl = document.getElementById('folderPickerSelectedPreview');
      if (previewEl) {
        previewEl.innerText = pathStr || 'Nenhuma selecionada';
        previewEl.title = pathStr;
      }
    }

    async function promptCreateFolder() {
      const name = prompt(`Criar nova subpasta dentro de:\n${folderPickerCurrentPath}\n\nDigite o nome da nova pasta:`);
      if (!name || !name.trim()) return;

      try {
        const res = await fetch('/api/browse/mkdir', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ parent: folderPickerCurrentPath, name: name.trim() })
        });
        const data = await res.json();
        if (!res.ok || data.status !== 'sucesso') {
          throw new Error(data.mensagem || 'Falha ao criar pasta');
        }
        showToast(`Pasta '${name.trim()}' criada com sucesso!`, 'success');
        await fetchFolderList(folderPickerCurrentPath);
        if (data.path) selectFolderItem(data.path);
      } catch (err) {
        showToast('Erro ao criar pasta: ' + err.message, 'error');
      }
    }

    async function pickNativeFolder() {
      const btnNative = document.getElementById('btnFolderPickerNative');
      const origHtml = btnNative ? btnNative.innerHTML : '';
      if (btnNative) {
        btnNative.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-indigo-300"></i> Abrindo...';
        btnNative.disabled = true;
      }

      try {
        const res = await fetch('/api/browse/native', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            initial_path: folderPickerCurrentPath,
            title: folderPickerTarget === 'pdf' ? 'Selecione a Pasta de PDFs' : 'Selecione a Pasta de Saída'
          })
        });
        const data = await res.json();
        if (data.status === 'sucesso' && data.path) {
          folderPickerSelectedPath = data.path;
          confirmFolderSelection();
        } else if (data.status === 'cancelado') {
          showToast('Seleção cancelada pelo usuário.', 'info');
        } else if (data.status === 'erro') {
          showToast(data.mensagem || 'Erro ao abrir diálogo nativo.', 'error');
        }
      } catch (err) {
        showToast('Erro no diálogo do sistema: ' + err.message, 'error');
      } finally {
        if (btnNative) {
          btnNative.innerHTML = origHtml;
          btnNative.disabled = false;
        }
      }
    }

    async function confirmFolderSelection() {
      const chosen = folderPickerSelectedPath || folderPickerCurrentPath;
      if (!chosen) {
        showToast('Nenhuma pasta selecionada!', 'error');
        return;
      }

      if (folderPickerTarget === 'pdf') {
        const inPdf = document.getElementById('cfgInputPdfDir');
        if (inPdf) inPdf.value = chosen;
      } else {
        const inJson = document.getElementById('cfgInputJsonPath');
        if (inJson) {
          if (chosen.toLowerCase().endsWith('.json')) {
            inJson.value = chosen;
          } else {
            const trimmed = chosen.replace(/\/+$/, '');
            inJson.value = `${trimmed}/joakindex.json`;
          }
        }
      }

      closeFolderPicker();
      showToast('Pasta atualizada!', 'success');
      await testAndRefreshFolders();
    }

    // =========================================================================
    // MÓDULO DE GALERIA DE DOCUMENTOS (MOSAICO DE THUMBNAILS - PAPERLESS-NGX)
    // =========================================================================
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
    let currentMainTab = 'galeria'; // 'galeria' | 'conferencia' | 'bi'
    let biState = {
      scope: 'classificados', // 'classificados' | 'todos' | 'aprovados'
      unitMode: 'ambos',      // 'ambos' | 'absoluto' | 'relativo'
      domain: 'geral',        // 'geral' | 'financeiro' | 'juridico' | 'identificacao' | 'cadastral' | 'academico'
      startupMode: 'geral',
      brackets: [1000, 10000, 100000],
      matrixDim: 'dominio_status',
      backendStats: null,
      initialized: false
    };
    let biChartInstances = {};

    function switchMainTab(tabName) {
      currentMainTab = tabName;
      try {
        localStorage.setItem('joakindex_active_tab', tabName);
      } catch (e) {}
      const btnConf = document.getElementById('tabMainConferencia');
      const btnGal = document.getElementById('tabMainGaleria');
      const btnBI = document.getElementById('tabMainBI');
      const viewConf = document.getElementById('viewConferencia');
      const viewGal = document.getElementById('viewGaleria');
      const viewBI = document.getElementById('viewBI');
      const confToolbar = document.getElementById('conferenciaToolbar');
      const galToolbar = document.getElementById('galeriaToolbar');
      const biToolbar = document.getElementById('biToolbar');

      // Reseta todos os botões de abas para o estado inativo
      if (btnConf) btnConf.className = 'px-2 sm:px-3.5 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 sm:gap-2 transition text-slate-400 hover:text-slate-200 hover:bg-slate-800/60';
      if (btnGal) btnGal.className = 'px-2 sm:px-3.5 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 sm:gap-2 transition text-slate-400 hover:text-slate-200 hover:bg-slate-800/60';
      if (btnBI) btnBI.className = 'px-2 sm:px-3.5 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 sm:gap-2 transition text-slate-400 hover:text-slate-200 hover:bg-slate-800/60';

      // Esconde todas as visões principais e toolbars
      if (viewConf) { viewConf.classList.add('hidden'); viewConf.classList.remove('flex'); }
      if (viewGal) { viewGal.classList.add('hidden'); viewGal.classList.remove('flex'); }
      if (viewBI) { viewBI.classList.add('hidden'); }
      if (confToolbar) { confToolbar.classList.add('hidden'); confToolbar.classList.remove('flex'); }
      if (galToolbar) { galToolbar.classList.add('hidden'); galToolbar.classList.remove('flex'); }
      if (biToolbar) { biToolbar.classList.add('hidden'); biToolbar.classList.remove('flex'); }

      if (tabName === 'conferencia') {
        if (btnConf) btnConf.className = 'px-2 sm:px-3.5 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 sm:gap-2 transition bg-emerald-600 text-white shadow';
        if (viewConf) { viewConf.classList.remove('hidden'); viewConf.classList.add('flex'); }
        if (confToolbar) { confToolbar.classList.remove('hidden'); confToolbar.classList.add('flex'); }
        if (typeof setMobileConferenceView === 'function') {
          if (window.innerWidth < 768) {
            setMobileConferenceView(currentMobileConfView || 'lista');
          } else {
            setMobileConferenceView('desktop');
          }
        }
        if (typeof filteredDocs !== 'undefined' && filteredDocs.length > 0 && typeof currentIndex !== 'undefined' && currentIndex >= 0) {
          const curDoc = filteredDocs[currentIndex];
          if (curDoc && curDoc.md5) {
            loadMediaForDocument(curDoc, false);
          }
        }
      } else if (tabName === 'galeria') {
        if (btnGal) btnGal.className = 'px-2 sm:px-3.5 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 sm:gap-2 transition bg-amber-600 text-white shadow';
        if (viewGal) { viewGal.classList.remove('hidden'); viewGal.classList.add('flex'); }
        if (galToolbar) { galToolbar.classList.remove('hidden'); galToolbar.classList.add('flex'); }
        renderGalleryView();
      } else if (tabName === 'bi') {
        if (btnBI) btnBI.className = 'px-2 sm:px-3.5 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 sm:gap-2 transition bg-cyan-600 text-white shadow';
        if (viewBI) { viewBI.classList.remove('hidden'); }
        if (biToolbar) { biToolbar.classList.remove('hidden'); biToolbar.classList.add('flex'); }
        renderBIDashboard();
      }
    }

    function initBIPreferences() {
      if (biState.initialized) return;
      try {
        const savedMode = localStorage.getItem('joakindex_bi_startup_mode');
        if (savedMode) biState.startupMode = savedMode;
        const savedBrackets = localStorage.getItem('joakindex_bi_brackets');
        if (savedBrackets) {
          const parsed = JSON.parse(savedBrackets);
          if (Array.isArray(parsed) && parsed.length >= 3) {
            biState.brackets = parsed.map(Number);
          }
        }
      } catch (e) {
        console.warn('Erro ao carregar preferências de BI:', e);
      }

      // Aplica modo de inicialização
      if (biState.startupMode === 'preponderante') {
        const domCounts = {};
        (documents || []).forEach(d => {
          const dom = safeString(d.dominio || 'outro').toLowerCase();
          domCounts[dom] = (domCounts[dom] || 0) + 1;
        });
        const total = (documents || []).length;
        let dominant = null;
        for (const [k, v] of Object.entries(domCounts)) {
          if (total > 0 && (v / total) > 0.5) {
            dominant = k;
            break;
          }
        }
        biState.domain = dominant || 'geral';
      } else if (biState.startupMode && biState.startupMode !== 'geral') {
        biState.domain = biState.startupMode;
      } else {
        biState.domain = 'geral';
      }

      // Atualiza visual do botão do domínio inicial
      const domains = ['geral', 'financeiro', 'veicular', 'juridico', 'identificacao', 'cadastral', 'academico'];
      domains.forEach(d => {
        const id = 'biDomain' + d.charAt(0).toUpperCase() + d.slice(1);
        const el = document.getElementById(id);
        if (el) {
          if (d === biState.domain) {
            el.className = 'px-2 py-1 rounded text-xs font-semibold transition bg-cyan-600 text-white shadow-xs';
          } else {
            el.className = 'px-2 py-1 rounded text-xs font-medium transition text-slate-400 hover:text-slate-200';
          }
        }
      });
      const badge = document.getElementById('biActiveDomainBadge');
      if (badge) {
        const labelMap = {
          'geral': 'Visão Geral Executiva',
          'financeiro': 'Domínio Financeiro',
          'veicular': 'Domínio Veicular / Trânsito',
          'juridico': 'Domínio Jurídico',
          'identificacao': 'Domínio Identificação',
          'cadastral': 'Domínio Cadastral',
          'academico': 'Domínio Acadêmico'
        };
        badge.innerText = labelMap[biState.domain] || biState.domain;
      }

      biState.initialized = true;
    }

    function setBIDomain(domain) {
      biState.domain = domain;
      const domains = ['geral', 'financeiro', 'veicular', 'juridico', 'identificacao', 'cadastral', 'academico'];
      domains.forEach(d => {
        const id = 'biDomain' + d.charAt(0).toUpperCase() + d.slice(1);
        const el = document.getElementById(id);
        if (el) {
          if (d === domain) {
            el.className = 'px-2 py-1 rounded text-xs font-semibold transition bg-cyan-600 text-white shadow-xs';
          } else {
            el.className = 'px-2 py-1 rounded text-xs font-medium transition text-slate-400 hover:text-slate-200';
          }
        }
      });
      const badge = document.getElementById('biActiveDomainBadge');
      if (badge) {
        const labelMap = {
          'geral': 'Visão Geral Executiva',
          'financeiro': 'Domínio Financeiro',
          'veicular': 'Domínio Veicular / Trânsito',
          'juridico': 'Domínio Jurídico',
          'identificacao': 'Domínio Identificação',
          'cadastral': 'Domínio Cadastral',
          'academico': 'Domínio Acadêmico'
        };
        badge.innerText = labelMap[domain] || domain;
      }
      const helperRow = document.getElementById('biAcademicHelperRow');
      if (helperRow) {
        if (domain === 'academico') helperRow.classList.remove('hidden');
        else helperRow.classList.add('hidden');
      }
      renderBIDashboard();
    }

    function setBIScope(scope) {
      biState.scope = scope;
      ['classificados', 'todos', 'aprovados'].forEach(s => {
        const id = 'biScope' + s.charAt(0).toUpperCase() + s.slice(1);
        const el = document.getElementById(id);
        if (el) {
          if (s === scope) {
            el.className = 'px-2.5 py-1 rounded text-xs font-medium transition bg-slate-800 text-slate-100 border border-slate-700 shadow-sm';
          } else {
            el.className = 'px-2.5 py-1 rounded text-xs font-medium transition text-slate-400 hover:text-slate-200';
          }
        }
      });
      renderBIDashboard();
    }

    function setBIUnitMode(mode) {
      biState.unitMode = mode;
      ['ambos', 'absoluto', 'relativo'].forEach(m => {
        const id = 'biUnit' + m.charAt(0).toUpperCase() + m.slice(1);
        const el = document.getElementById(id);
        if (el) {
          if (m === mode) {
            el.className = 'px-2 py-1 rounded text-xs font-medium transition bg-cyan-600/30 text-cyan-200 border border-cyan-500/40';
          } else {
            el.className = 'px-2 py-1 rounded text-xs font-medium transition text-slate-400 hover:text-slate-200';
          }
        }
      });
      renderBIDashboard();
    }

    function formatBIVal(val, total) {
      const pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0.0';
      if (biState.unitMode === 'absoluto') return `${val}`;
      if (biState.unitMode === 'relativo') return `${pct}%`;
      return `${val} (${pct}%)`;
    }

    function destroyBIChart(chartKey) {
      if (biChartInstances[chartKey]) {
        try {
          biChartInstances[chartKey].destroy();
        } catch (e) {
          console.warn('Erro ao destruir gráfico:', e);
        }
        delete biChartInstances[chartKey];
      }
    }

    function parseMonetaryVal(valStr) {
      if (!valStr) return 0.0;
      const clean = String(valStr).replace(/[^\d.,]/g, '').trim();
      if (!clean) return 0.0;
      let num = 0.0;
      if (clean.includes(',') && clean.includes('.')) {
        num = parseFloat(clean.replace(/\./g, '').replace(',', '.'));
      } else if (clean.includes(',')) {
        num = parseFloat(clean.replace(',', '.'));
      } else {
        num = parseFloat(clean);
      }
      return (!isNaN(num) && num > 0) ? num : 0.0;
    }

    function formatCurrencyBRL(num) {
      return (num || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    }

    function isCpfValid(cpfRaw) {
      if (!cpfRaw) return false;
      const digits = String(cpfRaw).replace(/\D/g, '');
      if (digits.length !== 11) return false;
      if (/^(\d)\1{10}$/.test(digits)) return false;
      let sum = 0, rest;
      for (let i = 1; i <= 9; i++) sum += parseInt(digits.substring(i - 1, i)) * (11 - i);
      rest = (sum * 10) % 11;
      if (rest === 10 || rest === 11) rest = 0;
      if (rest !== parseInt(digits.substring(9, 10))) return false;
      sum = 0;
      for (let i = 1; i <= 10; i++) sum += parseInt(digits.substring(i - 1, i)) * (12 - i);
      rest = (sum * 10) % 11;
      if (rest === 10 || rest === 11) rest = 0;
      if (rest !== parseInt(digits.substring(10, 11))) return false;
      return true;
    }

    function isCnpjValid(cnpjRaw) {
      if (!cnpjRaw) return false;
      const digits = String(cnpjRaw).replace(/\D/g, '');
      if (digits.length !== 14) return false;
      if (/^(\d)\1{13}$/.test(digits)) return false;
      let size = digits.length - 2;
      let numbers = digits.substring(0, size);
      let sum = 0;
      let pos = size - 7;
      for (let i = size; i >= 1; i--) {
        sum += parseInt(numbers.charAt(size - i)) * pos--;
        if (pos < 2) pos = 9;
      }
      let result = sum % 11 < 2 ? 0 : 11 - (sum % 11);
      if (result !== parseInt(digits.charAt(size))) return false;
      size = size + 1;
      numbers = digits.substring(0, size);
      sum = 0;
      pos = size - 7;
      for (let i = size; i >= 1; i--) {
        sum += parseInt(numbers.charAt(size - i)) * pos--;
        if (pos < 2) pos = 9;
      }
      result = sum % 11 < 2 ? 0 : 11 - (sum % 11);
      if (result !== parseInt(digits.charAt(size))) return false;
      return true;
    }

    function extractHours(ch) {
      if (!ch) return null;
      const str = String(ch).toLowerCase();
      const m = str.match(/(\d[\d\.\,]*)\s*(h|hora|hr)/i) || str.match(/\b(\d+)\b/);
      if (m) {
        const clean = m[1].replace(/\./g, '').replace(',', '.');
        const n = parseFloat(clean);
        if (!isNaN(n) && n > 0 && n < 20000) return n;
      }
      return null;
    }

    function extractYear(dt) {
      if (!dt) return null;
      const str = String(dt);
      const m = str.match(/\b(19\d\d|20\d\d)\b/);
      if (m) {
        const y = parseInt(m[1]);
        if (y >= 1970 && y <= 2035) return y;
      }
      return null;
    }

    function escapeHtmlAttr(str) {
      return String(str || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function filterFromBI(filterType, filterVal) {
      if (filterType === 'dominio') {
        setBIDomain(filterVal.toLowerCase());
        return;
      }
      switchMainTab('galeria');
      if (filterType === 'natureza') {
        activeNaturezaFilter = filterVal;
        const sel = document.getElementById('selectNaturezaFilter');
        if (sel) sel.value = filterVal;
        applyFilter(false);
      } else if (filterType === 'tipo' || filterType === 'classe') {
        const inp = document.getElementById('searchInput');
        if (inp) {
          inp.value = filterVal;
          onSearchInput();
        }
      } else if (filterType === 'faculdade' || filterType === 'busca' || filterType === 'titular') {
        const inp = document.getElementById('searchInput');
        if (inp) {
          inp.value = filterVal;
          onSearchInput();
        }
      } else if (filterType === 'ano') {
        const inp = document.getElementById('searchInput');
        if (inp) {
          inp.value = filterVal;
          onSearchInput();
        }
      }
      showToast(`Filtro ativado no acervo: "${filterVal}"`, 'info');
    }

    async function fetchBIExtendedStats() {
      try {
        const bStr = biState.brackets.join(',');
        const resp = await fetch(`/api/estatisticas_gerenciais?brackets=${encodeURIComponent(bStr)}`);
        if (resp.ok) {
          biState.backendStats = await resp.json();
          if (biState.backendStats) {
            const elDup = document.getElementById('kpiDuplicatasSuspeitas');
            if (elDup && typeof biState.backendStats.duplicatas_count === 'number') {
              elDup.innerText = biState.backendStats.duplicatas_count.toLocaleString('pt-BR');
            }
            const elAss = document.getElementById('kpiAssinaturasDigitais');
            if (elAss && typeof biState.backendStats.assinaturas_count === 'number') {
              elAss.innerText = biState.backendStats.assinaturas_count.toLocaleString('pt-BR');
              const elAssPct = document.getElementById('kpiAssinaturasPct');
              if (elAssPct && biState.backendStats.total_docs > 0) {
                const p = ((biState.backendStats.assinaturas_count / biState.backendStats.total_docs) * 100).toFixed(1);
                elAssPct.innerText = `${p}%`;
              }
            }
            const elNat = document.getElementById('kpiNativosDigitais');
            if (elNat && typeof biState.backendStats.nativos_digitais_count === 'number') {
              elNat.innerText = `${biState.backendStats.nativos_digitais_count} nativos`;
            }
          }
        }
      } catch (e) {
        console.warn('Estatísticas estendidas do backend indisponíveis:', e);
      }
    }

    function refreshBIDashboard(showNotification = false) {
      fetchBIExtendedStats();
      renderBIDashboard();
      if (showNotification) {
        showToast('Painel de BI & Universal Analytics recalculado com sucesso!', 'success');
      }
    }

    // Configurações de tema para Chart.js
    function isLightThemeActive() {
      return document.documentElement.classList.contains('theme-light');
    }

    function getBiChartBorderColor() {
      return isLightThemeActive() ? '#ffffff' : '#0f172a';
    }

    function getBiGridColor() {
      return isLightThemeActive() ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.06)';
    }

    function getBiTickColor() {
      return isLightThemeActive() ? '#475569' : '#94a3b8';
    }

    function getBiLabelColor() {
      return isLightThemeActive() ? '#1e293b' : '#cbd5e1';
    }

    const biChartDarkOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: {
            color: '#cbd5e1',
            font: { size: 11, family: 'system-ui, -apple-system, sans-serif' },
            boxWidth: 12,
            padding: 10
          }
        },
        tooltip: {
          backgroundColor: 'rgba(15, 23, 42, 0.95)',
          borderColor: 'rgba(51, 65, 85, 0.8)',
          borderWidth: 1,
          titleColor: '#f8fafc',
          bodyColor: '#cbd5e1',
          padding: 10,
          cornerRadius: 8,
          boxPadding: 4
        }
      }
    };

    function updateChartThemeConfig() {
      const isLight = isLightThemeActive();
      biChartDarkOptions.plugins.legend.labels.color = isLight ? '#334155' : '#cbd5e1';
      biChartDarkOptions.plugins.tooltip.backgroundColor = isLight ? 'rgba(255, 255, 255, 0.98)' : 'rgba(15, 23, 42, 0.95)';
      biChartDarkOptions.plugins.tooltip.borderColor = isLight ? 'rgba(203, 213, 225, 0.9)' : 'rgba(51, 65, 85, 0.8)';
      biChartDarkOptions.plugins.tooltip.titleColor = isLight ? '#0f172a' : '#f8fafc';
      biChartDarkOptions.plugins.tooltip.bodyColor = isLight ? '#334155' : '#cbd5e1';
    }

    // =========================================================================
    // RENDERIZADOR PRINCIPAL DO BI
    // =========================================================================
    function renderBIDashboard() {
      initBIPreferences();
      updateChartThemeConfig();

      const allDocs = documents || [];
      const totalAcervo = allDocs.length;
      const unprocDocs = allDocs.filter(d => isDocumentUnprocessed(d));
      const classifDocs = allDocs.filter(d => !isDocumentUnprocessed(d));
      const aprovDocs = classifDocs.filter(d => safeString(d.status_conferencia).toLowerCase() === 'aprovado');

      // 1. Atualiza Indicadores Chave (Hero KPIs)
      const elKpiTotal = document.getElementById('kpiTotalDocs');
      if (elKpiTotal) elKpiTotal.innerText = totalAcervo.toLocaleString('pt-BR');

      const elKpiClass = document.getElementById('kpiClassificadosSub');
      const elKpiClassPct = document.getElementById('kpiClassificadosPct');
      if (elKpiClass) elKpiClass.innerText = `${classifDocs.length.toLocaleString('pt-BR')} classificados`;
      if (elKpiClassPct) {
        const pct = totalAcervo > 0 ? ((classifDocs.length / totalAcervo) * 100).toFixed(1) : '0.0';
        elKpiClassPct.innerText = `${pct}% IA`;
      }

      // Cálculo de Patrimônio Mapeado e Transações
      let sumReais = 0.0;
      let countWithVal = 0;
      let maxReais = 0.0;
      allDocs.forEach(d => {
        const val = parseMonetaryVal(d.valor_monetario);
        if (val > 0) {
          sumReais += val;
          countWithVal++;
          if (val > maxReais) maxReais = val;
        }
      });

      const elKpiVal = document.getElementById('kpiTotalValor');
      if (elKpiVal) {
        elKpiVal.innerText = formatCurrencyBRL(sumReais);
        elKpiVal.title = `Volume total: ${formatCurrencyBRL(sumReais)} em ${countWithVal} documentos`;
      }

      const elKpiTicket = document.getElementById('kpiTicketMedio');
      if (elKpiTicket) {
        const ticket = countWithVal > 0 ? (sumReais / countWithVal) : 0;
        elKpiTicket.innerText = `Méd: ${formatCurrencyBRL(ticket)}`;
      }

      const elKpiMaxBadge = document.getElementById('kpiMaiorTransacaoBadge');
      if (elKpiMaxBadge) {
        elKpiMaxBadge.innerText = `Max: ${formatCurrencyBRL(maxReais)}`;
        elKpiMaxBadge.title = `Maior Transação: ${formatCurrencyBRL(maxReais)}`;
      }

      // Entidades & Titulares
      const cpfs = new Set();
      const cnpjs = new Set();
      const beneficiarios = new Set();
      allDocs.forEach(d => {
        if (isCpfValid(d.cpf)) cpfs.add(String(d.cpf).replace(/\D/g, ''));
        if (isCnpjValid(d.cnpj)) cnpjs.add(String(d.cnpj).replace(/\D/g, ''));
        const ben = safeString(d.beneficiario).trim();
        if (ben && ben.length >= 3 && !ben.toLowerCase().includes('não informado')) {
          beneficiarios.add(ben.toLowerCase());
        }
      });

      const elKpiEntidades = document.getElementById('kpiTotalEntidades');
      if (elKpiEntidades) {
        const totalEnt = beneficiarios.size || (cpfs.size + cnpjs.size);
        elKpiEntidades.innerText = totalEnt.toLocaleString('pt-BR');
      }

      const elKpiCpf = document.getElementById('kpiCpfCount');
      if (elKpiCpf) elKpiCpf.innerText = `${cpfs.size} CPFs`;
      const elKpiCnpj = document.getElementById('kpiCnpjCount');
      if (elKpiCnpj) elKpiCnpj.innerText = `${cnpjs.size} CNPJs`;

      // Conferência Humana
      const elKpiApr = document.getElementById('kpiAprovados');
      const elKpiAprPct = document.getElementById('kpiAprovadosPct');
      const elKpiPend = document.getElementById('kpiPendentesConf');
      if (elKpiApr) elKpiApr.innerText = aprovDocs.length.toLocaleString('pt-BR');
      if (elKpiAprPct) {
        const pct = classifDocs.length > 0 ? ((aprovDocs.length / classifDocs.length) * 100).toFixed(1) : '0.0';
        elKpiAprPct.innerText = `${pct}%`;
      }
      if (elKpiPend) {
        const pendentes = classifDocs.length - aprovDocs.length;
        elKpiPend.innerText = `${pendentes.toLocaleString('pt-BR')} pendentes`;
      }

      // Assinaturas e Integridade Inicial
      const assinadosLocal = allDocs.filter(d => Boolean(d.assinatura_digital || d.assinaturas_digitais || d.icp_brasil || (Array.isArray(d.assinaturas) && d.assinaturas.length > 0))).length;
      const elAssin = document.getElementById('kpiAssinaturasDigitais');
      const elAssinPct = document.getElementById('kpiAssinaturasPct');
      if (elAssin) elAssin.innerText = assinadosLocal.toLocaleString('pt-BR');
      if (elAssinPct) {
        const pct = totalAcervo > 0 ? ((assinadosLocal / totalAcervo) * 100).toFixed(1) : '0.0';
        elAssinPct.innerText = `${pct}%`;
      }

      // Duplicatas e Nativos
      const nativosLocal = allDocs.filter(d => !d.is_scanned && !d.ocr_required).length;
      const elNat = document.getElementById('kpiNativosDigitais');
      if (elNat) elNat.innerText = `${nativosLocal} nativos`;

      // 2. Banner de Preponderância / Aviso
      renderBIAvisoBanner(allDocs);

      // 3. Determina o subconjunto de documentos conforme Escopo e Domínio
      let targetDocs = classifDocs;
      if (biState.scope === 'todos') targetDocs = allDocs;
      else if (biState.scope === 'aprovados') targetDocs = aprovDocs;

      // Filtro de domínio (quando diferente de 'geral')
      if (biState.domain && biState.domain !== 'geral') {
        targetDocs = targetDocs.filter(d => {
          const dDom = safeString(d.dominio || 'outro').toLowerCase();
          return dDom === biState.domain;
        });
      }
      const targetTotal = targetDocs.length;

      // 4. Renderiza os 6 Gráficos e a Tabela Matriz
      renderChart1(targetDocs, targetTotal);
      renderChart2(targetDocs, targetTotal);
      renderChart3Timeline(targetDocs, targetTotal);
      renderChart4Titulares(targetDocs, targetTotal);
      renderChart5RadarQualidade(targetDocs, targetTotal);
      renderChart6Pipeline(targetDocs, targetTotal);
      renderDynamicPivotTable(targetDocs, targetTotal);

      // Inicia busca assíncrona das estatísticas completas de backend (se ainda não carregadas)
      if (!biState.backendStats) {
        fetchBIExtendedStats();
      }
    }

    // Banner de Aviso / Preponderância
    function renderBIAvisoBanner(allDocs) {
      const banner = document.getElementById('biDomainNoticeBanner');
      if (!banner) return;
      const icon = document.getElementById('biNoticeBannerIcon');
      const text = document.getElementById('biNoticeBannerText');
      const actions = document.getElementById('biNoticeBannerActions');
      if (!text || !actions) return;

      const domCounts = {};
      allDocs.forEach(d => {
        const dom = safeString(d.dominio || 'outro').toLowerCase();
        domCounts[dom] = (domCounts[dom] || 0) + 1;
      });

      const total = allDocs.length;
      let dominant = null;
      let dominantPct = 0;
      let dominantCount = 0;

      for (const [k, v] of Object.entries(domCounts)) {
        const pct = total > 0 ? (v / total) * 100 : 0;
        if (pct > 50) {
          dominant = k;
          dominantPct = pct.toFixed(1);
          dominantCount = v;
          break;
        }
      }

      const domainNames = {
        'financeiro': 'Financeiro',
        'juridico': 'Jurídico',
        'identificacao': 'Identificação',
        'cadastral': 'Cadastral',
        'academico': 'Acadêmico',
        'outro': 'Outros Documentos'
      };

      if (biState.domain !== 'geral') {
        banner.className = 'rounded-xl p-3 sm:p-4 border transition flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shadow-sm bg-cyan-950/40 border-cyan-500/30 text-cyan-200';
        if (icon) icon.className = 'fa-solid fa-filter text-cyan-400 text-base';
        const domTitle = domainNames[biState.domain] || biState.domain;
        text.innerHTML = `Filtro ativo por domínio: <strong>${domTitle}</strong> (${domCounts[biState.domain] || 0} documentos encontrados no acervo).`;
        actions.innerHTML = `
          <button type="button" onclick="setBIDomain('geral')" class="px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg font-semibold transition text-xs shadow-sm flex items-center gap-1.5">
            <i class="fa-solid fa-globe"></i>
            <span>Voltar à Visão Geral</span>
          </button>
        `;
        banner.classList.remove('hidden');
      } else if (dominant) {
        banner.className = 'rounded-xl p-3 sm:p-4 border transition flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shadow-sm bg-amber-950/30 border-amber-500/30 text-amber-200';
        if (icon) icon.className = 'fa-solid fa-bolt text-amber-400 text-base';
        const domTitle = domainNames[dominant] || dominant;
        text.innerHTML = `⚡ <strong>Domínio Preponderante Detectado: ${domTitle}</strong> (${dominantPct}% do acervo — ${dominantCount.toLocaleString('pt-BR')} documentos).`;
        actions.innerHTML = `
          <button type="button" onclick="setBIDomain('${dominant}')" class="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded-lg font-semibold transition text-xs shadow-sm flex items-center gap-1.5">
            <i class="fa-solid fa-magnifying-glass-chart"></i>
            <span>Focar em ${domTitle}</span>
          </button>
          <button type="button" onclick="openBIConfigModal()" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition text-xs border border-slate-700">
            <i class="fa-solid fa-gear"></i>
            <span>Configurar Abertura</span>
          </button>
        `;
        banner.classList.remove('hidden');
      } else {
        banner.classList.add('hidden');
      }
    }

    // =========================================================================
    // CARD GRÁFICO 1: DISTRIBUIÇÃO PRIMÁRIA (DOMÍNIOS OU SUB-CATEGORIAS)
    // =========================================================================
    function renderChart1(docs, total) {
      destroyBIChart('chart1');
      const canvas = document.getElementById('chart1Canvas');
      const tbody = document.getElementById('chart1TableBody');
      const titleEl = document.getElementById('chart1Title');
      const labelTotalEl = document.getElementById('labelChart1Total');
      const thCategory = document.getElementById('chart1ThCategory');

      if (labelTotalEl) labelTotalEl.innerText = `${total.toLocaleString('pt-BR')} documentos`;

      let categories = [];
      let counts = {};

      if (biState.domain === 'geral') {
        if (titleEl) titleEl.innerText = 'Distribuição por Domínio do Acervo';
        if (thCategory) thCategory.innerText = 'Domínio Documental';

        categories = [
          { key: 'financeiro', label: 'Financeiro', color: '#10b981', icon: 'fa-sack-dollar' },
          { key: 'juridico', label: 'Jurídico', color: '#6366f1', icon: 'fa-scale-balanced' },
          { key: 'identificacao', label: 'Identificação', color: '#f59e0b', icon: 'fa-id-card' },
          { key: 'cadastral', label: 'Cadastral', color: '#0284c7', icon: 'fa-building' },
          { key: 'academico', label: 'Acadêmico', color: '#ec4899', icon: 'fa-graduation-cap' },
          { key: 'veicular', label: 'Veicular', color: '#f97316', icon: 'fa-car' },
          { key: 'outro', label: 'Outros', color: '#64748b', icon: 'fa-folder' }
        ];

        categories.forEach(c => counts[c.key] = 0);
        docs.forEach(d => {
          let dom = safeString(d.dominio || 'outro').toLowerCase();
          if (dom === 'profissional') dom = 'cadastral';
          if (!counts.hasOwnProperty(dom)) dom = 'outro';
          counts[dom] = (counts[dom] || 0) + 1;
        });

      } else if (biState.domain === 'academico') {
        if (titleEl) titleEl.innerText = 'Cursos & Níveis Acadêmicos';
        if (thCategory) thCategory.innerText = 'Nível Acadêmico';

        categories = [
          { key: 'Pós-Graduação Lato Sensu (Especialização/MBA)', label: 'Pós Lato Sensu (MBA/Espec.)', color: '#0ea5e9' },
          { key: 'Curso Técnico / Profissionalizante', label: 'Técnico / Profissionalizante', color: '#f59e0b' },
          { key: 'Graduação / Curso Superior', label: 'Graduação / Superior', color: '#a855f7' },
          { key: 'Curso de Extensão / Aperfeiçoamento', label: 'Extensão / Aperfeiçoamento', color: '#6366f1' },
          { key: 'Educação Básica', label: 'Educação Básica', color: '#ec4899' },
          { key: 'Pós-Graduação Stricto Sensu (Mestrado/Doutorado)', label: 'Pós Stricto (Mestrado/Dout.)', color: '#10b981' },
          { key: 'Não identificada', label: 'Não identificada', color: '#64748b' }
        ];

        categories.forEach(c => counts[c.key] = 0);
        docs.forEach(d => {
          const nat = classifyNatureza(d.natureza_curso);
          counts[nat] = (counts[nat] || 0) + 1;
        });

      } else {
        if (titleEl) titleEl.innerText = `Tipologia no Domínio ${biState.domain.charAt(0).toUpperCase() + biState.domain.slice(1)}`;
        if (thCategory) thCategory.innerText = 'Tipo / Subclasse';

        const mapTypes = {};
        docs.forEach(d => {
          const t = safeString(d.tipo_documento).trim() || 'Não especificado';
          mapTypes[t] = (mapTypes[t] || 0) + 1;
        });

        const sorted = Object.entries(mapTypes).sort((a, b) => b[1] - a[1]);
        const palette = ['#10b981', '#06b6d4', '#6366f1', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6', '#64748b'];

        categories = sorted.slice(0, 7).map(([k, v], idx) => ({
          key: k,
          label: k.length > 25 ? k.substring(0, 23) + '...' : k,
          fullLabel: k,
          color: palette[idx % palette.length]
        }));

        if (sorted.length > 7) {
          const restCount = sorted.slice(7).reduce((acc, curr) => acc + curr[1], 0);
          categories.push({
            key: 'Outros Subtipos',
            label: 'Outros Subtipos',
            fullLabel: 'Outros Subtipos',
            color: '#475569'
          });
          mapTypes['Outros Subtipos'] = restCount;
        }

        categories.forEach(c => counts[c.key] = mapTypes[c.key] || 0);
      }

      const dataPoints = categories.map(c => counts[c.key] || 0);
      const totalFiltered = dataPoints.reduce((a, b) => a + b, 0);

      // Atualiza a tabela lateral
      if (tbody) {
        tbody.innerHTML = categories.map(c => {
          const count = counts[c.key] || 0;
          const pct = totalFiltered > 0 ? ((count / totalFiltered) * 100).toFixed(1) : '0.0';
          const clickAction = biState.domain === 'geral'
            ? `setBIDomain('${escapeHtmlAttr(c.key)}')`
            : `filterFromBI('classe', '${escapeHtmlAttr(c.fullLabel || c.key)}')`;
          const actionText = biState.domain === 'geral' ? 'Focar ➔' : 'Filtrar ➔';

          return `
            <tr class="hover:bg-slate-800/40 transition">
              <td class="py-1.5 pr-2 text-slate-200 flex items-center gap-1.5 truncate max-w-[150px]" title="${escapeHtmlAttr(c.fullLabel || c.key)}">
                <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background-color: ${c.color}"></span>
                <span class="truncate">${c.label}</span>
              </td>
              <td class="py-1.5 px-2 text-right text-slate-300 font-semibold">${count.toLocaleString('pt-BR')}</td>
              <td class="py-1.5 px-2 text-right text-cyan-300">${pct}%</td>
              <td class="py-1.5 pl-2 text-right no-print">
                <button type="button" onclick="${clickAction}"
                        class="text-[10px] text-cyan-400 hover:text-cyan-300 hover:underline inline-flex items-center gap-0.5">
                  ${actionText}
                </button>
              </td>
            </tr>
          `;
        }).join('');
      }

      // Renderiza Doughnut Chart
      if (canvas && typeof Chart !== 'undefined') {
        biChartInstances['chart1'] = new Chart(canvas, {
          type: 'doughnut',
          data: {
            labels: categories.map(c => c.label),
            datasets: [{
              data: dataPoints,
              backgroundColor: categories.map(c => c.color),
              borderColor: getBiChartBorderColor(),
              borderWidth: 2,
              hoverOffset: 6
            }]
          },
          options: {
            ...biChartDarkOptions,
            cutout: '62%',
            onClick: (evt, elements) => {
              if (elements && elements.length > 0) {
                const idx = elements[0].index;
                const cat = categories[idx];
                if (cat) {
                  if (biState.domain === 'geral') setBIDomain(cat.key);
                  else filterFromBI('classe', cat.fullLabel || cat.key);
                }
              }
            },
            plugins: {
              ...biChartDarkOptions.plugins,
              legend: { display: false },
              tooltip: {
                ...biChartDarkOptions.plugins.tooltip,
                callbacks: {
                  label: function(ctx) {
                    const val = ctx.raw || 0;
                    const pct = totalFiltered > 0 ? ((val / totalFiltered) * 100).toFixed(1) : 0;
                    return ` ${ctx.label}: ${val.toLocaleString('pt-BR')} docs (${pct}%) - Clique p/ abrir`;
                  }
                }
              }
            }
          }
        });
      }
    }

    // =========================================================================
    // CARD GRÁFICO 2: CLASSES / FAIXAS DE VALOR (CONFIGURÁVEIS)
    // =========================================================================
    function renderChart2(docs, total) {
      destroyBIChart('chart2');
      const canvas = document.getElementById('chart2Canvas');
      const tbody = document.getElementById('chart2TableBody');
      const titleEl = document.getElementById('chart2Title');
      const labelTotalEl = document.getElementById('labelChart2Total');
      const thCategory = document.getElementById('chart2ThCategory');

      if (labelTotalEl) labelTotalEl.innerText = `${total.toLocaleString('pt-BR')} analisados`;

      if (biState.domain === 'financeiro') {
        if (titleEl) titleEl.innerText = 'Distribuição por Faixa de Valor Financeiro';
        if (thCategory) thCategory.innerText = 'Faixa de Valor (R$)';

        const [b1, b2, b3] = biState.brackets;
        const b1Fmt = b1 >= 1000 ? `${b1/1000}k` : `${b1}`;
        const b2Fmt = b2 >= 1000 ? `${b2/1000}k` : `${b2}`;
        const b3Fmt = b3 >= 1000 ? `${b3/1000}k` : `${b3}`;

        const bracketsDefs = [
          { label: `Até R$ ${b1Fmt}`, min: 0.01, max: b1, color: '#34d399' },
          { label: `R$ ${b1Fmt} a ${b2Fmt}`, min: b1, max: b2, color: '#06b6d4' },
          { label: `R$ ${b2Fmt} a ${b3Fmt}`, min: b2, max: b3, color: '#818cf8' },
          { label: `Acima de R$ ${b3Fmt}`, min: b3, max: Infinity, color: '#f43f5e' },
          { label: 'Sem Valor Declarado', min: -1, max: 0, color: '#64748b' }
        ];

        const bracketCounts = bracketsDefs.map(() => 0);
        const bracketSums = bracketsDefs.map(() => 0.0);

        docs.forEach(d => {
          const val = parseMonetaryVal(d.valor_monetario);
          if (val <= 0) {
            bracketCounts[4]++;
          } else if (val <= b1) {
            bracketCounts[0]++;
            bracketSums[0] += val;
          } else if (val <= b2) {
            bracketCounts[1]++;
            bracketSums[1] += val;
          } else if (val <= b3) {
            bracketCounts[2]++;
            bracketSums[2] += val;
          } else {
            bracketCounts[3]++;
            bracketSums[3] += val;
          }
        });

        // Tabela
        if (tbody) {
          tbody.innerHTML = bracketsDefs.map((b, idx) => {
            const count = bracketCounts[idx];
            const sumVal = bracketSums[idx];
            const pct = total > 0 ? ((count / total) * 100).toFixed(1) : '0.0';
            const sumFmt = sumVal > 0 ? formatCurrencyBRL(sumVal) : '-';

            return `
              <tr class="hover:bg-slate-800/40 transition">
                <td class="py-1.5 pr-2 text-slate-200 flex items-center gap-1.5 truncate">
                  <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background-color: ${b.color}"></span>
                  <span class="truncate">${b.label}</span>
                </td>
                <td class="py-1.5 px-2 text-right text-slate-300 font-semibold">${count.toLocaleString('pt-BR')}</td>
                <td class="py-1.5 px-2 text-right text-emerald-300 font-mono text-[10px]">${sumFmt}</td>
                <td class="py-1.5 pl-2 text-right no-print">
                  <button type="button" onclick="openBIConfigModal()" class="text-[10px] text-cyan-400 hover:underline">
                    Editar Faixas
                  </button>
                </td>
              </tr>
            `;
          }).join('');
        }

        if (canvas && typeof Chart !== 'undefined') {
          biChartInstances['chart2'] = new Chart(canvas, {
            type: 'bar',
            data: {
              labels: bracketsDefs.map(b => b.label),
              datasets: [{
                label: 'Documentos',
                data: bracketCounts,
                backgroundColor: bracketsDefs.map(b => b.color + 'cc'),
                hoverBackgroundColor: bracketsDefs.map(b => b.color),
                borderColor: bracketsDefs.map(b => b.color),
                borderWidth: 1,
                borderRadius: 4
              }]
            },
            options: {
              ...biChartDarkOptions,
              scales: {
                x: {
                  grid: { display: false },
                  ticks: { color: getBiLabelColor(), font: { size: 9.5 } }
                },
                y: {
                  grid: { color: getBiGridColor(), drawBorder: false },
                  ticks: { color: getBiTickColor(), font: { size: 10 } }
                }
              },
              plugins: {
                ...biChartDarkOptions.plugins,
                legend: { display: false },
                tooltip: {
                  ...biChartDarkOptions.plugins.tooltip,
                  callbacks: {
                    label: function(ctx) {
                      const idx = ctx.dataIndex;
                      const c = bracketCounts[idx];
                      const s = bracketSums[idx];
                      const pct = total > 0 ? ((c / total) * 100).toFixed(1) : 0;
                      return ` ${c.toLocaleString('pt-BR')} docs (${pct}%) • Total: ${formatCurrencyBRL(s)}`;
                    }
                  }
                }
              }
            }
          });
        }

      } else if (biState.domain === 'academico') {
        if (titleEl) titleEl.innerText = 'Distribuição por Carga Horária';
        if (thCategory) thCategory.innerText = 'Faixa de Horas';

        const buckets = {
          '< 40h (Curta Duração)': 0,
          '40h a 179h (Extensão)': 0,
          '180h a 359h (Capacitação)': 0,
          '360h a 999h (Especialização/MBA)': 0,
          '≥ 1000h (Graduação/Técnico)': 0,
          'Não informada': 0
        };

        docs.forEach(doc => {
          const h = extractHours(doc.carga_horaria);
          if (h === null) buckets['Não informada']++;
          else if (h < 40) buckets['< 40h (Curta Duração)']++;
          else if (h < 180) buckets['40h a 179h (Extensão)']++;
          else if (h < 360) buckets['180h a 359h (Capacitação)']++;
          else if (h < 1000) buckets['360h a 999h (Especialização/MBA)']++;
          else buckets['≥ 1000h (Graduação/Técnico)']++;
        });

        const keys = Object.keys(buckets);
        const values = keys.map(k => buckets[k]);
        const colors = ['#38bdf8', '#818cf8', '#a78bfa', '#c084fc', '#f472b6', '#64748b'];

        if (tbody) {
          tbody.innerHTML = keys.map((k, idx) => {
            const count = values[idx];
            const pct = total > 0 ? ((count / total) * 100).toFixed(1) : '0.0';
            return `
              <tr class="hover:bg-slate-800/40 transition">
                <td class="py-1.5 pr-2 text-slate-200 flex items-center gap-1.5 truncate">
                  <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background-color: ${colors[idx]}"></span>
                  <span class="truncate">${k}</span>
                </td>
                <td class="py-1.5 px-2 text-right text-slate-300 font-semibold">${count.toLocaleString('pt-BR')}</td>
                <td class="py-1.5 px-2 text-right text-sky-300">${pct}%</td>
                <td class="py-1.5 pl-2 text-right no-print">
                  <button type="button" onclick="filterFromBI('busca', '${k.split(' ')[0]}')" class="text-[10px] text-sky-400 hover:underline">
                    Filtrar ➔
                  </button>
                </td>
              </tr>
            `;
          }).join('');
        }

        if (canvas && typeof Chart !== 'undefined') {
          biChartInstances['chart2'] = new Chart(canvas, {
            type: 'bar',
            data: {
              labels: keys,
              datasets: [{
                label: 'Documentos',
                data: values,
                backgroundColor: colors.map(c => c + 'cc'),
                hoverBackgroundColor: colors,
                borderColor: colors,
                borderWidth: 1,
                borderRadius: 4
              }]
            },
            options: {
              ...biChartDarkOptions,
              scales: {
                x: {
                  grid: { display: false },
                  ticks: { color: getBiLabelColor(), font: { size: 9 } }
                },
                y: {
                  grid: { color: getBiGridColor(), drawBorder: false },
                  ticks: { color: getBiTickColor(), font: { size: 10 } }
                }
              },
              plugins: {
                ...biChartDarkOptions.plugins,
                legend: { display: false }
              }
            }
          });
        }

      } else {
        if (titleEl) titleEl.innerText = 'Classes Documentais Mais Frequentes';
        if (thCategory) thCategory.innerText = 'Classe Documental';

        const mapClasses = {};
        const mapValores = {};

        docs.forEach(d => {
          const c = safeString(d.tipo_documento).trim() || 'Não identificado';
          mapClasses[c] = (mapClasses[c] || 0) + 1;
          const val = parseMonetaryVal(d.valor_monetario);
          mapValores[c] = (mapValores[c] || 0.0) + val;
        });

        const sorted = Object.entries(mapClasses).sort((a, b) => b[1] - a[1]).slice(0, 8);
        const labels = sorted.map(s => s[0]);
        const countsArr = sorted.map(s => s[1]);
        const shortLabels = labels.map(l => l.length > 24 ? l.substring(0, 22) + '...' : l);

        if (tbody) {
          tbody.innerHTML = sorted.map(([cName, cnt]) => {
            const pct = total > 0 ? ((cnt / total) * 100).toFixed(1) : '0.0';
            const valSum = mapValores[cName] || 0;
            const valFmt = valSum > 0 ? formatCurrencyBRL(valSum) : '-';
            return `
              <tr class="hover:bg-slate-800/40 transition">
                <td class="py-1.5 pr-2 text-slate-200 truncate max-w-[140px]" title="${escapeHtmlAttr(cName)}">
                  ${cName}
                </td>
                <td class="py-1.5 px-2 text-right text-slate-300 font-semibold">${cnt.toLocaleString('pt-BR')}</td>
                <td class="py-1.5 px-2 text-right text-teal-300 text-[10px] font-mono">${valFmt}</td>
                <td class="py-1.5 pl-2 text-right no-print">
                  <button type="button" onclick="filterFromBI('classe', '${escapeHtmlAttr(cName)}')" class="text-[10px] text-teal-400 hover:underline">
                    Filtrar ➔
                  </button>
                </td>
              </tr>
            `;
          }).join('');
        }

        if (canvas && typeof Chart !== 'undefined') {
          biChartInstances['chart2'] = new Chart(canvas, {
            type: 'bar',
            data: {
              labels: shortLabels,
              datasets: [{
                label: 'Documentos',
                data: countsArr,
                backgroundColor: 'rgba(20, 184, 166, 0.8)',
                hoverBackgroundColor: 'rgba(20, 184, 166, 1)',
                borderColor: '#0d9488',
                borderWidth: 1,
                borderRadius: 4
              }]
            },
            options: {
              ...biChartDarkOptions,
              indexAxis: 'y',
              onClick: (evt, elements) => {
                if (elements && elements.length > 0) {
                  const idx = elements[0].index;
                  const cName = labels[idx];
                  if (cName) filterFromBI('classe', cName);
                }
              },
              scales: {
                x: {
                  grid: { color: getBiGridColor(), drawBorder: false },
                  ticks: { color: getBiTickColor(), font: { size: 10 } }
                },
                y: {
                  grid: { display: false },
                  ticks: { color: getBiLabelColor(), font: { size: 10 } }
                }
              },
              plugins: {
                ...biChartDarkOptions.plugins,
                legend: { display: false },
                tooltip: {
                  ...biChartDarkOptions.plugins.tooltip,
                  callbacks: {
                    title: items => labels[items[0].dataIndex] || '',
                    label: ctx => {
                      const idx = ctx.dataIndex;
                      const cName = labels[idx];
                      const valSum = mapValores[cName] || 0;
                      const sFmt = valSum > 0 ? ` • Montante: ${formatCurrencyBRL(valSum)}` : '';
                      return ` ${ctx.raw} docs${sFmt} - Clique p/ filtrar`;
                    }
                  }
                }
              }
            }
          });
        }
      }
    }

    // =========================================================================
    // CARD GRÁFICO 3: LINHA DO TEMPO DUAL (VOLUME E R$ POR ANO)
    // =========================================================================
    function renderChart3Timeline(docs, total) {
      destroyBIChart('chart3');
      const canvas = document.getElementById('chart3Canvas');
      if (!canvas || typeof Chart === 'undefined') return;

      const yearCounts = {};
      const yearValues = {};

      docs.forEach(d => {
        const y = extractYear(d.data);
        if (y) {
          yearCounts[y] = (yearCounts[y] || 0) + 1;
          const val = parseMonetaryVal(d.valor_monetario);
          yearValues[y] = (yearValues[y] || 0.0) + val;
        }
      });

      const sortedYears = Object.keys(yearCounts).map(Number).sort((a, b) => a - b);
      const labels = sortedYears.length > 0 ? sortedYears.map(String) : ['Sem dados temporais'];
      const countsData = sortedYears.length > 0 ? sortedYears.map(y => yearCounts[y]) : [0];
      const valuesData = sortedYears.length > 0 ? sortedYears.map(y => yearValues[y]) : [0];

      biChartInstances['chart3'] = new Chart(canvas, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              type: 'bar',
              label: 'Volume de Documentos',
              data: countsData,
              backgroundColor: 'rgba(16, 185, 129, 0.75)',
              hoverBackgroundColor: 'rgba(16, 185, 129, 0.95)',
              borderColor: '#10b981',
              borderWidth: 1,
              borderRadius: 4,
              yAxisID: 'y'
            },
            {
              type: 'line',
              label: 'Montante em R$',
              data: valuesData,
              borderColor: '#f59e0b',
              backgroundColor: 'rgba(245, 158, 11, 0.15)',
              borderWidth: 2.5,
              fill: false,
              tension: 0.3,
              pointBackgroundColor: '#f59e0b',
              pointRadius: 4,
              pointHoverRadius: 6,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          ...biChartDarkOptions,
          onClick: (evt, elements) => {
            if (elements && elements.length > 0) {
              const idx = elements[0].index;
              const yr = labels[idx];
              if (yr && yr !== 'Sem dados temporais') filterFromBI('ano', yr);
            }
          },
          scales: {
            x: {
              grid: { color: getBiGridColor(), drawBorder: false },
              ticks: { color: getBiTickColor(), font: { size: 10 } }
            },
            y: {
              type: 'linear',
              position: 'left',
              grid: { color: getBiGridColor(), drawBorder: false },
              ticks: { color: '#10b981', font: { size: 10 } },
              title: { display: true, text: 'Qtd. Documentos', color: '#10b981', font: { size: 10 } }
            },
            y1: {
              type: 'linear',
              position: 'right',
              grid: { display: false },
              ticks: {
                color: '#f59e0b',
                font: { size: 9.5 },
                callback: v => {
                  if (v >= 1000000) return `R$ ${(v / 1000000).toFixed(1)}M`;
                  if (v >= 1000) return `R$ ${(v / 1000).toFixed(0)}k`;
                  return `R$ ${v}`;
                }
              },
              title: { display: true, text: 'Volume Financeiro (R$)', color: '#f59e0b', font: { size: 10 } }
            }
          },
          plugins: {
            ...biChartDarkOptions.plugins,
            tooltip: {
              ...biChartDarkOptions.plugins.tooltip,
              callbacks: {
                title: items => `Ano ${labels[items[0].dataIndex] || ''}`,
                label: ctx => {
                  if (ctx.dataset.type === 'line') {
                    return ` Montante Financeiro: ${formatCurrencyBRL(ctx.raw)}`;
                  }
                  return ` Volume: ${ctx.raw} documentos - Clique p/ filtrar`;
                }
              }
            }
          }
        }
      });
    }

    // =========================================================================
    // CARD GRÁFICO 4: TOP TITULARES / BENEFICIÁRIOS / ENTIDADES
    // =========================================================================
    function renderChart4Titulares(docs, total) {
      destroyBIChart('chart4');
      const canvas = document.getElementById('chart4Canvas');
      const titleEl = document.getElementById('chart4Title');
      if (!canvas || typeof Chart === 'undefined') return;

      if (biState.domain === 'academico') {
        if (titleEl) titleEl.innerText = 'Top 10 Instituições / Faculdades Emissoras';
        const counts = {};
        docs.forEach(doc => {
          const fac = normalizeInstitution(doc.faculdade) || safeString(doc.faculdade).trim();
          if (fac) counts[fac] = (counts[fac] || 0) + 1;
        });

        const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 10);
        const labels = sorted.map(s => s[0]);
        const shortLabels = labels.map(l => l.length > 28 ? l.substring(0, 26) + '...' : l);
        const dataArr = sorted.map(s => s[1]);

        biChartInstances['chart4'] = new Chart(canvas, {
          type: 'bar',
          data: {
            labels: shortLabels,
            datasets: [{
              label: 'Documentos',
              data: dataArr,
              backgroundColor: 'rgba(245, 158, 11, 0.8)',
              hoverBackgroundColor: 'rgba(245, 158, 11, 1)',
              borderColor: '#d97706',
              borderWidth: 1,
              borderRadius: 4
            }]
          },
          options: {
            ...biChartDarkOptions,
            indexAxis: 'y',
            onClick: (evt, elements) => {
              if (elements && elements.length > 0) {
                const idx = elements[0].index;
                const instName = labels[idx];
                if (instName) filterFromBI('faculdade', instName);
              }
            },
            scales: {
              x: {
                grid: { color: getBiGridColor(), drawBorder: false },
                ticks: { color: getBiTickColor(), font: { size: 10 } }
              },
              y: {
                grid: { display: false },
                ticks: { color: getBiLabelColor(), font: { size: 10 } }
              }
            },
            plugins: {
              ...biChartDarkOptions.plugins,
              legend: { display: false },
              tooltip: {
                ...biChartDarkOptions.plugins.tooltip,
                callbacks: {
                  title: items => labels[items[0].dataIndex] || '',
                  label: ctx => ` ${ctx.raw} documentos - Clique p/ filtrar`
                }
              }
            }
          }
        });

      } else {
        if (titleEl) titleEl.innerText = 'Top 10 Titulares, Favorecidos & Entidades';

        const mapEntities = {};
        const mapValores = {};

        docs.forEach(d => {
          const ben = safeString(d.beneficiario).trim();
          if (ben && ben.length >= 3 && !ben.toLowerCase().includes('não informado')) {
            mapEntities[ben] = (mapEntities[ben] || 0) + 1;
            const val = parseMonetaryVal(d.valor_monetario);
            mapValores[ben] = (mapValores[ben] || 0.0) + val;
          }
        });

        const sorted = Object.entries(mapEntities).sort((a, b) => b[1] - a[1]).slice(0, 10);
        const labels = sorted.map(s => s[0]);
        const shortLabels = labels.map(l => l.length > 28 ? l.substring(0, 26) + '...' : l);
        const dataArr = sorted.map(s => s[1]);

        biChartInstances['chart4'] = new Chart(canvas, {
          type: 'bar',
          data: {
            labels: shortLabels,
            datasets: [{
              label: 'Documentos',
              data: dataArr,
              backgroundColor: 'rgba(59, 130, 246, 0.8)',
              hoverBackgroundColor: 'rgba(59, 130, 246, 1)',
              borderColor: '#2563eb',
              borderWidth: 1,
              borderRadius: 4
            }]
          },
          options: {
            ...biChartDarkOptions,
            indexAxis: 'y',
            onClick: (evt, elements) => {
              if (elements && elements.length > 0) {
                const idx = elements[0].index;
                const entName = labels[idx];
                if (entName) filterFromBI('titular', entName);
              }
            },
            scales: {
              x: {
                grid: { color: getBiGridColor(), drawBorder: false },
                ticks: { color: getBiTickColor(), font: { size: 10 } }
              },
              y: {
                grid: { display: false },
                ticks: { color: getBiLabelColor(), font: { size: 10 } }
              }
            },
            plugins: {
              ...biChartDarkOptions.plugins,
              legend: { display: false },
              tooltip: {
                ...biChartDarkOptions.plugins.tooltip,
                callbacks: {
                  title: items => labels[items[0].dataIndex] || '',
                  label: ctx => {
                    const idx = ctx.dataIndex;
                    const entName = labels[idx];
                    const valSum = mapValores[entName] || 0;
                    const sFmt = valSum > 0 ? ` • Montante: ${formatCurrencyBRL(valSum)}` : '';
                    return ` ${ctx.raw} documentos${sFmt} - Clique p/ filtrar`;
                  }
                }
              }
            }
          }
        });
      }
    }

    // =========================================================================
    // CARD GRÁFICO 5: RADAR DE CONFORMIDADE & QUALIDADE CADASTRAL
    // =========================================================================
    function renderChart5RadarQualidade(docs, total) {
      destroyBIChart('chart5');
      const canvas = document.getElementById('chart5Canvas');
      if (!canvas || typeof Chart === 'undefined') return;

      const hasCpfCnpj = docs.filter(d => isCpfValid(d.cpf) || isCnpjValid(d.cnpj)).length;
      const hasValor = docs.filter(d => parseMonetaryVal(d.valor_monetario) > 0).length;
      const hasData = docs.filter(d => Boolean(extractYear(d.data))).length;
      const hasTitular = docs.filter(d => Boolean(safeString(d.beneficiario).trim())).length;
      const hasAssinatura = docs.filter(d => Boolean(d.assinatura_digital || d.assinaturas_digitais || d.icp_brasil)).length;
      const hasAprovacao = docs.filter(d => safeString(d.status_conferencia).toLowerCase() === 'aprovado').length;

      const calcPct = cnt => total > 0 ? parseFloat(((cnt / total) * 100).toFixed(1)) : 0;

      const labels = [
        'CPF/CNPJ Válido',
        'Valor Monetário',
        'Data Documental',
        'Titular / Beneficiário',
        'Assinatura Digital ICP',
        'Conferência Aprovada'
      ];

      const percentages = [
        calcPct(hasCpfCnpj),
        calcPct(hasValor),
        calcPct(hasData),
        calcPct(hasTitular),
        calcPct(hasAssinatura),
        calcPct(hasAprovacao)
      ];

      biChartInstances['chart5'] = new Chart(canvas, {
        type: 'radar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Taxa de Completude (%)',
            data: percentages,
            backgroundColor: 'rgba(6, 182, 212, 0.25)',
            borderColor: '#06b6d4',
            borderWidth: 2,
            pointBackgroundColor: '#06b6d4',
            pointBorderColor: '#fff',
            pointHoverRadius: 6
          }]
        },
        options: {
          ...biChartDarkOptions,
          scales: {
            r: {
              min: 0,
              max: 100,
              angleLines: { color: getBiGridColor() },
              grid: { color: getBiGridColor() },
              pointLabels: {
                color: getBiLabelColor(),
                font: { size: 10, weight: '500' }
              },
              ticks: {
                color: getBiTickColor(),
                backdropColor: 'transparent',
                font: { size: 9 },
                callback: v => `${v}%`
              }
            }
          },
          plugins: {
            ...biChartDarkOptions.plugins,
            legend: { display: false },
            tooltip: {
              ...biChartDarkOptions.plugins.tooltip,
              callbacks: {
                label: ctx => ` ${ctx.label}: ${ctx.raw}% dos documentos com metadado válido`
              }
            }
          }
        }
      });
    }

    // =========================================================================
    // CARD GRÁFICO 6: PIPELINE DE INTEGRIDADE & AUDITORIA TÉCNICA
    // =========================================================================
    function renderChart6Pipeline(docs, total) {
      destroyBIChart('chart6');
      const canvas = document.getElementById('chart6Canvas');
      if (!canvas || typeof Chart === 'undefined') return;

      const nativos = docs.filter(d => !d.is_scanned && !d.ocr_required).length;
      const comTexto = docs.filter(d => !isDocumentUnprocessed(d)).length;
      const aprovados = docs.filter(d => safeString(d.status_conferencia).toLowerCase() === 'aprovado').length;
      const confAlta = docs.filter(d => safeString(d.confiabilidade).toLowerCase() === 'alta').length;

      const calcPct = cnt => total > 0 ? parseFloat(((cnt / total) * 100).toFixed(1)) : 0;

      const dimensions = [
        { label: 'Camada Digital Nativa', pct: calcPct(nativos), color: '#38bdf8' },
        { label: 'Texto Extraído com Sucesso', pct: calcPct(comTexto), color: '#34d399' },
        { label: 'Alta Confiabilidade IA', pct: calcPct(confAlta), color: '#a78bfa' },
        { label: 'Revisão Humana Concluída', pct: calcPct(aprovados), color: '#f472b6' }
      ];

      biChartInstances['chart6'] = new Chart(canvas, {
        type: 'polarArea',
        data: {
          labels: dimensions.map(d => d.label),
          datasets: [{
            data: dimensions.map(d => d.pct),
            backgroundColor: dimensions.map(d => d.color + 'aa'),
            hoverBackgroundColor: dimensions.map(d => d.color),
            borderColor: getBiChartBorderColor(),
            borderWidth: 1.5
          }]
        },
        options: {
          ...biChartDarkOptions,
          scales: {
            r: {
              min: 0,
              max: 100,
              grid: { color: getBiGridColor() },
              ticks: {
                color: getBiTickColor(),
                backdropColor: 'transparent',
                font: { size: 9 },
                callback: v => `${v}%`
              }
            }
          },
          plugins: {
            ...biChartDarkOptions.plugins,
            legend: {
              display: true,
              position: 'bottom',
              labels: {
                ...biChartDarkOptions.plugins.legend.labels,
                boxWidth: 10,
                font: { size: 10 }
              }
            },
            tooltip: {
              ...biChartDarkOptions.plugins.tooltip,
              callbacks: {
                label: ctx => ` ${ctx.label}: ${ctx.raw}% do acervo analisado`
              }
            }
          }
        }
      });
    }

    // =========================================================================
    // MATRIZ CRUZADA ANALÍTICA DINÂMICA (PIVOT MATRIX COM HEATMAP)
    // =========================================================================
    function onMatrixDimensionChange(dimKey) {
      biState.matrixDim = dimKey;
      renderBIDashboard();
    }

    function renderDynamicPivotTable(docs, total) {
      const thead = document.getElementById('matrixTableHead');
      const tbody = document.getElementById('matrixTableBody');
      if (!thead || !tbody) return;

      const dim = biState.matrixDim || 'dominio_status';

      if (dim === 'dominio_status') {
        const rows = ['financeiro', 'juridico', 'identificacao', 'cadastral', 'academico', 'veicular', 'outro'];
        const cols = ['Pendente', 'Aprovado'];
        const rowLabels = {
          'financeiro': '💰 Financeiro',
          'juridico': '⚖️ Jurídico',
          'identificacao': '🪪 Identificação',
          'cadastral': '🏢 Cadastral',
          'academico': '🎓 Acadêmico',
          'veicular': '🚗 Veicular',
          'outro': '📁 Outro'
        };

        const matrix = {};
        const rowTotals = {};
        const colTotals = { 'Pendente': 0, 'Aprovado': 0 };

        rows.forEach(r => {
          matrix[r] = { 'Pendente': 0, 'Aprovado': 0 };
          rowTotals[r] = 0;
        });

        docs.forEach(d => {
          let dom = safeString(d.dominio || 'outro').toLowerCase();
          if (dom === 'profissional') dom = 'cadastral';
          if (!matrix.hasOwnProperty(dom)) dom = 'outro';
          const st = safeString(d.status_conferencia).toLowerCase() === 'aprovado' ? 'Aprovado' : 'Pendente';
          matrix[dom][st]++;
          rowTotals[dom]++;
          colTotals[st]++;
        });

        const grandTotal = Object.values(rowTotals).reduce((a, b) => a + b, 0);

        thead.innerHTML = `
          <tr class="text-[11px] text-slate-300 border-b border-slate-800 bg-slate-950/60">
            <th class="p-2.5 font-semibold">Domínio Documental</th>
            <th class="p-2.5 font-semibold text-center text-amber-300">Pendente de Revisão</th>
            <th class="p-2.5 font-semibold text-center text-emerald-300">Aprovado por Operador</th>
            <th class="p-2.5 font-semibold text-right bg-slate-950/90 text-white">Total do Domínio</th>
          </tr>
        `;

        tbody.innerHTML = rows.map(r => {
          const rTot = rowTotals[r];
          const cells = cols.map(c => {
            const val = matrix[r][c];
            const pct = grandTotal > 0 ? ((val / grandTotal) * 100).toFixed(1) : '0.0';
            const displayVal = biState.unitMode === 'absoluto' ? `${val}` : (biState.unitMode === 'relativo' ? `${pct}%` : `${val} (${pct}%)`);
            let bgStyle = 'text-slate-400';
            if (val > 0) {
              const intensity = Math.min(val / (grandTotal || 1) * 3, 0.4);
              const color = c === 'Aprovado' ? 'rgba(16, 185, 129,' : 'rgba(245, 158, 11,';
              bgStyle = `style="background-color: ${color} ${intensity + 0.08}); color: #ffffff; font-weight: 600;"`;
            }
            return `<td class="p-2.5 text-center cursor-pointer hover:underline" onclick="filterFromBI('dominio', '${r}')" ${bgStyle}>${displayVal}</td>`;
          }).join('');

          const rPct = grandTotal > 0 ? ((rTot / grandTotal) * 100).toFixed(1) : '0.0';
          const rDisplay = biState.unitMode === 'absoluto' ? `${rTot}` : (biState.unitMode === 'relativo' ? `${rPct}%` : `${rTot} (${rPct}%)`);

          return `
            <tr class="hover:bg-slate-800/40 transition">
              <td class="p-2.5 text-slate-200 font-sans font-medium text-xs flex items-center justify-between">
                <span>${rowLabels[r]}</span>
                <button type="button" onclick="setBIDomain('${r}')" class="text-[10px] text-cyan-400 hover:text-cyan-300 ml-2 no-print">
                  Filtrar ➔
                </button>
              </td>
              ${cells}
              <td class="p-2.5 text-right font-bold text-white bg-slate-950/50">${rDisplay}</td>
            </tr>
          `;
        }).join('') + `
          <tr class="bg-slate-950 text-white font-bold border-t-2 border-slate-800">
            <td class="p-2.5 font-sans text-xs">TOTAL GERAL</td>
            ${cols.map(c => {
              const tot = colTotals[c];
              const pct = grandTotal > 0 ? ((tot / grandTotal) * 100).toFixed(1) : '0.0';
              const dVal = biState.unitMode === 'absoluto' ? `${tot}` : (biState.unitMode === 'relativo' ? `${pct}%` : `${tot} (${pct}%)`);
              return `<td class="p-2.5 text-center text-cyan-300">${dVal}</td>`;
            }).join('')}
            <td class="p-2.5 text-right text-emerald-400 font-extrabold text-sm">${grandTotal.toLocaleString('pt-BR')} (100%)</td>
          </tr>
        `;

      } else if (dim === 'classe_faixa') {
        const [b1, b2, b3] = biState.brackets;
        const b1Fmt = b1 >= 1000 ? `${b1/1000}k` : `${b1}`;
        const b2Fmt = b2 >= 1000 ? `${b2/1000}k` : `${b2}`;
        const b3Fmt = b3 >= 1000 ? `${b3/1000}k` : `${b3}`;

        const colHeaders = [
          `Até R$ ${b1Fmt}`,
          `R$ ${b1Fmt}-${b2Fmt}`,
          `R$ ${b2Fmt}-${b3Fmt}`,
          `> R$ ${b3Fmt}`,
          'Sem Valor'
        ];

        const mapClasses = {};
        docs.forEach(d => {
          const c = safeString(d.tipo_documento).trim() || 'Outro';
          mapClasses[c] = (mapClasses[c] || 0) + 1;
        });

        const topClasses = Object.entries(mapClasses).sort((a, b) => b[1] - a[1]).slice(0, 8).map(s => s[0]);
        const matrix = {};
        const rowTotals = {};
        const colTotals = [0, 0, 0, 0, 0];

        topClasses.forEach(c => {
          matrix[c] = [0, 0, 0, 0, 0];
          rowTotals[c] = 0;
        });

        docs.forEach(d => {
          const c = safeString(d.tipo_documento).trim() || 'Outro';
          if (!matrix.hasOwnProperty(c)) return;
          const val = parseMonetaryVal(d.valor_monetario);
          let colIdx = 4;
          if (val > 0) {
            if (val <= b1) colIdx = 0;
            else if (val <= b2) colIdx = 1;
            else if (val <= b3) colIdx = 2;
            else colIdx = 3;
          }
          matrix[c][colIdx]++;
          rowTotals[c]++;
          colTotals[colIdx]++;
        });

        const grandTotal = Object.values(rowTotals).reduce((a, b) => a + b, 0);

        thead.innerHTML = `
          <tr class="text-[11px] text-slate-300 border-b border-slate-800 bg-slate-950/60">
            <th class="p-2.5 font-semibold">Classe Documental</th>
            ${colHeaders.map(ch => `<th class="p-2.5 font-semibold text-center">${ch}</th>`).join('')}
            <th class="p-2.5 font-semibold text-right bg-slate-950/90 text-white">Total</th>
          </tr>
        `;

        tbody.innerHTML = topClasses.map(c => {
          const rTot = rowTotals[c];
          const cells = matrix[c].map(val => {
            const pct = grandTotal > 0 ? ((val / grandTotal) * 100).toFixed(1) : '0.0';
            const displayVal = biState.unitMode === 'absoluto' ? `${val}` : (biState.unitMode === 'relativo' ? `${pct}%` : `${val} (${pct}%)`);
            let highlight = 'text-slate-400';
            if (val > 0) highlight = 'bg-emerald-500/15 text-emerald-300 font-semibold';
            return `<td class="p-2.5 text-center ${highlight}">${displayVal}</td>`;
          }).join('');

          const rPct = grandTotal > 0 ? ((rTot / grandTotal) * 100).toFixed(1) : '0.0';
          const rDisplay = biState.unitMode === 'absoluto' ? `${rTot}` : (biState.unitMode === 'relativo' ? `${rPct}%` : `${rTot} (${rPct}%)`);

          return `
            <tr class="hover:bg-slate-800/40 transition">
              <td class="p-2.5 text-slate-200 font-sans font-medium text-xs flex items-center justify-between">
                <span>${c}</span>
                <button type="button" onclick="filterFromBI('classe', '${escapeHtmlAttr(c)}')" class="text-[10px] text-cyan-400 hover:text-cyan-300 ml-2 no-print">
                  Filtrar ➔
                </button>
              </td>
              ${cells}
              <td class="p-2.5 text-right font-bold text-white bg-slate-950/50">${rDisplay}</td>
            </tr>
          `;
        }).join('');

      } else {
        const naturezas = [
          'Pós-Graduação Lato Sensu (Especialização/MBA)',
          'Curso Técnico / Profissionalizante',
          'Graduação / Curso Superior',
          'Curso de Extensão / Aperfeiçoamento',
          'Educação Básica',
          'Pós-Graduação Stricto Sensu (Mestrado/Doutorado)',
          'Não identificada'
        ];

        const tipos = [
          'Diploma',
          'Certificado',
          'Histórico Escolar',
          'Declaração / Atestado',
          'Outro / Não identificado'
        ];

        const matrix = {};
        const rowTotals = {};
        const colTotals = {};
        tipos.forEach(t => colTotals[t] = 0);

        naturezas.forEach(n => {
          matrix[n] = {};
          rowTotals[n] = 0;
          tipos.forEach(t => matrix[n][t] = 0);
        });

        docs.forEach(doc => {
          const matchedNat = classifyNatureza(doc.natureza_curso);
          const rawTipo = normalizeText(safeString(doc.tipo_documento));
          let matchedTipo = 'Outro / Não identificado';
          if (rawTipo.includes('diploma')) matchedTipo = 'Diploma';
          else if (rawTipo.includes('certificado')) matchedTipo = 'Certificado';
          else if (rawTipo.includes('historico')) matchedTipo = 'Histórico Escolar';
          else if (rawTipo.includes('declaracao') || rawTipo.includes('atestado')) matchedTipo = 'Declaração / Atestado';

          matrix[matchedNat][matchedTipo]++;
          rowTotals[matchedNat]++;
          colTotals[matchedTipo]++;
        });

        const grandTotal = Object.values(rowTotals).reduce((a, b) => a + b, 0);

        thead.innerHTML = `
          <tr class="text-[11px] text-slate-300 border-b border-slate-800 bg-slate-950/60">
            <th class="p-2.5 font-semibold">Nível / Natureza</th>
            <th class="p-2.5 font-semibold text-center">Diploma</th>
            <th class="p-2.5 font-semibold text-center">Certificado</th>
            <th class="p-2.5 font-semibold text-center">Histórico</th>
            <th class="p-2.5 font-semibold text-center">Declaração</th>
            <th class="p-2.5 font-semibold text-center">Outros</th>
            <th class="p-2.5 font-semibold text-right bg-slate-950/90 text-white">Total Geral</th>
          </tr>
        `;

        tbody.innerHTML = naturezas.map(n => {
          const rowTotal = rowTotals[n];
          const rowPct = grandTotal > 0 ? ((rowTotal / grandTotal) * 100).toFixed(1) : '0.0';
          const cells = tipos.map(t => {
            const c = matrix[n][t];
            const cPct = grandTotal > 0 ? ((c / grandTotal) * 100).toFixed(1) : '0.0';
            let highlight = 'text-slate-400';
            if (c > 0) highlight = 'bg-emerald-500/10 text-emerald-300 font-semibold';
            let displayVal = `${c}`;
            if (biState.unitMode === 'relativo') displayVal = `${cPct}%`;
            else if (biState.unitMode === 'ambos') displayVal = `${c} (${cPct}%)`;
            return `<td class="p-2.5 text-center ${highlight}">${displayVal}</td>`;
          }).join('');

          let displayRowTotal = `${rowTotal} (${rowPct}%)`;
          if (biState.unitMode === 'absoluto') displayRowTotal = `${rowTotal}`;
          else if (biState.unitMode === 'relativo') displayRowTotal = `${rowPct}%`;

          return `
            <tr class="hover:bg-slate-800/40 transition">
              <td class="p-2.5 text-slate-200 font-sans font-medium text-xs flex items-center justify-between">
                <span>${n}</span>
                <button type="button" onclick="filterFromBI('natureza', '${escapeHtmlAttr(n)}')" class="text-[10px] text-purple-400 hover:text-purple-300 ml-2 no-print">
                  Filtrar ➔
                </button>
              </td>
              ${cells}
              <td class="p-2.5 text-right font-bold text-white bg-slate-950/50">${displayRowTotal}</td>
            </tr>
          `;
        }).join('') + `
          <tr class="bg-slate-950 text-white font-bold border-t-2 border-slate-800">
            <td class="p-2.5 font-sans text-xs">TOTAL GERAL</td>
            ${tipos.map(t => {
              const colTot = colTotals[t];
              const colPct = grandTotal > 0 ? ((colTot / grandTotal) * 100).toFixed(1) : '0.0';
              let displayCol = `${colTot} (${colPct}%)`;
              if (biState.unitMode === 'absoluto') displayCol = `${colTot}`;
              else if (biState.unitMode === 'relativo') displayCol = `${colPct}%`;
              return `<td class="p-2.5 text-center text-cyan-300">${displayCol}</td>`;
            }).join('')}
            <td class="p-2.5 text-right text-emerald-400 font-extrabold text-sm">${grandTotal.toLocaleString('pt-BR')} (100%)</td>
          </tr>
        `;
      }
    }

    // =========================================================================
    // MODAL DE CONFIGURAÇÃO DE PREFERÊNCIAS DO BI
    // =========================================================================
    function openBIConfigModal() {
      const modal = document.getElementById('modalBIConfig');
      if (!modal) return;
      const selMode = document.getElementById('configBIStartupMode');
      if (selMode) selMode.value = biState.startupMode || 'geral';
      const b1 = document.getElementById('configBIBracket1');
      const b2 = document.getElementById('configBIBracket2');
      const b3 = document.getElementById('configBIBracket3');
      if (b1) b1.value = biState.brackets[0] || 1000;
      if (b2) b2.value = biState.brackets[1] || 10000;
      if (b3) b3.value = biState.brackets[2] || 100000;
      modal.classList.remove('hidden');
    }

    function closeBIConfigModal() {
      const modal = document.getElementById('modalBIConfig');
      if (modal) modal.classList.add('hidden');
    }

    function applyBIBracketsPreset(v1, v2, v3) {
      const b1 = document.getElementById('configBIBracket1');
      const b2 = document.getElementById('configBIBracket2');
      const b3 = document.getElementById('configBIBracket3');
      if (b1) b1.value = v1;
      if (b2) b2.value = v2;
      if (b3) b3.value = v3;
    }

    function saveBIConfigPreferences() {
      const selMode = document.getElementById('configBIStartupMode');
      const b1 = parseFloat(document.getElementById('configBIBracket1').value) || 1000;
      const b2 = parseFloat(document.getElementById('configBIBracket2').value) || 10000;
      const b3 = parseFloat(document.getElementById('configBIBracket3').value) || 100000;

      if (b1 <= 0 || b2 <= b1 || b3 <= b2) {
        alert('Por favor, informe valores numéricos estritamente crescentes para os cortes das faixas de valor (Corte 1 < Corte 2 < Corte 3).');
        return;
      }

      biState.startupMode = selMode ? selMode.value : 'geral';
      biState.brackets = [b1, b2, b3];

      try {
        localStorage.setItem('joakindex_bi_startup_mode', biState.startupMode);
        localStorage.setItem('joakindex_bi_brackets', JSON.stringify(biState.brackets));
      } catch (e) {}

      closeBIConfigModal();
      showToast('Preferências do BI salvas com sucesso! Recalculando painel...', 'success');
      fetchBIExtendedStats();
      renderBIDashboard();
    }

    function restoreBIConfigDefaults() {
      applyBIBracketsPreset(1000, 10000, 100000);
      const selMode = document.getElementById('configBIStartupMode');
      if (selMode) selMode.value = 'geral';
    }

    // =========================================================================
    // EXPORTAÇÃO DE RELATÓRIOS (PDF, TXT E CSV)
    // =========================================================================
    function downloadBIPdfReport() {
      const bStr = biState.brackets.join(',');
      showToast('Gerando Relatório Executivo de Auditoria em PDF diagramado...', 'info');
      const url = `/api/relatorio/pdf?brackets=${encodeURIComponent(bStr)}`;
      const win = window.open(url, '_blank');
      if (!win) {
        window.location.href = url;
      }
    }

    function exportBIReport() {
      const allDocs = documents || [];
      const totalAcervo = allDocs.length;
      const classifDocs = allDocs.filter(d => !isDocumentUnprocessed(d));
      const unprocDocs = allDocs.filter(d => isDocumentUnprocessed(d));
      const aprovDocs = classifDocs.filter(d => safeString(d.status_conferencia).toLowerCase() === 'aprovado');
      const nowStr = new Date().toLocaleString('pt-BR');

      let totalValor = 0.0;
      let countWithVal = 0;
      allDocs.forEach(d => {
        const v = parseMonetaryVal(d.valor_monetario);
        if (v > 0) {
          totalValor += v;
          countWithVal++;
        }
      });
      const ticketMedio = countWithVal > 0 ? (totalValor / countWithVal) : 0;

      const lines = [
        '='.repeat(80),
        'JOAKINDEX - RELATÓRIO EXECUTIVO DE BUSINESS INTELLIGENCE & ANALYTICS',
        'Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>',
        `Data e Hora de Emissão: ${nowStr}`,
        '='.repeat(80),
        '',
        '1. RESUMO EXECUTIVO MULTIDOMÍNIO',
        `  • Total de Documentos Indexados : ${totalAcervo}`,
        `  • Classificados pela IA         : ${classifDocs.length} (${totalAcervo > 0 ? ((classifDocs.length / totalAcervo) * 100).toFixed(1) : 0}%)`,
        `  • Pendentes de Leitura / OCR    : ${unprocDocs.length} (${totalAcervo > 0 ? ((unprocDocs.length / totalAcervo) * 100).toFixed(1) : 0}%)`,
        `  • Revisão Humana Aprovada       : ${aprovDocs.length} (${classifDocs.length > 0 ? ((aprovDocs.length / classifDocs.length) * 100).toFixed(1) : 0}% dos classificados)`,
        `  • Patrimônio Financeiro Mapeado : ${formatCurrencyBRL(totalValor)}`,
        `  • Ticket Médio por Transação    : ${formatCurrencyBRL(ticketMedio)} (${countWithVal} documentos com valor)`,
        '',
        '-'.repeat(80),
        '2. DISTRIBUIÇÃO POR DOMÍNIO',
        '-'.repeat(80)
      ];

      const domCounts = {};
      allDocs.forEach(d => {
        const dom = safeString(d.dominio || 'outro').toLowerCase();
        domCounts[dom] = (domCounts[dom] || 0) + 1;
      });
      Object.entries(domCounts).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => {
        const pct = totalAcervo > 0 ? ((v / totalAcervo) * 100).toFixed(1) : '0.0';
        lines.push(`  • ${k.toUpperCase().padEnd(20, ' ')}: ${String(v).padStart(5, ' ')} docs (${pct}%)`);
      });

      lines.push('');
      lines.push('-'.repeat(80));
      lines.push('3. TOP CLASSES DOCUMENTAIS');
      lines.push('-'.repeat(80));

      const classCounts = {};
      allDocs.forEach(d => {
        const c = safeString(d.tipo_documento).trim() || 'Não especificado';
        classCounts[c] = (classCounts[c] || 0) + 1;
      });
      Object.entries(classCounts).sort((a, b) => b[1] - a[1]).slice(0, 15).forEach(([k, v], i) => {
        const pct = totalAcervo > 0 ? ((v / totalAcervo) * 100).toFixed(1) : '0.0';
        lines.push(`  [${String(i + 1).padStart(2, '0')}] ${k.padEnd(46, '.')} ${String(v).padStart(5, ' ')} (${pct}%)`);
      });

      lines.push('');
      lines.push('='.repeat(80));
      lines.push('FIM DO RELATÓRIO DE BI & UNIVERSAL ANALYTICS');
      lines.push('='.repeat(80));

      const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `relatorio_estatistico_bi_${new Date().toISOString().slice(0, 10)}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('Relatório executivo TXT baixado com sucesso!', 'success');
    }

    function exportBICSV() {
      const allDocs = documents || [];
      const total = allDocs.length;

      const rows = [
        ['Secao', 'Categoria', 'Quantidade_Absoluta', 'Percentual_Relativo', 'Montante_Reais']
      ];

      // Domínios
      const domCounts = {};
      allDocs.forEach(d => {
        const dom = safeString(d.dominio || 'outro').toLowerCase();
        domCounts[dom] = (domCounts[dom] || 0) + 1;
      });
      Object.entries(domCounts).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => {
        const pct = total > 0 ? ((v / total) * 100).toFixed(1) : '0.0';
        rows.push(['Dominio', k, v, `${pct}%`, '']);
      });

      // Classes
      const classCounts = {};
      const classSums = {};
      allDocs.forEach(d => {
        const c = safeString(d.tipo_documento).trim() || 'Outro';
        classCounts[c] = (classCounts[c] || 0) + 1;
        const val = parseMonetaryVal(d.valor_monetario);
        classSums[c] = (classSums[c] || 0.0) + val;
      });
      Object.entries(classCounts).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => {
        const pct = total > 0 ? ((v / total) * 100).toFixed(1) : '0.0';
        const sVal = classSums[k] > 0 ? classSums[k].toFixed(2) : '';
        rows.push(['Classe_Documental', k, v, `${pct}%`, sVal]);
      });

      const csvContent = '\uFEFF' + rows.map(r => r.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(';')).join('\r\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `estatisticas_joakindex_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('Tabela analítica CSV baixada com sucesso!', 'success');
    }

    async function confirmarUniformizacaoInstituicoes() {
      const confirmMsg = `✨ UNIFORMIZAÇÃO INTELIGENTE DE INSTITUIÇÕES DE ENSINO\n\n` +
        `Deseja unificar nomes e variações de ordem em toda a base de dados?\n\n` +
        `• Converte variações (ex: 'SIGLA - Nome' e 'Nome - SIGLA') para o padrão canônico 'Nome por Extenso (SIGLA)'.\n` +
        `• Unifica siglas e nomes fragmentados (FIVAR, UNIFTB, FAB, CETEC, FACI, Dominius, etc.).\n` +
        `• Atualiza permanentemente o JSON consolidado, o relatório TXT e as fichas individuais.\n` +
        `• NÃO é necessário reprocessar nenhum PDF: o processo dura apenas 1 a 2 segundos.\n\n` +
        `Deseja prosseguir com a consolidação da base?`;

      if (!confirm(confirmMsg)) return;

      const notifId = showToast('Uniformizando instituições na base de dados...', 'info', 0);
      try {
        const resp = await fetch('/api/uniformizar_instituicoes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });

        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.mensagem || `Erro HTTP ${resp.status}`);
        }

        const data = await resp.json();
        removeToast(notifId);

        const msgSucesso = `✓ Base de dados uniformizada com sucesso!\n\n` +
          `• Total de registros analisados: ${data.total_registros}\n` +
          `• Documentos ajustados: ${data.total_modificados}\n` +
          `• Fichas individuais salvas: ${data.individuais_atualizados}\n` +
          `• Instituições únicas: de ${data.instituicoes_antes} para ${data.instituicoes_depois}\n` +
          `• Fragmentações eliminadas: ${data.reducao_fragmentacao} variações unificadas!`;

        alert(msgSucesso);
        showToast(`Instituições consolidadas: ${data.instituicoes_depois} entidades únicas!`, 'success');

        await loadDocuments();
        refreshBIDashboard(true);
      } catch (e) {
        removeToast(notifId);
        alert(`Falha ao uniformizar instituições: ${e.message}`);
        showToast(`Erro na uniformização: ${e.message}`, 'error');
      }
    }

    // =========================================================
    // SUÍTE AVANÇADA: DASHBOARD, DOSSIÊS, DUPLICATAS & DISPATCHER
    // =========================================================

    // 1. Dashboard Gerencial & Relatório
    async function openGovernanceDashboard() {
      const modal = document.getElementById('modalGovernance');
      if (!modal) return;
      modal.classList.remove('hidden');
      const body = document.getElementById('governanceModalBody');
      body.innerHTML = `<div class="text-center py-6 text-slate-400"><i class="fa-solid fa-spinner fa-spin text-emerald-400 text-lg mr-2"></i>Carregando métricas gerenciais...</div>`;

      try {
        const resp = await fetch('/api/estatisticas_gerenciais');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        const total = data.total_docs || 0;
        const totalFin = data.total_financeiro_fmt || 'R$ 0,00';
        const conf = data.confiabilidade || {};
        const confAltaPct = total ? Math.round((conf.alta || 0) / total * 100) : 0;

        let classesHtml = '';
        const topClasses = Object.entries(data.classes_distribuicao || {}).slice(0, 10);
        topClasses.forEach(([cName, count]) => {
          const pct = total ? Math.round(count / total * 100) : 0;
          classesHtml += `
            <div class="flex items-center justify-between py-1 border-b border-slate-800/60 text-xs">
              <span class="text-slate-200 truncate max-w-[280px]">${cName}</span>
              <div class="flex items-center gap-2">
                <span class="font-mono text-slate-400">${count}</span>
                <span class="text-[10px] text-slate-500 w-8 text-right">${pct}%</span>
              </div>
            </div>
          `;
        });

        body.innerHTML = `
          <!-- Cartões de KPI -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            <div class="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
              <div class="text-[10px] text-slate-400 uppercase font-semibold">Total Documentos</div>
              <div class="text-xl font-bold text-white font-mono mt-0.5">${total}</div>
              <div class="text-[10px] text-slate-500 mt-0.5">Base indexada</div>
            </div>
            <div class="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
              <div class="text-[10px] text-emerald-400 uppercase font-semibold">Total Financeiro</div>
              <div class="text-lg font-bold text-emerald-400 font-mono mt-0.5 truncate" title="${totalFin}">${totalFin}</div>
              <div class="text-[10px] text-slate-500 mt-0.5">Boletos & PIX</div>
            </div>
            <div class="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
              <div class="text-[10px] text-cyan-400 uppercase font-semibold">Confiabilidade</div>
              <div class="text-xl font-bold text-cyan-300 font-mono mt-0.5">${confAltaPct}%</div>
              <div class="text-[10px] text-slate-500 mt-0.5">Alta precisão</div>
            </div>
            <div class="bg-slate-950/70 p-3 rounded-xl border border-slate-800">
              <div class="text-[10px] text-purple-400 uppercase font-semibold">Assinaturas ICP</div>
              <div class="text-xl font-bold text-purple-300 font-mono mt-0.5">${data.assinaturas_count || 0}</div>
              <div class="text-[10px] text-slate-500 mt-0.5">Criptografados</div>
            </div>
          </div>

          <!-- Linha com Duplicatas e Nativos -->
          <div class="grid grid-cols-2 gap-2.5 text-xs">
            <div class="bg-slate-950/50 p-3 rounded-xl border border-slate-800/80 flex items-center justify-between">
              <div>
                <span class="text-slate-300 font-medium block">Nativos Digitais vs OCR</span>
                <span class="text-[11px] text-slate-500">${data.nativos_digitais_count || 0} nativos / ${total - (data.nativos_digitais_count || 0)} digitalizados</span>
              </div>
              <span class="px-2 py-1 bg-sky-500/10 text-sky-400 border border-sky-500/20 rounded font-mono">${Math.round(((data.nativos_digitais_count || 0) / (total || 1)) * 100)}%</span>
            </div>
            <div class="bg-slate-950/50 p-3 rounded-xl border border-slate-800/80 flex items-center justify-between">
              <div>
                <span class="text-slate-300 font-medium block">Possíveis Duplicatas</span>
                <span class="text-[11px] text-slate-500">${data.duplicatas_count || 0} documentos redundantes</span>
              </div>
              <button onclick="closeGovernanceModal(); openDuplicatesModal();" class="px-2 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 rounded text-[11px]">Revisar</button>
            </div>
          </div>

          <!-- Top Classes Documentais -->
          <div class="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800 space-y-2">
            <div class="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 pb-1 border-b border-slate-800">
              <i class="fa-solid fa-chart-pie text-emerald-400"></i> Principais Classes no Acervo
            </div>
            <div class="space-y-1 max-h-48 overflow-y-auto pr-1">
              ${classesHtml || '<p class="text-slate-500 text-center py-2">Nenhuma classe identificada</p>'}
            </div>
          </div>
        `;
      } catch (e) {
        body.innerHTML = `<div class="p-4 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-300">Falha ao carregar métricas: ${e.message}</div>`;
      }
    }

    function closeGovernanceModal() {
      const modal = document.getElementById('modalGovernance');
      if (modal) modal.classList.add('hidden');
    }

    // 2. Dossiês Inteligentes
    async function openDossiersModal() {
      const modal = document.getElementById('modalDossiers');
      if (!modal) return;
      modal.classList.remove('hidden');
      loadDossiersData();
    }

    function closeDossiersModal() {
      const modal = document.getElementById('modalDossiers');
      if (modal) modal.classList.add('hidden');
    }

    async function loadDossiersData() {
      const body = document.getElementById('dossiersModalBody');
      body.innerHTML = `<div class="text-center py-6 text-slate-400"><i class="fa-solid fa-spinner fa-spin text-indigo-400 text-lg mr-2"></i>Carregando dossiês agrupados...</div>`;
      try {
        const resp = await fetch('/api/dossies');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const dossiers = await resp.json();

        if (dossiers.length === 0) {
          body.innerHTML = `
            <div class="text-center py-10 space-y-3 text-slate-400">
              <i class="fa-solid fa-folder-open text-3xl text-slate-600"></i>
              <p>Nenhum dossiê com 2 ou mais documentos identificado ainda.</p>
              <button onclick="recalculateDossiers()" class="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold">
                Executar Agrupamento Inteligente Agora
              </button>
            </div>
          `;
          return;
        }

        let html = `<div class="space-y-3">`;
        dossiers.forEach(dos => {
          const docsHtml = (dos.documentos || []).map(d => `
            <div class="flex items-center justify-between py-1 px-2 hover:bg-slate-900 rounded text-[11px] text-slate-300">
              <span class="truncate max-w-[320px] font-mono">${d.nome_arquivo}</span>
              <span class="px-1.5 py-0.2 bg-slate-800 text-slate-400 rounded text-[10px]">${d.tipo_documento || 'Geral'}</span>
            </div>
          `).join('');

          html += `
            <div class="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800 space-y-2">
              <div class="flex items-center justify-between pb-1 border-b border-slate-800">
                <div class="flex items-center gap-2">
                  <i class="fa-solid fa-folder text-indigo-400 text-base"></i>
                  <div>
                    <h5 class="font-semibold text-slate-100">${dos.nome_titular || dos.identificador}</h5>
                    <span class="text-[10px] text-slate-400 font-mono">${dos.tipo_entidade}: ${dos.identificador} • ${dos.total_documentos} documentos</span>
                  </div>
                </div>
                <button onclick="exportDossierSinglePdf('${dos.id}')" class="px-2.5 py-1 bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 border border-indigo-500/30 rounded text-xs font-medium flex items-center gap-1 transition">
                  <i class="fa-solid fa-file-pdf"></i>
                  <span>Exportar PDF</span>
                </button>
              </div>
              <div class="space-y-0.5 bg-slate-900/60 p-1.5 rounded-lg max-h-32 overflow-y-auto">
                ${docsHtml}
              </div>
            </div>
          `;
        });
        html += `</div>`;
        body.innerHTML = html;
      } catch (e) {
        body.innerHTML = `<div class="p-4 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-300">Falha ao carregar dossiês: ${e.message}</div>`;
      }
    }

    async function recalculateDossiers() {
      const body = document.getElementById('dossiersModalBody');
      body.innerHTML = `<div class="text-center py-6 text-slate-400"><i class="fa-solid fa-spinner fa-spin text-indigo-400 text-lg mr-2"></i>Cruzando entidades e reconstruindo dossiês...</div>`;
      try {
        const resp = await fetch('/api/dossies/gerar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const data = await resp.json();
        if (data.status === 'sucesso') {
          showToast(`Dossiês calculados: ${data.total_dossies} grupos identificados!`, 'success');
          await loadDocuments();
          loadDossiersData();
        } else {
          alert(`Erro: ${data.mensagem}`);
        }
      } catch (e) {
        alert(`Erro de conexão: ${e.message}`);
      }
    }

    async function exportDossierSinglePdf(dossieId) {
      showToast('Fundindo PDFs do dossiê...', 'info');
      try {
        const resp = await fetch('/api/dossies/exportar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dossie_id: dossieId })
        });
        const data = await resp.json();
        if (data.status === 'sucesso') {
          alert(`✓ ${data.mensagem}\n\nSalvo em: ${data.caminho}`);
          showToast('Dossiê exportado com sucesso!', 'success');
        } else {
          alert(`Erro: ${data.mensagem}`);
        }
      } catch (e) {
        alert(`Erro ao exportar: ${e.message}`);
      }
    }

    // 3. Central de Duplicatas
    async function openDuplicatesModal() {
      const modal = document.getElementById('modalDuplicates');
      if (!modal) return;
      modal.classList.remove('hidden');
      loadDuplicatesData();
    }

    function closeDuplicatesModal() {
      const modal = document.getElementById('modalDuplicates');
      if (modal) modal.classList.add('hidden');
    }

    let currentCompareData = null;
    let currentCompareTab = 'media';

    async function loadDuplicatesData() {
      const body = document.getElementById('duplicatesModalBody');
      body.innerHTML = `<div class="text-center py-6 text-slate-400"><i class="fa-solid fa-spinner fa-spin text-rose-400 text-lg mr-2"></i>Calculando similaridade e varrendo duplicatas...</div>`;
      try {
        const resp = await fetch('/api/duplicatas');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const pairs = await resp.json();

        if (pairs.length === 0) {
          body.innerHTML = `
            <div class="text-center py-10 space-y-2 text-slate-400">
              <i class="fa-solid fa-circle-check text-3xl text-emerald-400"></i>
              <p class="font-medium text-slate-200">Nenhuma duplicata detectada!</p>
              <p class="text-xs text-slate-500">Todos os documentos do lote apresentam conteúdos e assinaturas únicos.</p>
            </div>
          `;
          return;
        }

        let html = `<div class="space-y-3">`;
        pairs.forEach((p, idx) => {
          const simPct = p.similaridade_pct || Math.round(p.similaridade * 100);
          const isHigh = simPct >= 95;
          const badgeBg = isHigh ? 'bg-rose-500/20 text-rose-300 border-rose-500/40' : 'bg-amber-500/20 text-amber-300 border-amber-500/40';
          const progressBg = isHigh ? 'bg-rose-500' : 'bg-amber-500';

          html += `
            <div class="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800 hover:border-slate-700 transition space-y-3 shadow-sm">
              <div class="flex items-center justify-between pb-2 border-b border-slate-800">
                <div class="flex items-center gap-2">
                  <span class="px-2 py-0.5 rounded font-mono font-bold text-[11px] border ${badgeBg}">
                    ${p.tipo} (${simPct}% similaridade)
                  </span>
                  <span class="text-slate-400 text-[11px]">Classe: <strong class="text-slate-200">${escapeHtml(p.classe)}</strong></span>
                </div>
                <!-- Barra de progresso visual de similaridade -->
                <div class="flex items-center gap-2">
                  <div class="w-24 h-2 rounded-full bg-slate-800 overflow-hidden" title="${simPct}% de coincidência">
                    <div class="h-full ${progressBg} rounded-full" style="width: ${simPct}%"></div>
                  </div>
                  <span class="text-[10px] font-mono font-bold text-slate-400">${simPct}%</span>
                </div>
              </div>

              <!-- Cartões Comparativos lado a lado com metadados chave -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-2.5 text-xs">
                <!-- Base / Original -->
                <div class="bg-slate-900/70 p-2.5 rounded-lg border border-slate-800 space-y-1.5 cursor-pointer hover:bg-slate-900 transition" onclick="openCompareDuplicatesModal('${p.canonico_md5}', '${p.duplicata_md5}')" title="Clique para abrir comparador visual detalhado">
                  <div class="flex items-center justify-between">
                    <span class="text-[10px] text-emerald-400 font-bold uppercase tracking-wider flex items-center gap-1">
                      <i class="fa-solid fa-file text-[10px]"></i> Documento Base
                    </span>
                    <span class="text-[9px] font-mono text-slate-500">${p.canonico_extensao || 'PDF'}</span>
                  </div>
                  <div class="font-mono text-slate-200 font-medium truncate" title="${escapeHtml(p.canonico_nome)}">
                    ${escapeHtml(p.canonico_nome)}
                  </div>
                  <div class="grid grid-cols-2 gap-1 text-[11px] pt-1 border-t border-slate-800/80 text-slate-400">
                    <div class="truncate"><span class="text-slate-500 block text-[9px]">Valor</span><span class="text-emerald-400 font-semibold">${escapeHtml(p.canonico_valor || '-')}</span></div>
                    <div class="truncate"><span class="text-slate-500 block text-[9px]">CPF / Data</span>${escapeHtml(p.canonico_cpf || p.canonico_data || '-')}</div>
                  </div>
                </div>

                <!-- Cópia Duplicada -->
                <div class="bg-slate-900/70 p-2.5 rounded-lg border border-rose-900/40 space-y-1.5 cursor-pointer hover:bg-slate-900 transition" onclick="openCompareDuplicatesModal('${p.canonico_md5}', '${p.duplicata_md5}')" title="Clique para abrir comparador visual detalhado">
                  <div class="flex items-center justify-between">
                    <span class="text-[10px] text-rose-400 font-bold uppercase tracking-wider flex items-center gap-1">
                      <i class="fa-solid fa-copy text-[10px]"></i> Cópia Duplicada
                    </span>
                    <span class="text-[9px] font-mono text-slate-500">${p.duplicata_extensao || 'PDF'}</span>
                  </div>
                  <div class="font-mono text-slate-200 font-medium truncate" title="${escapeHtml(p.duplicata_nome)}">
                    ${escapeHtml(p.duplicata_nome)}
                  </div>
                  <div class="grid grid-cols-2 gap-1 text-[11px] pt-1 border-t border-slate-800/80 text-slate-400">
                    <div class="truncate"><span class="text-slate-500 block text-[9px]">Valor</span><span class="text-rose-400 font-semibold">${escapeHtml(p.duplicata_valor || '-')}</span></div>
                    <div class="truncate"><span class="text-slate-500 block text-[9px]">CPF / Data</span>${escapeHtml(p.duplicata_cpf || p.duplicata_data || '-')}</div>
                  </div>
                </div>
              </div>

              <!-- Barra de Ações: Comparar e Decidir -->
              <div class="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-slate-800/80">
                <button type="button" onclick="openCompareDuplicatesModal('${p.canonico_md5}', '${p.duplicata_md5}')"
                        class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow-sm">
                  <i class="fa-solid fa-code-compare"></i>
                  <span>Inspecionar e Comparar Lado a Lado</span>
                </button>
                <div class="flex items-center gap-2">
                  <button type="button" onclick="resolveDuplicateAction('${p.duplicata_md5}', true)"
                          class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition" title="Marcar como documentos distintos">
                    Descartar Falso Positivo
                  </button>
                  <button type="button" onclick="resolveDuplicateAction('${p.duplicata_md5}', false)"
                          class="px-3 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-bold transition shadow" title="Confirmar como duplicata no banco de dados">
                    Confirmar Duplicata
                  </button>
                </div>
              </div>
            </div>
          `;
        });
        html += `</div>`;
        body.innerHTML = html;
      } catch (e) {
        body.innerHTML = `<div class="p-4 bg-rose-500/10 border border-rose-500/20 rounded-lg text-rose-300">Falha ao buscar duplicatas: ${e.message}</div>`;
      }
    }

    // Modal Comparador Visual Detalhado
    async function openCompareDuplicatesModal(baseMd5, copiaMd5) {
      const modal = document.getElementById('modalCompareDuplicates');
      if (!modal) return;
      modal.classList.remove('hidden');

      const spinner = document.getElementById('compareLoadingSpinner');
      const content = document.getElementById('compareContentArea');
      if (spinner) spinner.classList.remove('hidden');
      if (content) content.classList.add('hidden');

      try {
        const resp = await fetch(`/api/duplicatas/comparar?base=${baseMd5}&copia=${copiaMd5}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        if (data.erro) throw new Error(data.erro);

        currentCompareData = data;
        const badge = document.getElementById('compareSimilarityBadge');
        if (badge) {
          badge.innerText = `${data.similaridade_pct}% Similaridade (${data.tipo})`;
          badge.className = data.similaridade_pct >= 95 
            ? 'px-2.5 py-0.5 rounded-full font-mono font-bold text-[11px] bg-rose-500/20 text-rose-300 border border-rose-500/40'
            : 'px-2.5 py-0.5 rounded-full font-mono font-bold text-[11px] bg-amber-500/20 text-amber-300 border border-amber-500/40';
        }

        // Configura ações de rodapé
        const btnConfirm = document.getElementById('btnCompareConfirm');
        const btnDiscard = document.getElementById('btnCompareDiscard');
        const btnBaseMain = document.getElementById('btnCompareOpenBaseMain');
        const btnDupMain = document.getElementById('btnCompareOpenDupMain');

        if (btnConfirm) btnConfirm.onclick = () => resolveDuplicateAction(copiaMd5, false, true);
        if (btnDiscard) btnDiscard.onclick = () => resolveDuplicateAction(copiaMd5, true, true);
        if (btnBaseMain) btnBaseMain.onclick = () => navigateToDocByMd5(baseMd5);
        if (btnDupMain) btnDupMain.onclick = () => navigateToDocByMd5(copiaMd5);

        currentCompareTab = 'media';
        updateCompareTabsVisual();
        renderCompareContent();

        if (spinner) spinner.classList.add('hidden');
        if (content) content.classList.remove('hidden');
      } catch (err) {
        if (spinner) spinner.classList.add('hidden');
        if (content) {
          content.classList.remove('hidden');
          content.innerHTML = `<div class="p-6 text-center text-rose-400 bg-rose-500/10 rounded-xl border border-rose-500/20">Erro ao carregar comparação: ${escapeHtml(err.message)}</div>`;
        }
      }
    }

    function closeCompareDuplicatesModal() {
      const modal = document.getElementById('modalCompareDuplicates');
      if (modal) modal.classList.add('hidden');
    }

    function switchCompareTab(tab) {
      currentCompareTab = tab;
      updateCompareTabsVisual();
      renderCompareContent();
    }

    function updateCompareTabsVisual() {
      const tabs = [
        { id: 'btnCompareTabMedia', key: 'media' },
        { id: 'btnCompareTabText', key: 'text' },
        { id: 'btnCompareTabMeta', key: 'meta' }
      ];
      tabs.forEach(t => {
        const btn = document.getElementById(t.id);
        if (!btn) return;
        if (t.key === currentCompareTab) {
          btn.className = 'px-3 py-1 rounded-md font-semibold text-xs transition bg-indigo-600 text-white shadow-sm flex items-center gap-1.5';
        } else {
          btn.className = 'px-3 py-1 rounded-md font-semibold text-xs transition text-slate-400 hover:text-slate-200 flex items-center gap-1.5';
        }
      });
    }

    function renderCompareContent() {
      const container = document.getElementById('compareContentArea');
      if (!container || !currentCompareData) return;

      const docA = currentCompareData.doc_a || {};
      const docB = currentCompareData.doc_b || {};

      if (currentCompareTab === 'media') {
        const fmtA = getDocFormatMeta(docA);
        const fmtB = getDocFormatMeta(docB);

        const isPdfA = fmtA.type === 'pdf';
        const isImgA = fmtA.type === 'image';
        const isPdfB = fmtB.type === 'pdf';
        const isImgB = fmtB.type === 'image';

        container.innerHTML = `
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 h-full overflow-hidden">
            <!-- Coluna 1: Documento Base -->
            <div class="flex flex-col h-full bg-slate-900 rounded-xl border border-slate-800 overflow-hidden shadow-sm">
              <div class="px-3.5 py-2.5 bg-slate-950 border-b border-slate-800 flex items-center justify-between shrink-0">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold text-[10px] border border-emerald-500/30 shrink-0">
                    BASE (ORIGINAL)
                  </span>
                  <span class="font-mono text-slate-200 text-xs truncate font-medium" title="${escapeHtml(docA.nome_arquivo || docA.md5)}">${escapeHtml(docA.nome_arquivo || docA.md5)}</span>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                  <button type="button" onclick="navigateToDocByMd5('${docA.md5}')" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-emerald-300 rounded text-[11px] flex items-center gap-1" title="Carregar no visualizador principal">
                    <i class="fa-solid fa-eye text-[10px]"></i> Visualizador
                  </button>
                  <a href="/api/arquivo/${docA.md5}" target="_blank" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-[11px] flex items-center gap-1" title="Abrir arquivo em nova aba">
                    <i class="fa-solid fa-up-right-from-square text-[10px]"></i> Nova Aba
                  </a>
                </div>
              </div>
              
              <!-- Tira de atributos rápidos -->
              <div class="px-3 py-1.5 bg-slate-950/60 border-b border-slate-800/80 grid grid-cols-4 gap-2 text-[11px] shrink-0 font-mono text-slate-300">
                <div class="truncate"><span class="text-slate-500 block text-[9px] uppercase font-sans">Classe</span>${escapeHtml(docA.tipo_documento || '-')}</div>
                <div class="truncate"><span class="text-slate-500 block text-[9px] uppercase font-sans">Valor</span><span class="text-emerald-400 font-semibold">${escapeHtml(docA.valor_monetario || '-')}</span></div>
                <div class="truncate"><span class="text-slate-500 block text-[9px] uppercase font-sans">CPF / CNPJ</span>${escapeHtml(docA.cpf || docA.cnpj || '-')}</div>
                <div class="truncate"><span class="text-slate-500 block text-[9px] uppercase font-sans">Data</span>${escapeHtml(docA.data || '-')}</div>
              </div>

              <!-- Mídia Viewer -->
              <div class="flex-1 bg-slate-950 p-1 relative overflow-hidden flex items-center justify-center">
                ${isPdfA ? `
                  <iframe src="/api/arquivo/${docA.md5}#toolbar=0" class="w-full h-full border-0 rounded bg-slate-900"></iframe>
                ` : isImgA ? `
                  <div class="w-full h-full overflow-auto flex items-center justify-center p-2">
                    <img src="/api/arquivo/${docA.md5}" class="max-h-full max-w-full object-contain rounded shadow">
                  </div>
                ` : `
                  <div class="text-center p-6 space-y-2">
                    <i class="fa-solid fa-file-word text-4xl text-sky-400"></i>
                    <p class="text-slate-300 text-xs">Arquivo Word / editável original (${escapeHtml(fmtA.label)})</p>
                    <a href="/api/arquivo/${docA.md5}" download class="inline-block px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded text-xs font-semibold">Baixar Arquivo</a>
                  </div>
                `}
              </div>
            </div>

            <!-- Coluna 2: Cópia Duplicada -->
            <div class="flex flex-col h-full bg-slate-900 rounded-xl border border-rose-900/40 overflow-hidden shadow-sm">
              <div class="px-3.5 py-2.5 bg-slate-950 border-b border-rose-900/30 flex items-center justify-between shrink-0">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold text-[10px] border border-rose-500/30 shrink-0">
                    CÓPIA SUSPEITA
                  </span>
                  <span class="font-mono text-slate-200 text-xs truncate font-medium" title="${escapeHtml(docB.nome_arquivo || docB.md5)}">${escapeHtml(docB.nome_arquivo || docB.md5)}</span>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                  <button type="button" onclick="navigateToDocByMd5('${docB.md5}')" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-rose-300 rounded text-[11px] flex items-center gap-1" title="Carregar no visualizador principal">
                    <i class="fa-solid fa-eye text-[10px]"></i> Visualizador
                  </button>
                  <a href="/api/arquivo/${docB.md5}" target="_blank" class="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-[11px] flex items-center gap-1" title="Abrir arquivo em nova aba">
                    <i class="fa-solid fa-up-right-from-square text-[10px]"></i> Nova Aba
                  </a>
                </div>
              </div>

              <!-- Tira de atributos rápidos -->
              <div class="px-3 py-1.5 bg-slate-950/60 border-b border-slate-800/80 grid grid-cols-4 gap-2 text-[11px] shrink-0 font-mono text-slate-300">
                <div class="truncate"><span class="text-slate-500 block text-[9px] uppercase font-sans">Classe</span>${escapeHtml(docB.tipo_documento || '-')}</div>
                <div class="truncate"><span class="text-slate-500 block text-[9px] uppercase font-sans">Valor</span><span class="text-rose-400 font-semibold">${escapeHtml(docB.valor_monetario || '-')}</span></div>
                <div class="truncate"><span class="text-slate-500 block text-[9px] uppercase font-sans">CPF / CNPJ</span>${escapeHtml(docB.cpf || docB.cnpj || '-')}</div>
                <div class="truncate"><span class="text-slate-500 block text-[9px] uppercase font-sans">Data</span>${escapeHtml(docB.data || '-')}</div>
              </div>

              <!-- Mídia Viewer -->
              <div class="flex-1 bg-slate-950 p-1 relative overflow-hidden flex items-center justify-center">
                ${isPdfB ? `
                  <iframe src="/api/arquivo/${docB.md5}#toolbar=0" class="w-full h-full border-0 rounded bg-slate-900"></iframe>
                ` : isImgB ? `
                  <div class="w-full h-full overflow-auto flex items-center justify-center p-2">
                    <img src="/api/arquivo/${docB.md5}" class="max-h-full max-w-full object-contain rounded shadow">
                  </div>
                ` : `
                  <div class="text-center p-6 space-y-2">
                    <i class="fa-solid fa-file-word text-4xl text-sky-400"></i>
                    <p class="text-slate-300 text-xs">Arquivo Word / editável original (${escapeHtml(fmtB.label)})</p>
                    <a href="/api/arquivo/${docB.md5}" download class="inline-block px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded text-xs font-semibold">Baixar Arquivo</a>
                  </div>
                `}
              </div>
            </div>
          </div>
        `;
      } else if (currentCompareTab === 'text') {
        const textA = currentCompareData.texto_a || '';
        const textB = currentCompareData.texto_b || '';

        container.innerHTML = `
          <div class="flex flex-col h-full space-y-2.5">
            <div class="flex items-center justify-between px-3 py-2 bg-slate-900 rounded-lg border border-slate-800 text-xs text-slate-300 shrink-0">
              <div class="flex items-center gap-2">
                <i class="fa-solid fa-align-left text-indigo-400"></i>
                <span class="font-bold text-slate-200">Comparação Paralela de Transcrição & OCR:</span>
                <span class="text-slate-400 text-[11px]">Base: ${textA.length} caracteres • Cópia: ${textB.length} caracteres</span>
              </div>
              <div class="font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 text-[11px]">
                Similaridade de Texto: ${currentCompareData.similaridade_pct}%
              </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 overflow-hidden">
              <!-- Texto Doc A -->
              <div class="flex flex-col h-full bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
                <div class="px-3 py-2 bg-slate-950 border-b border-slate-800 flex items-center justify-between text-xs font-semibold text-emerald-400 shrink-0">
                  <span>Documento Base: ${escapeHtml(docA.nome_arquivo || docA.md5)}</span>
                  <button type="button" onclick="navigator.clipboard.writeText(currentCompareData.texto_a); showToast('Texto do Doc Base copiado!', 'success');" class="text-slate-400 hover:text-white text-[11px] flex items-center gap-1 font-normal">
                    <i class="fa-regular fa-copy"></i> Copiar Texto
                  </button>
                </div>
                <div class="flex-1 p-3 overflow-y-auto font-mono text-[11px] leading-relaxed text-slate-300 bg-slate-950/70 select-all whitespace-pre-wrap">
${escapeHtml(textA || '(Nenhum texto extraído para este documento)')}
                </div>
              </div>

              <!-- Texto Doc B -->
              <div class="flex flex-col h-full bg-slate-900 rounded-xl border border-rose-900/40 overflow-hidden">
                <div class="px-3 py-2 bg-slate-950 border-b border-rose-900/30 flex items-center justify-between text-xs font-semibold text-rose-400 shrink-0">
                  <span>Cópia Duplicada: ${escapeHtml(docB.nome_arquivo || docB.md5)}</span>
                  <button type="button" onclick="navigator.clipboard.writeText(currentCompareData.texto_b); showToast('Texto da Cópia copiado!', 'success');" class="text-slate-400 hover:text-white text-[11px] flex items-center gap-1 font-normal">
                    <i class="fa-regular fa-copy"></i> Copiar Texto
                  </button>
                </div>
                <div class="flex-1 p-3 overflow-y-auto font-mono text-[11px] leading-relaxed text-slate-300 bg-slate-950/70 select-all whitespace-pre-wrap">
${escapeHtml(textB || '(Nenhum texto extraído para este documento)')}
                </div>
              </div>
            </div>
          </div>
        `;
      } else if (currentCompareTab === 'meta') {
        const fields = [
          { label: 'Identificador MD5', valA: docA.md5, valB: docB.md5, mono: true },
          { label: 'Nome do Arquivo', valA: docA.nome_arquivo, valB: docB.nome_arquivo },
          { label: 'Classe / Tipo', valA: docA.tipo_documento, valB: docB.tipo_documento },
          { label: 'Domínio', valA: docA.dominio, valB: docB.dominio },
          { label: 'Beneficiário', valA: docA.beneficiario, valB: docB.beneficiario },
          { label: 'CPF', valA: docA.cpf, valB: docB.cpf, mono: true },
          { label: 'CNPJ', valA: docA.cnpj, valB: docB.cnpj, mono: true },
          { label: 'Valor Monetário', valA: docA.valor_monetario, valB: docB.valor_monetario, mono: true },
          { label: 'Data do Documento', valA: docA.data, valB: docB.data, mono: true },
          { label: 'Formato / Extensão', valA: docA.extensao, valB: docB.extensao, mono: true },
          { label: 'Método de Leitura', valA: docA.metodo_leitura, valB: docB.metodo_leitura },
          { label: 'Status de Conferência', valA: docA.status_conferencia, valB: docB.status_conferencia }
        ];

        let rowsHtml = '';
        fields.forEach(f => {
          const vA = safeString(f.valA) || '-';
          const vB = safeString(f.valB) || '-';
          const isMatch = (vA !== '-' && vB !== '-' && vA.toLowerCase() === vB.toLowerCase());
          const isDiff = (vA !== '-' && vB !== '-' && vA.toLowerCase() !== vB.toLowerCase());

          let statusBadge = '<span class="text-slate-500">-</span>';
          if (isMatch) {
            statusBadge = '<span class="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-semibold text-[10px] border border-emerald-500/30">Idêntico</span>';
          } else if (isDiff) {
            statusBadge = '<span class="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 font-semibold text-[10px] border border-amber-500/30">Divergente</span>';
          }

          rowsHtml += `
            <tr class="border-b border-slate-800/80 hover:bg-slate-900/40 transition">
              <td class="px-4 py-2.5 font-medium text-slate-300 text-xs">${escapeHtml(f.label)}</td>
              <td class="px-4 py-2.5 text-slate-200 text-xs ${f.mono ? 'font-mono select-all' : ''}">${escapeHtml(vA)}</td>
              <td class="px-4 py-2.5 text-slate-200 text-xs ${f.mono ? 'font-mono select-all' : ''}">${escapeHtml(vB)}</td>
              <td class="px-4 py-2.5 text-center">${statusBadge}</td>
            </tr>
          `;
        });

        container.innerHTML = `
          <div class="h-full overflow-y-auto bg-slate-900 rounded-xl border border-slate-800 shadow-sm">
            <table class="w-full text-left border-collapse">
              <thead class="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider sticky top-0 border-b border-slate-800">
                <tr>
                  <th class="px-4 py-3">Atributo</th>
                  <th class="px-4 py-3 text-emerald-400">Documento Base</th>
                  <th class="px-4 py-3 text-rose-400">Cópia Duplicada</th>
                  <th class="px-4 py-3 text-center">Correspondência</th>
                </tr>
              </thead>
              <tbody>
                ${rowsHtml}
              </tbody>
            </table>
          </div>
        `;
      }
    }

    function navigateToDocByMd5(md5) {
      if (!allDocs || allDocs.length === 0 || !md5) return;
      const targetMd5 = md5.trim().toLowerCase();
      let idx = filteredDocs.findIndex(d => (d.md5 || '').toLowerCase() === targetMd5);
      if (idx === -1) {
        // Se não encontrou no filtro atual, reseta os filtros e tenta novamente
        resetAllFilters();
        idx = filteredDocs.findIndex(d => (d.md5 || '').toLowerCase() === targetMd5);
      }
      if (idx !== -1) {
        closeCompareDuplicatesModal();
        closeDuplicatesModal();
        selectDocument(idx);
        showToast('Documento carregado no visualizador principal.', 'info');
      } else {
        showToast('Documento não encontrado no acervo.', 'warning');
      }
    }

    async function resolveDuplicateAction(md5, descartar, fromCompareModal = false) {
      try {
        const resp = await fetch('/api/duplicatas/resolver', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ md5, descartar })
        });
        const data = await resp.json();
        if (data.status === 'sucesso') {
          showToast(descartar ? 'Falso positivo descartado. Documento mantido normal.' : 'Duplicata confirmada com sucesso pelo conferente!', 'success');
          if (fromCompareModal) {
            closeCompareDuplicatesModal();
          }
          await loadDocuments();
          loadDuplicatesData();
        }
      } catch (e) {
        alert(`Erro: ${e.message}`);
      }
    }

    // 4. Smart Dispatcher (Organização Física de Pastas)
    function openDispatcherModal() {
      const modal = document.getElementById('modalDispatcher');
      if (!modal) return;
      modal.classList.remove('hidden');
      const resBox = document.getElementById('dispatcherResultBox');
      if (resBox) resBox.classList.add('hidden');
    }

    function closeDispatcherModal() {
      const modal = document.getElementById('modalDispatcher');
      if (modal) modal.classList.add('hidden');
    }

    async function runDispatcher(dryRun) {
      const outDirInput = document.getElementById('dispatcherOutputDir');
      const outDir = (outDirInput ? outDirInput.value : '').trim();
      const modeRadio = document.querySelector('input[name="dispatcherMode"]:checked');
      const mode = modeRadio ? modeRadio.value : 'copy';

      const btnSim = document.getElementById('btnDispatcherSimulate');
      const btnExec = document.getElementById('btnDispatcherExecute');
      const resBox = document.getElementById('dispatcherResultBox');

      if (!dryRun && mode === 'move') {
        if (!confirm("⚠️ ATENÇÃO: O modo 'Mover' irá transferir os arquivos originais de lugar. Deseja realmente prosseguir?")) {
          return;
        }
      }

      if (btnSim) btnSim.disabled = true;
      if (btnExec) btnExec.disabled = true;
      resBox.classList.remove('hidden');
      resBox.innerHTML = `<div class="p-3 bg-slate-950 rounded border border-slate-800 text-center text-slate-400 font-mono text-xs"><i class="fa-solid fa-spinner fa-spin text-amber-400 mr-2"></i>${dryRun ? 'Simulando plano de organização...' : 'Executando organização e gerando manifesto...'}</div>`;

      try {
        const resp = await fetch('/api/organizar_arquivos', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            output_dir: outDir,
            mode: mode,
            dry_run: dryRun
          })
        });
        const data = await resp.json();

        if (dryRun) {
          const itemsSample = (data.itens || []).slice(0, 5).map(it => `
            <div class="py-1 border-b border-slate-800/50 flex flex-col font-mono text-[10.5px]">
              <span class="text-slate-400 truncate">Origem: ${it.origem_nome}</span>
              <span class="text-emerald-400 truncate">➔ Destino: ${it.destino_nome}</span>
            </div>
          `).join('');

          resBox.innerHTML = `
            <div class="p-3.5 bg-amber-500/10 border border-amber-500/30 rounded-lg space-y-2 text-xs">
              <div class="font-semibold text-amber-300 flex items-center gap-1.5">
                <i class="fa-solid fa-circle-info text-amber-400"></i> Simulação Concluída com Sucesso!
              </div>
              <p class="text-slate-300 text-[11px]">
                Serão organizados <strong>${data.total_planejado}</strong> arquivos no diretório <code>${data.diretorio_destino}</code>.
              </p>
              <div class="bg-slate-950 p-2 rounded border border-slate-800 max-h-36 overflow-y-auto">
                ${itemsSample}
              </div>
            </div>
          `;
        } else {
          resBox.innerHTML = `
            <div class="p-3.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg space-y-2 text-xs">
              <div class="font-semibold text-emerald-300 flex items-center gap-1.5">
                <i class="fa-solid fa-circle-check text-emerald-400"></i> Arquivos Organizados com Sucesso!
              </div>
              <p class="text-slate-300 text-[11px]">
                Total de <strong>${data.total_organizados}</strong> arquivos copiados/movidos com integridade referencial.
              </p>
              <p class="text-slate-400 text-[10px] font-mono">
                Manifesto salvo em: <strong>${data.manifesto_csv}</strong>
              </p>
            </div>
          `;
          showToast(`Organização concluída: ${data.total_organizados} arquivos padronizados!`, 'success');
        }
      } catch (e) {
        resBox.innerHTML = `<div class="p-3 bg-rose-500/10 border border-rose-500/20 rounded text-rose-300 text-xs">Falha na organização: ${e.message}</div>`;
      } finally {
        if (btnSim) btnSim.disabled = false;
        if (btnExec) btnExec.disabled = false;
      }
    }
