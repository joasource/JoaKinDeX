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
