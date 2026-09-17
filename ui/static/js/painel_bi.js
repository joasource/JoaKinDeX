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

