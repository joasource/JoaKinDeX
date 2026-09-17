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
