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
