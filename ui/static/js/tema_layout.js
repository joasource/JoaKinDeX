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
