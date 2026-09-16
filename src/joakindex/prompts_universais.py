#!/usr/bin/env python3
"""
JoaKinDeX - Prompts Universais de Extração e Gatilho de Fallback Híbrido
Criado por: Joaquim Ferreira Silva Neto <joaquimfsneto@gmail.com>

Construtores dos prompts universais de extração estruturada (texto e visão
multimodal/OCR) usados na classificação de documentos, e a função
`should_trigger_hybrid_fallback`, que decide se um documento classificado
localmente deve ser promovido para reclassificação na nuvem (modo cascata
híbrido).
"""

__project__ = "JoaKinDeX"
__author__ = "Joaquim Ferreira Silva Neto"
__email__ = "joaquimfsneto@gmail.com"
__version__ = "1.0.0"

from typing import Any, Dict, Tuple


# ---------------------------------------------------------------------------
# Prompts Universais de Extração (Texto e Visão / OCR Multimodal)
# ---------------------------------------------------------------------------
def build_universal_vision_prompt(extra_context: str = "") -> str:
    ctx_note = ""
    if extra_context:
        ctx_note = f"""
OBSERVAÇÃO DA LEITURA TEXTUAL PRÉVIA:
\"\"\"
{extra_context[:1200]}
\"\"\"
Atenção: Analise com precisão os elementos visuais das páginas (títulos, logotipos de faculdades ou bancos, cabeçalhos, comprovantes PIX, tabelas, selos, carimbos, assinaturas e formatação) para classificar o domínio e tipo de documento.
"""

    return f"""Você é um especialista em OCR multimodal e classificação de documentos oficiais brasileiros.
Analise visualmente as imagens deste documento (que pode ser acadêmico, comprovante financeiro/PIX, identificação civil, jurídico ou outro) e extraia todas as entidades estruturadas.
{ctx_note}
Extraia as seguintes informações e retorne ESTRITAMENTE um objeto JSON com as chaves exatas abaixo:

1. DOMÍNIO E CLASSIFICAÇÃO:
- "dominio": Classifique em uma das seguintes opções estritas:
    * "academico" (para diplomas, certificados de cursos, históricos escolares, declarações de matrícula/conclusão, carteiras de estudante)
    * "financeiro" (para comprovantes PIX, recibos de pagamento, transferências bancárias, boletos, extratos, notas fiscais)
    * "identificacao" (para RG, CNH, CPF, Título de Eleitor, Certidão de Nascimento/Casamento, Passaporte, Registro Profissional)
    * "profissional" (para Cartão CNPJ, Comprovante de Inscrição e Situação Cadastral, currículos, carteira de trabalho, atestados de capacidade)
    * "veicular" (para Certificado de Registro de Veículo - CRV, Certificado de Registro e Licenciamento de Veículo - CRLV, Autorização para Transferência de Propriedade - ATPV, laudos de vistoria veicular, guias de remoção/pátio, comunicação de venda ao DETRAN, notas de arrematação de veículos)
    * "juridico" (para contratos, procurações, termos de posse, certidões judiciais, mandados de busca e apreensão, escrituras, petições)
    * "outro" (para quaisquer outros documentos não contemplados acima)
- "tipo_documento": Nome específico do documento. Exemplos com critérios estritos:
    * "Certificado de Registro de Veículo (CRV)" (ATENÇÃO: documento de propriedade e transferência de veículo, antigo DUT, frente e verso físico ou versão digital unificada. NUNCA confunda com CRLV e NUNCA classifique como Contrato de Compra e Venda)
    * "Certificado de Registro e Licenciamento de Veículo (CRLV)" (ATENÇÃO: documento anual de porte obrigatório para circulação do veículo, com exercício/ano e QR Code, físico ou digital unificado. NUNCA confunda com CRV e NUNCA classifique como Contrato de Compra e Venda)
    * "Autorização para Transferência de Propriedade de Veículo (ATPV)" (ATENÇÃO: autorização de transferência de veículo física ou digital/ATPV-e com comprador, vendedor e valor da venda. NUNCA classifique como Contrato de Compra e Venda)
    * "Comunicação de Venda ao DETRAN", "Laudo de Vistoria Veicular", "Guia de Remoção de Veículo", "Nota de Arrematação (Leilão)", "Comprovante de Agendamento DETRAN"
    * "Recibo de Entrega da Declaração de Ajuste Anual" / "Declaração de Imposto de Renda" (ATENÇÃO: classifique no domínio financeiro se o documento for declaração de IRPF ou recibo de entrega da Receita Federal, contendo expressões como "Imposto sobre a Renda - Pessoa Física", "Declaração de Ajuste Anual", "Recibo de Entrega", número do recibo, exercício/ano-calendário)
    * "Informe de Rendimentos Financeiros" (ATENÇÃO: classifique no domínio financeiro se o documento for um informe de rendimentos financeiros emitido por banco/instituição financeira ou comprovante de rendimentos para fins de IRPF)
    * "Talão de Cheques" / "Folha de Cheque" (ATENÇÃO: classifique como Folha de Cheque ou Talão de Cheques se o documento for uma folha ou talonário de cheque bancário, contendo expressões como "Pague por este cheque", "a quantia de", "à sua ordem", "centavos acima", número do cheque com 6 dígitos, série, agência, conta corrente ou canhotos de talão)
    * "Boleto Bancário" (ATENÇÃO: classifique categoricamente como Boleto Bancário se o documento contiver linha digitável com 47 ou 48 dígitos, código de barras FEBRABAN com 44 dígitos, termos como "ficha de compensação", "recibo do pagador/sacado", "nosso número", "pagável em qualquer banco", ou se for conta/fatura de concessionária de energia/água/serviços públicos com código de cobrança)
    * "Listagem de Pagamentos / Depósitos" (para borderôs, listagens de depósitos bancários, relações de pagamentos com tabelas ou múltiplos favorecidos)
    * "Comprovante PIX" (ATENÇÃO: classifique como PIX ESTRITAMENTE se o documento contiver expressamente o termo "PIX" ou identificador E2E padrão BACEN iniciado por 'E')
    * "Comprovante de Transferência Bancária (TED/DOC)" (para transferências bancárias entre contas sem indicação de PIX)
    * "DARF / Guia de Arrecadação Federal" (para guias de receitas federais / tributos)
    * "Contrato de Compra e Venda" (ATENÇÃO: classifique no domínio jurídico apenas se o documento for contrato particular ou escritura de compromisso/promessa de compra e venda. NUNCA classifique CRV, CRLV ou ATPV como Contrato de Compra e Venda, mesmo que contenham vendedor, comprador e valor da venda)
    * "Nota Promissória" (ATENÇÃO: classifique no domínio financeiro se o documento for nota promissória / título de crédito comercial, contendo expressões como "Nota Promissória", "por esta única via", "pagarei/pagará por esta", "vencimento", "avalista", "emitente", padrão São Domingos cód. 6091)
    * "Recibo" / "Recibo de Pagamento" (ATENÇÃO: classifique no domínio financeiro para recibos de quitação ou comprovantes de recebimento de valores)
    * "Citação de Mandado de Busca e Apreensão" (para mandados judiciais e citações)
    * "Extrato Bancário", "Cartão CNPJ / Situação Cadastral", "Diploma", "Certificado", "Histórico Escolar", "RG / Identidade", "CNH", "Contrato de Prestação de Serviços", "Declaração", "Outro". Se não puder identificar, retorne "Não identificado".

2. CAMPOS UNIVERSAIS:
- "data": Data principal do documento ou data/hora da transação (ex: "18/12/2023", "08/09/2026 14:30:00" ou "18 de dezembro de 2023"). Se não encontrar, retorne null.
- "beneficiario": Nome do titular principal, favorecido, empresa ou emitente. Se não encontrar, retorne null.
- "cpf": CPF do titular ou recebedor identificado (ex: "000.000.000-00" ou apenas números). Se não houver menção, retorne null.
- "rg": Número da Cédula de Identidade / RG do titular incluindo órgão emissor/UF (ex: "12.345.678-9 SSP/SP"). Se não houver, retorne null.
- "cnpj": CNPJ da empresa, órgão ou pagador/recebedor formatado (ex: "00.000.000/0000-00") ou apenas números. Se não houver, retorne null.
- "valor_monetario": Se for comprovante financeiro, cheque ou PIX, informe o valor monetário com 'R$' (ex: "R$ 150,00" ou "R$ 1.250,50"). Para outros documentos, retorne null.

3. CAMPOS VEICULARES (se for documento do domínio veicular, senão retorne null):
- "placa": Placa do veículo identificada no documento (ex: "MQB-4382" ou "MQB4382").
- "renavam": Código Renavam do veículo com 9 a 11 dígitos (ex: "00833434136").
- "chassi": Número de Identificação do Veículo / Chassi VIN com 17 dígitos (ex: "9C2JC30104R079694").
- "marca_modelo": Marca, modelo e versão do veículo (ex: "HONDA/CG 125 TITAN KS").
- "ano_veiculo": Ano de fabricação e modelo (ex: "2003/2004").
- "orgao_transito": Órgão executivo de trânsito emissor (ex: "DETRAN-ES", "DETRAN-SP", "SENATRAN").
- "valor_venda": Valor da venda expresso na ATPV ou nota de arrematação se houver.

4. CAMPOS ACADÊMICOS (se aplicável):
- "curso": Nome oficial do curso concluído (ex: "Pós-graduação Lato Sensu em Gestão Escolar", "Bacharelado em Administração"). Se não for curso, retorne null.
- "natureza_curso": Nível acadêmico: "Graduação / Curso Superior", "Pós-Graduação Lato Sensu (Especialização/MBA)", "Pós-Graduação Stricto Sensu (Mestrado/Doutorado)", "Curso Técnico / Profissionalizante", "Curso de Extensão / Aperfeiçoamento", "Educação Básica" ou null.
- "carga_horaria": Carga horária total (ex: "750 h/aulas", "360 horas", "750h"). Se não houver, retorne null.
- "faculdade": Nome padronizado da faculdade, universidade ou instituição de ensino no formato "Nome Completo por Extenso (SIGLA)" (ex: "Universidade de São Paulo (USP)"). Se for comprovante bancário, cheque ou PIX, informe o nome da Instituição Financeira / Banco / PSP (ex: "SICOOB", "Banco do Brasil (BB)", "Caixa Econômica Federal (CEF)"). Se for Cartão CNPJ, informe "Receita Federal do Brasil (RFB)". Se não houver, retorne null.

4. CAMPOS ESPECÍFICOS DE BOLETO / CHEQUE / PIX / FINANCEIRO (preencha se for comprovante financeiro/boleto/cheque, senão retorne null):
- "numero_cheque": Número de 6 dígitos da folha de cheque (ex: "002366") se for cheque.
- "banco_cheque": Nome do banco emissor do cheque (ex: "SICOOB", "Banco do Brasil").
- "conta_corrente": Conta corrente bancária do emitente.
- "serie_cheque": Série da folha de cheque (ex: "001").
- "linha_digitavel": Linha digitável completa do boleto bancário (ex: "00190.00009 03183.378003 00078.500170 6 12780001804302" ou "836000000099 121500513001 180131922639 000227593344"). Se não houver, retorne null.
- "codigo_barras": Código de barras numérico contínuo do boleto (44 dígitos). Se não houver, retorne null.
- "nosso_numero": Nosso Número do boleto bancário (se presente).
- "pix_pagador_nome": Nome completo do pagador da transferência.
- "pix_pagador_cpf_cnpj": CPF ou CNPJ mascarado ou completo do pagador (ex: "***.123.456-**").
- "pix_pagador_banco": Banco / PSP de origem do pagador.
- "pix_recebedor_banco": Banco / PSP de destino do recebedor.
- "pix_chave": Chave PIX utilizada (e-mail, CPF/CNPJ, telefone ou chave EVP aleatória). Não confunda com número de conta ou agência!
- "pix_e2e_id": Identificador fim-a-fim da transação (ID E2E com 32 a 40 caracteres iniciado por 'E', ex: "E00416968202609081430s0123456789"). Não confunda com CPF ou conta!
- "pix_autenticacao": Código de autenticação bancária ou hash de controle de segurança.

5. CAMPOS CADASTRAIS / PESSOA JURÍDICA (preencha se for Cartão CNPJ / Comprovante de Situação Cadastral ou documento de empresa, senão retorne null):
- "razao_social": Nome empresarial oficial da entidade/empresa.
- "nome_fantasia": Título do estabelecimento / nome fantasia.
- "situacao_cadastral": Situação cadastral oficial (ex: "ATIVA", "BAIXADA", "SUSPENSA", "INAPTA", "NULA").
- "data_situacao": Data da situação cadastral (ex: "10/05/2021").
- "data_abertura": Data de fundação / início de atividade da empresa.
- "cnae_principal": Código e descrição da atividade econômica principal (CNAE).
- "natureza_juridica": Código e descrição da natureza jurídica.
- "endereco_completo": Endereço cadastral completo (logradouro, número, complemento, bairro, município, UF e CEP).
- "telefone": Telefone oficial informado no cadastro.
- "email": Endereço eletrônico / e-mail informado na Receita.

6. ESCRITA MANUAL / PREENCHIMENTO À MÃO (ATENÇÃO ESPECIAL):
- "manuscrito": true ou false. Defina OBRIGATORIAMENTE como true se o documento contiver escrita cursiva, manual ou se for um formulário/recibo preenchido com caneta/lápis (ex: recibos manuais de papelaria preenchidos à mão, notas promissórias, declarações de próprio punho, fichas com preenchimento manual). Caso contrário, retorne false.
- "emitente": Se for documento/recibo preenchido à mão, nome do emitente, pagador ou responsável que preencheu/assinou. Se não houver, retorne null.
- "referente_a": Finalidade, histórico ou justificativa manuscrita da operação (ex: "Serviços prestados de reforma", "Aluguel referente ao mês de janeiro"). Se não houver, retorne null.
- "conteudo_manuscrito": Transcrição fiel do conteúdo escrito à mão relevante (especialmente para declarações de próprio punho ou observações manuais). Se não houver, retorne null.

7. LEITURA E TRANSCRIÇÃO INTEGRAL (OCR COMPLETO):
- "texto_transcrito": Transcrição textual contínua e integral de TODO o conteúdo legível no documento (OCR completo de todas as páginas/imagens, incluindo parágrafos digitados, cabeçalhos, carimbos, tabelas e escrita manual). Transcreva com máxima fidelidade. Se o documento for ilegível ou sem texto visível, retorne null.

8. MÚLTIPLOS NOMES / TITULARES (LISTAGENS E RELAÇÕES):
- "nomes_detectados": Se o documento contiver uma relação, listagem, tabela de depósitos/pagamentos ou múltiplos titulares, favorecidos, alunos, clientes ou signatários, retorne um array de strings contendo TODOS os nomes completos identificados (ex: ["NOME 1", "NOME 2", ...]). Se houver apenas uma pessoa no documento, retorne [nome]. Se não houver nomes, retorne [].

REGRAS:
1. Responda APENAS o JSON válido. Sem explicações, sem comentários e sem formatação markdown fora do JSON.
2. ATENÇÃO A DOCUMENTOS PREENCHIDOS À MÃO: Leia atentamente caligrafia e números manuscritos com caneta, transcrevendo com máxima fidelidade valores, nomes, CPFs, datas e emitentes para os respectivos campos.
3. ATENÇÃO A LISTAGENS: Se for listagem ou tabela com vários nomes, extraia a lista completa em "nomes_detectados".
4. REGRA DO PIX: Não classifique como Comprovante PIX a menos que a palavra "PIX" esteja claramente presente.
5. REGRA DO BOLETO: Se o documento contiver linha digitável (47 ou 48 dígitos), código de barras (44 dígitos), ficha de compensação, recibo do sacado/pagador ou for fatura de energia/água com cobrança, classifique categoricamente como "Boleto Bancário" (domínio "financeiro") e NUNCA como PIX.
6. Não invente nenhuma informação. Se não estiver visível na imagem, preencha o valor como null.
"""


