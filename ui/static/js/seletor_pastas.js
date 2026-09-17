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
