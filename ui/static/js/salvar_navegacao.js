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