def build_universal_prompt(document_text: str) -> str:
    return f"""Você é um especialista em classificação de documentos oficiais brasileiros e extração estruturada de dados.
Analise o texto extraído deste documento (que pode ser acadêmico, comprovante financeiro/PIX, identificação, profissional/CNPJ, jurídico ou outro) e extraia todas as entidades estruturadas.

Texto extraído do documento:
\"\"\"
{document_text}
\"\"\"

Extraia as seguintes informações e retorne ESTRITAMENTE um objeto JSON com as chaves exatas abaixo:

1. DOMÍNIO E CLASSIFICAÇÃO:
- "dominio": Classifique em uma das seguintes opções estritas:
    * "academico" (para diplomas, certificados de cursos, históricos escolares, declarações de matrícula/conclusão, carteiras de estudante)
    * "financeiro" (para comprovantes PIX, recibos de pagamento, transferências bancárias, boletos, extratos, notas fiscais, listagens de depósito)
    * "identificacao" (para RG, CNH, CPF, Título de Eleitor, Certidão de Nascimento/Casamento, Passaporte, Registro Profissional)
    * "profissional" (para Cartão CNPJ, Comprovante de Inscrição e Situação Cadastral, currículos, carteira de trabalho, atestados de capacidade)
    * "veicular" (para Certificado de Registro de Veículo - CRV, Certificado de Registro e Licenciamento de Veículo - CRLV, Autorização para Transferência de Propriedade - ATPV, laudos de vistoria veicular, guias de remoção/pátio, comunicação de venda ao DETRAN, notas de arrematação de veículos)
    * "juridico" (para contratos, procurações, termos de posse, certidões judiciais, mandados de busca e apreensão, escrituras, petições)
    * "outro" (para quaisquer outros documentos não contemplados acima)
- "tipo_documento": Nome específico do documento. Exemplos com critérios estritos:
    * "Certificado de Registro de Veículo (CRV)" (ATENÇÃO: documento de propriedade e transferência de veículo, antigo DUT, frente e verso físico ou versão digital unificada. NUNCA confunda com CRLV e NUNCA classifique como Contrato de Compra e Venda)
    * "Certificado de Registro e Licenciamento de Veículo (CRLV)" (ATENÇÃO: documento anual de porte obrigatório para circulação do veículo, com exercício/ano e QR Code, físico ou digital unificado. NUNCA confunda com CRV e NUNCA classifique como Contrato de Compra e Venda)
    * "Autorização para Transferência de Propriedade de Veículo (ATPV)" (ATENÇÃO: autorização de transferência de veículo física ou digital/ATPV-e com comprador, vendedor e valor da venda. NUNCA classifique como Contrato de Compra e Venda)
    * "Comunicação de Venda ao DETRAN", "Laudo de Vistoria Veicular", "Guia de Remoção de Veículo", "Nota de Arrematação (Leilão)", "Comprovante de Agendamento DETRAN"
    * "Recibo de Entrega da Declaração de Ajuste Anual" / "Declaração de Imposto de Renda" (ATENÇÃO: classifique no domínio financeiro se o documento for declaração de IRPF ou recibo de entrega da Receita Federal, contendo expressões como "Imposto sobre a Renda - Pessoa Física", "Declaração de Ajuste Anual", "Recibo de Entrega", número do recibo, exercício/ano-calendário)
    * "Informe de Rendimentos Financeiros" (ATENÇÃO: classifique no domínio financeiro se o documento for um informe de rendimentos financeiros emitido por banco/instituição financeira ou comprovante de rendimentos para fins de IRPF)
    * "Talão de Cheques" / "Folha de Cheque" (ATENÇÃO: classifique como Folha de Cheque ou Talão de Cheques se o documento for uma folha ou talonário de cheque bancário, contendo expressões como "Pague por este cheque", "a quantia de", "à sua ordem", "centavos acima", número do cheque com 6 dígitos, série, agência, conta corrente ou canhotos de talão)
    * "Boleto Bancário" (ATENÇÃO: classifique categoricamente como Boleto Bancário se o documento contiver linha digitável com 47 ou 48 dígitos, código de barras FEBRABAN com 44 dígitos, termos como "ficha de compensação", "recibo do pagador/sacado", "nosso número", "pagável em qualquer banco", ou se for conta/fatura de concessionária de energia/água/serviços públicos com código de cobrança)
    * "Listagem de Pagamentos / Depósitos" (para borderôs, listagens de depósitos bancários, relações de pagamentos com tabelas ou múltiplos favorecidos)
    * "Comprovante PIX" (ATENÇÃO: classifique como PIX ESTRITAMENTE se o documento contiver expressamente o termo "PIX" ou identificador E2E padrão BACEN iniciado por 'E')
    * "Comprovante de Transferência Bancária (TED/DOC)" (para transferências bancárias entre contas sem indicação de PIX)
    * "DARF / Guia de Arrecadação Federal" (para guias DARF, arrecadação federal, impostos federais)
    * "Contrato de Compra e Venda" (ATENÇÃO: classifique no domínio jurídico apenas se o documento for contrato particular ou escritura de compromisso/promessa de compra e venda. NUNCA classifique CRV, CRLV ou ATPV como Contrato de Compra e Venda, mesmo que contenham vendedor, comprador e valor da venda)
    * "Nota Promissória" (ATENÇÃO: classifique no domínio financeiro se o documento for nota promissória / título de crédito comercial, contendo expressões como "Nota Promissória", "por esta única via", "pagarei/pagará por esta", "vencimento", "avalista", "emitente", padrão São Domingos cód. 6091)
    * "Recibo" / "Recibo de Pagamento" (ATENÇÃO: classifique no domínio financeiro para recibos de quitação ou comprovantes de recebimento de valores)
    * "Citação de Mandado de Busca e Apreensão" (para mandados judiciais e citações)
    * "Extrato Bancário", "Cartão CNPJ / Situação Cadastral", "Diploma", "Certificado", "Histórico Escolar", "RG / Identidade", "CNH", "Contrato de Prestação de Serviços", "Declaração", "Outro". Se não puder identificar, retorne "Não identificado".

2. CAMPOS UNIVERSAIS:
- "data": Data principal do documento ou data/hora da transação (ex: "18/12/2023", "08/09/2026 14:30:00" ou "18 de dezembro de 2023"). Se não encontrar, retorne null.
- "beneficiario": Nome do titular, aluno, favorecido do pagamento ou Razão Social da empresa. Se não encontrar, retorne null.
- "cpf": CPF do titular ou recebedor identificado (ex: "000.000.000-00" ou apenas números). Se não houver menção, retorne null.
- "rg": Número da Cédula de Identidade / RG do titular incluindo órgão emissor/UF (ex: "12.345.678-9 SSP/SP"). Se não houver, retorne null.
- "cnpj": CNPJ da empresa, órgão ou pagador/recebedor formatado (ex: "00.000.000/0000-00") ou apenas números. Se não houver, retorne null.
- "valor_monetario": Se for comprovante financeiro, cheque ou PIX, informe o valor monetário com 'R$' (ex: "R$ 150,00" ou "R$ 1.250,50"). Para outros documentos, retorne null.

3. CAMPOS VEICULARES (se for documento do domínio veicular, senão retorne null):
- "placa": Placa do veículo identificada no documento (ex: "MQB-4382" ou "MQB4382").
- "renavam": Código Renavam do veículo com 9 a 11 dígitos (ex: "00833434136").
- "chassi": Número de Identificação do Veículo / Chassi VIN com 17 dígitos (ex: "9C2JC30104R079694").
- "marca_modelo": Marca, modelo e versão do veículo (ex: "HONDA/CG 125 TITAN KS").
- "ano_veiculo": Ano de fabricação e modelo (ex: "2003/2004").
- "orgao_transito": Órgão executivo de trânsito emissor (ex: "DETRAN-ES", "DETRAN-SP", "SENATRAN").
- "valor_venda": Valor da venda expresso na ATPV ou nota de arrematação se houver.

4. CAMPOS ACADÊMICOS (se aplicável):
- "curso": Nome oficial do curso concluído (ex: "Pós-graduação Lato Sensu em Gestão Escolar", "Bacharelado em Administração"). Se não for curso, retorne null.
- "natureza_curso": Nível acadêmico: "Graduação / Curso Superior", "Pós-Graduação Lato Sensu (Especialização/MBA)", "Pós-Graduação Stricto Sensu (Mestrado/Doutorado)", "Curso Técnico / Profissionalizante", "Curso de Extensão / Aperfeiçoamento", "Educação Básica" ou null.
- "carga_horaria": Carga horária total (ex: "750 h/aulas", "360 horas", "750h"). Se não houver, retorne null.
- "faculdade": Nome padronizado da faculdade, universidade ou instituição de ensino no formato "Nome Completo por Extenso (SIGLA)" (ex: "Universidade de São Paulo (USP)"). Se for comprovante bancário, cheque ou PIX, informe o nome da Instituição Financeira / Banco / PSP (ex: "SICOOB", "Banco do Brasil (BB)", "Caixa Econômica Federal (CEF)"). Se for Cartão CNPJ, informe "Receita Federal do Brasil (RFB)". Se não houver, retorne null.

4. CAMPOS ESPECÍFICOS DE BOLETO / CHEQUE / PIX / FINANCEIRO (preencha se for documento financeiro/PIX/boleto/cheque, senão retorne null):
- "numero_cheque": Número de 6 dígitos da folha de cheque (ex: "002366") se for cheque.
- "banco_cheque": Nome do banco emissor do cheque (ex: "SICOOB", "Banco do Brasil").
- "conta_corrente": Conta corrente bancária do emitente.
- "serie_cheque": Série da folha de cheque (ex: "001").
- "linha_digitavel": Linha digitável completa do boleto bancário (ex: "00190.00009 03183.378003 00078.500170 6 12780001804302" ou "836000000099 121500513001 180131922639 000227593344"). Se não houver, retorne null.
- "codigo_barras": Código de barras numérico contínuo do boleto (44 dígitos). Se não houver, retorne null.
- "nosso_numero": Nosso Número do boleto bancário (se presente).
- "pix_pagador_nome": Nome completo do pagador da transferência.
- "pix_pagador_cpf_cnpj": CPF ou CNPJ mascarado ou completo do pagador (ex: "***.123.456-**").
- "pix_pagador_banco": Banco / PSP de origem do pagador.
- "pix_recebedor_banco": Banco / PSP de destino do recebedor.
- "pix_chave": Chave PIX utilizada (e-mail, CPF/CNPJ, telefone ou chave EVP aleatória). Não confunda com conta bancária!
- "pix_e2e_id": Identificador fim-a-fim da transação (ID E2E com 32 a 40 caracteres iniciado por 'E', ex: "E00416968202609081430s0123456789"). Não confunda com CPF ou conta!
- "pix_autenticacao": Código de autenticação bancária ou hash de controle de segurança.

5. CAMPOS CADASTRAIS / PESSOA JURÍDICA (preencha se for Cartão CNPJ / Comprovante de Situação Cadastral ou documento de empresa, senão retorne null):
- "razao_social": Nome empresarial oficial da entidade/empresa.
- "nome_fantasia": Título do estabelecimento / nome fantasia.
- "situacao_cadastral": Situação cadastral oficial (ex: "ATIVA", "BAIXADA", "SUSPENSA", "INAPTA", "NULA").
- "data_situacao": Data da situação cadastral (ex: "10/05/2021").
- "data_abertura": Data de fundação / início de atividade da empresa.
- "cnae_principal": Código e descrição da atividade econômica principal (CNAE).
- "natureza_juridica": Código e descrição da natureza jurídica.
- "endereco_completo": Endereço cadastral completo (logradouro, número, complemento, bairro, município, UF e CEP).
- "telefone": Telefone oficial informado no cadastro.
- "email": Endereço eletrônico / e-mail informado na Receita.

6. ESCRITA MANUAL / PREENCHIMENTO À MÃO:
- "manuscrito": true ou false. Defina como true se o texto indicar documento escrito ou preenchido à mão (ex: recibos preenchidos com caneta, notas promissórias, declarações de próprio punho). Caso contrário, retorne false.
- "emitente": Se for documento/recibo manual, nome do emitente ou pagador. Se não houver, retorne null.
- "referente_a": Finalidade ou justificativa da operação manuscrita. Se não houver, retorne null.
- "conteudo_manuscrito": Transcrição de trecho escrito à mão se identificado. Se não houver, retorne null.

7. LEITURA E TRANSCRIÇÃO INTEGRAL:
- "texto_transcrito": Se o documento necessitar de transcrição ou consolidação textual completa, retorne-a na íntegra. Caso contrário, retorne null.

8. MÚLTIPLOS NOMES / TITULARES (LISTAGENS E RELAÇÕES):
- "nomes_detectados": Se o documento contiver uma relação, listagem, tabela de depósitos/pagamentos ou múltiplos titulares, favorecidos, alunos, clientes ou signatários, retorne um array de strings contendo TODOS os nomes completos identificados (ex: ["NOME 1", "NOME 2", ...]). Se houver apenas uma pessoa no documento, retorne [nome]. Se não houver nomes, retorne [].

REGRAS:
1. Responda APENAS o JSON válido. Sem explicações, sem comentários e sem formatação markdown fora do JSON.
2. ATENÇÃO A DOCUMENTOS PREENCHIDOS À MÃO: Se o texto contiver dados preenchidos manualmente com caneta, transcreva com fidelidade valores, nomes e datas.
3. ATENÇÃO A LISTAGENS: Se for listagem ou tabela com vários nomes, extraia a lista completa em "nomes_detectados".
4. REGRA DO PIX: Não classifique como Comprovante PIX a menos que a palavra "PIX" esteja claramente presente.
5. REGRA DO BOLETO: Se o documento contiver linha digitável (47 ou 48 dígitos), código de barras (44 dígitos), ficha de compensação, recibo do sacado/pagador ou for fatura de energia/água com cobrança, classifique categoricamente como "Boleto Bancário" (domínio "financeiro") e NUNCA como PIX.
6. Não invente nenhuma informação. Se não estiver explícito no texto, preencha como null.
"""

