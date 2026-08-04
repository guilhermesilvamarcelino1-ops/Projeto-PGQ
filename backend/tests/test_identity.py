"""O número de telefone é o que identifica a pessoa — e, por consequência, a empresa
cujo acervo será consultado — quando a mensagem chega pelo número central do WhatsApp.
Se a normalização falhar, o funcionário não é reconhecido e não consegue usar o sistema.
"""

from app.services.identity import UNKNOWN_NUMBER_MESSAGE, normalize_phone


def test_whatsapp_and_cadastro_formats_match():
    """O WhatsApp entrega sem '+', o cadastro costuma ter máscara. Os dois precisam
    virar exatamente a mesma chave, senão o mesmo telefone não bate com ele mesmo."""
    do_whatsapp = normalize_phone("5511999990000")
    do_cadastro = normalize_phone("+55 (11) 99999-0000")
    assert do_whatsapp == do_cadastro == "+5511999990000"


def test_numero_brasileiro_sem_codigo_do_pais_assume_brasil():
    assert normalize_phone("(11) 99999-0000") == "+5511999990000"  # celular, 11 dígitos
    assert normalize_phone("11 3333-0000") == "+551133330000"  # fixo, 10 dígitos


def test_numero_internacional_e_preservado():
    # 12 dígitos: já tem código de país, não deve ganhar o 55 na frente.
    assert normalize_phone("+351 912 345 678") == "+351912345678"


def test_entradas_vazias_ou_invalidas_viram_none():
    assert normalize_phone(None) is None
    assert normalize_phone("") is None
    assert normalize_phone("sem números") is None


def test_mensagem_para_numero_desconhecido_nao_entrega_conteudo():
    """Número não cadastrado não pode receber nenhuma informação de procedimento:
    não sabemos de que empresa é a pessoa, nem se ela é funcionária."""
    assert "não reconheço este número" in UNKNOWN_NUMBER_MESSAGE.lower()
    assert "cadastr" in UNKNOWN_NUMBER_MESSAGE.lower()
