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