# Aliases para retrocompatibilidade
build_vision_prompt = build_universal_vision_prompt
build_prompt = build_universal_prompt


def should_trigger_hybrid_fallback(doc: Dict[str, Any], text_length: int = 0) -> Tuple[bool, str]:
    """
    Avalia se um documento classificado localmente deve ser promovido para
    reclassificação na nuvem (OpenAI) no modo cascata híbrido.
    Retorna (deve_promover: bool, motivo: str).
    """
    if not doc:
        return True, "resultado_nulo"

    status = str(doc.get("status") or "").lower()
    if status == "erro":
        err_det = doc.get("motivo") or doc.get("erro") or "erro_leitura"
        return True, f"falha_leitura_local ({err_det})"

    tipo = str(doc.get("tipo_documento") or "").strip().upper()
    if not tipo or tipo in ["NÃO IDENTIFICADO", "NAO IDENTIFICADO", "OUTRO", "DESCONHECIDO", "DOCUMENTO NÃO IDENTIFICADO"]:
        return True, "tipo_documento_inconclusivo"

    dominio = str(doc.get("dominio") or "").strip().lower()

    # 1. Detecção de documento manuscrito / preenchido à mão com leitura local incompleta
    is_manuscrito = bool(
        doc.get("manuscrito")
        or any("manuscrito" in str(t).lower() or "mão" in str(t).lower() or "mao" in str(t).lower() for t in (doc.get("todos_tipos") or []))
        or "manuscrito" in tipo.lower() or "manual" in tipo.lower()
    )
    if is_manuscrito:
        tem_beneficiario = bool(str(doc.get("beneficiario") or "").strip())
        tem_valor = bool(str(doc.get("valor_monetario") or "").strip())
        tem_curso = bool(str(doc.get("curso") or "").strip())
        tem_emitente = bool(str(doc.get("emitente") or "").strip())
        if not tem_beneficiario and not tem_valor and not tem_curso and not tem_emitente:
            return True, "manuscrito_incompleto (caligrafia requer visão multimodal em nuvem)"

    if dominio == "academico" or any(k in tipo.lower() for k in ["diploma", "certificado", "histórico", "historico", "declaração", "declaracao"]):
        tem_beneficiario = bool(str(doc.get("beneficiario") or "").strip())
        tem_curso = bool(str(doc.get("curso") or "").strip())
        tem_faculdade = bool(str(doc.get("faculdade") or "").strip())
        if not tem_beneficiario:
            return True, "beneficiario_ausente (aluno/titular não identificado)"
        if not tem_curso and not tem_faculdade:
            return True, "dados_academicos_essenciais_ausentes (sem curso nem instituição)"

    elif dominio == "financeiro" or any(k in tipo.lower() for k in ["comprovante", "pagamento", "recibo", "nota fiscal", "extrato"]):
        tem_valor = bool(str(doc.get("valor_monetario") or "").strip())
        tem_beneficiario = bool(str(doc.get("beneficiario") or "").strip())
        if not tem_valor and not tem_beneficiario:
            return True, "dados_financeiros_essenciais_ausentes (sem valor nem beneficiário)"

    if text_length > 0 and text_length < 100:
        if dominio == "academico" and (not doc.get("beneficiario") or not doc.get("curso")):
            return True, "camada_textual_insuficiente"
        elif not doc.get("beneficiario") and not doc.get("valor_monetario"):
            return True, "camada_textual_insuficiente"

    return False, ""
