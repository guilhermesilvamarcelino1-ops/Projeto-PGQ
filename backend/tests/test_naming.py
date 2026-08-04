"""Nomenclatura do RQ 15.

Os casos abaixo são os exemplos do próprio documento de arquivamento da Persa — se
o código reproduz esses nomes exatamente, ele obedece à regra da empresa. Nome errado
significa documento que ninguém acha depois, que é o problema que o produto resolve.
"""

from datetime import date

from app.services.naming import (
    CamposDocumento,
    build_filename,
    build_storage_path,
    slug,
    slug_codigo,
    slug_documento,
    slug_pessoa,
)


def test_laudo_de_concreto_recuperado_por_data():
    """'Laudo de concreto, obra Vila Nova, NF 4471, laje 3º pav., 12/03/2026'"""
    nome = build_filename(
        nome_documento="Laudo de Concreto",
        campos=CamposDocumento(
            data=date(2026, 3, 12), obra="Vila Nova", complementos=["NF 4471", "laje 3º pav"]
        ),
        code=None,
        recovery_key="Data + nº da nota fiscal + local de aplicação",
    )
    # O RQ 15 grafa este complemento como LAJE-3PAV; aqui sai LAJE-3-PAV, mantendo a
    # regra de que hífen separa palavras. A chave de recuperação (data + NF) é idêntica.
    assert nome == "2026-03-12_LAUDO-CONCRETO_NF-4471_LAJE-3-PAV_VILA-NOVA"


def test_rnc_leva_codigo_e_obra_no_fim():
    """'Relatório de não conformidade da obra Vila Nova, 12/03/2026'"""
    nome = build_filename(
        nome_documento="RNC",
        campos=CamposDocumento(data=date(2026, 3, 12), obra="Vila Nova"),
        code="RQ 36",
        recovery_key="Data",
    )
    assert nome == "2026-03-12_RQ36_RNC_VILA-NOVA"


def test_alteracao_de_projeto_e_recuperada_pela_obra_e_leva_revisao():
    """'Alteração de projeto estrutural, obra Vila Nova, revisão 2'"""
    nome = build_filename(
        nome_documento="Alteração de Projeto",
        campos=CamposDocumento(obra="Vila Nova", complementos=["estrutural"], revisao=2),
        code="RQ 66",
        recovery_key="Nome do arquivo + nome da obra",
        has_revisions=True,
    )
    assert nome == "VILA-NOVA_RQ66_ALTERACAO-PROJETO_ESTRUTURAL_REV02"


def test_pesquisa_de_satisfacao_abre_pelo_cliente_em_sobrenome_nome():
    """'Pesquisa de satisfação, cliente Maria Souza, pós-chaves, 05/02/2026'"""
    nome = build_filename(
        nome_documento="Pesquisa satisfação chaves",
        campos=CamposDocumento(data=date(2026, 2, 5), pessoa="Maria Souza"),
        code="RQ 26",
        recovery_key="Nome do cliente, ordem alfabética",
    )
    assert nome == "SOUZA-MARIA_RQ26_PESQUISA-SATISFACAO-CHAVES_2026-02-05"


def test_ata_de_reuniao_sem_obra():
    """'Ata de reunião de análise crítica, 20/01/2026'"""
    nome = build_filename(
        nome_documento="Ata reunião",
        campos=CamposDocumento(data=date(2026, 1, 20), complementos=["análise crítica"]),
        code="RQ 24",
        recovery_key="Nome do arquivo",
    )
    assert nome == "2026-01-20_RQ24_ATA-REUNIAO_ANALISE-CRITICA"


def test_contrato_de_fornecedor_sem_codigo():
    """'Contrato de prestação de serviço, fornecedor Alfa, 10/03/2026'"""
    nome = build_filename(
        nome_documento="Contrato prest serviços",
        campos=CamposDocumento(data=date(2026, 3, 10), complementos=["Alfa"]),
        code=None,
        recovery_key="Data",
    )
    assert nome == "2026-03-10_CONTRATO-PREST-SERVICOS_ALFA"


def test_registro_de_evento_unico_nao_recebe_revisao():
    """Ata, laudo, ficha e termo não têm versão — REV neles seria ruído."""
    nome = build_filename(
        nome_documento="Ata reunião",
        campos=CamposDocumento(data=date(2026, 1, 20), revisao=3),
        code="RQ 24",
        recovery_key="Data",
        has_revisions=False,
    )
    assert "REV" not in nome


def test_revisao_sempre_com_dois_digitos():
    nome = build_filename(
        nome_documento="PQO",
        campos=CamposDocumento(obra="Vila Nova", revisao=1),
        recovery_key="Obra",
        has_revisions=True,
    )
    assert nome.endswith("_REV01")


def test_acentos_e_caracteres_proibidos_somem():
    """Barra, dois-pontos e afins quebram o caminho no Windows/SharePoint."""
    assert slug("Inspeção de serviços: laje/piso") == "INSPECAO-DE-SERVICOS-LAJE-PISO"
    assert slug("Análise Crítica da Direção") == "ANALISE-CRITICA-DA-DIRECAO"
    assert slug("laje 3º pavimento") == "LAJE-3-PAVIMENTO"  # ordinal não vira '3O'


def test_nome_do_documento_perde_conectivos_mas_obra_e_pessoa_nao():
    """O RQ 15 grafa 'Laudo de Concreto' como LAUDO-CONCRETO. Já em nome de obra
    ou pessoa, toda palavra identifica — não pode sumir."""
    assert slug_documento("Laudo de Concreto") == "LAUDO-CONCRETO"
    assert slug_documento("Alteração de Projeto") == "ALTERACAO-PROJETO"
    assert slug_documento("Controle de material fornecido pelo cliente") == (
        "CONTROLE-MATERIAL-FORNECIDO-PELO-CLIENTE"
    )
    assert slug("Residencial do Bosque") == "RESIDENCIAL-DO-BOSQUE"
    assert slug_pessoa("Maria de Souza") == "SOUZA-MARIA-DE"


def test_nome_de_pessoa_inverte_para_ordenar_por_sobrenome():
    assert slug_pessoa("Maria Souza") == "SOUZA-MARIA"
    assert slug_pessoa("João Carlos da Silva") == "SILVA-JOAO-CARLOS-DA"
    assert slug_pessoa("Cher") == "CHER"  # nome único não inverte


def test_codigo_perde_espaco_e_usa_o_primeiro_quando_composto():
    assert slug_codigo("RQ 36") == "RQ36"
    assert slug_codigo("RQ 00 / RQ 07") == "RQ00"
    assert slug_codigo("IS / FVS") == "IS"
    assert slug_codigo(None) == ""


def test_caminho_de_pasta_ganha_subpasta_da_obra():
    caminho = build_storage_path(storage_path="01. SGQ/11. Projetos", obra="Vila Nova")
    assert caminho == "01. SGQ/11. Projetos/Vila Nova"


def test_caminho_sem_obra_fica_na_pasta_da_taxonomia():
    assert build_storage_path(storage_path="01. SGQ/19. Medição de Indicadores") == (
        "01. SGQ/19. Medição de Indicadores"
    )
