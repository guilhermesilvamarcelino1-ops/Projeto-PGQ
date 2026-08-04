"""Nomenclatura e caminho de arquivamento, conforme as regras do RQ 15.

O nome do arquivo começa pela CHAVE DE RECUPERAÇÃO definida na taxonomia, porque é
por ela que o documento vai ser procurado depois. Um laudo é procurado por data; a
pesquisa de satisfação, pelo nome do cliente; a alteração de projeto, pela obra.

Estas funções são deliberadamente puras: o modelo extrai os campos do documento, mas
quem monta o nome é código. Assim o padrão nunca varia com a redação do modelo, e o
resultado é testável contra os exemplos do próprio RQ 15.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

# Caracteres proibidos em nome de arquivo (Windows/SharePoint): / \ : * ? " < > |
_INVALIDOS = re.compile(r'[\\/:*?"<>|]')

# Conectivos saem do NOME DO DOCUMENTO: o RQ 15 nomeia "Laudo de Concreto" como
# LAUDO-CONCRETO e "Alteração de Projeto" como ALTERACAO-PROJETO. Não se aplicam a
# nome de obra ou de pessoa, onde toda palavra faz parte da identificação.
_CONECTIVOS = {"DE", "DA", "DO", "DAS", "DOS", "E", "EM", "NO", "NA", "NOS", "NAS", "COM", "PARA", "POR"}


def slug(texto: str | None) -> str:
    """MAIÚSCULAS sem acento, palavras unidas por hífen. O hífen separa palavras
    dentro de um bloco; o underline separa blocos."""
    if not texto:
        return ""
    # Indicador de ordinal sai antes da conversão, senão "3º" viraria "3O".
    limpo = texto.replace("º", "").replace("ª", "").replace("°", "")
    sem_acento = unicodedata.normalize("NFKD", limpo).encode("ascii", "ignore").decode()
    sem_acento = _INVALIDOS.sub(" ", sem_acento)
    palavras = re.findall(r"[A-Za-z0-9]+", sem_acento)
    return "-".join(p.upper() for p in palavras)


def slug_documento(texto: str | None) -> str:
    """Como `slug`, mas sem os conectivos — é a forma usada para o nome do documento."""
    partes = [p for p in slug(texto).split("-") if p and p not in _CONECTIVOS]
    return "-".join(partes)


def slug_pessoa(nome_completo: str | None) -> str:
    """SOBRENOME-NOME, para o arquivo ordenar alfabeticamente pelo sobrenome —
    é assim que a pasta do cliente e a do funcionário são consultadas."""
    if not nome_completo:
        return ""
    partes = [p for p in re.findall(r"[^\s]+", nome_completo.strip()) if p]
    if len(partes) < 2:
        return slug(nome_completo)
    return slug(f"{partes[-1]} {' '.join(partes[:-1])}")


def slug_codigo(code: str | None) -> str:
    """'RQ 36' vira 'RQ36'. Código com barra ('RQ 00 / RQ 07') usa o primeiro."""
    if not code:
        return ""
    primeiro = code.split("/")[0]
    return re.sub(r"[^A-Za-z0-9]", "", primeiro).upper()


def _bloco_lider(recovery_key: str | None) -> str:
    """Qual informação abre o nome do arquivo, segundo a chave de recuperação.

    A ordem de verificação importa: 'Data + nº da nota fiscal' começa por data,
    enquanto 'Nome do arquivo + nome da obra' é recuperado pela obra.
    """
    chave = (recovery_key or "").strip().lower()
    if chave.startswith("data") or chave.startswith("ano"):
        return "data"
    if "cliente" in chave:
        return "pessoa"
    if "funcionário" in chave or "funcionario" in chave or "auditor" in chave:
        return "pessoa"
    if "obra" in chave or "empreendimento" in chave:
        return "obra"
    # Sem indicação clara, a data ordena melhor na pasta.
    return "data"


@dataclass
class CamposDocumento:
    """O que o classificador extrai do documento para compor o nome."""

    data: date | None = None
    obra: str | None = None
    pessoa: str | None = None  # cliente ou funcionário
    complementos: list[str] = field(default_factory=list)  # ex.: NF 4471, laje 3º pav.
    revisao: int | None = None


def build_filename(
    *,
    nome_documento: str,
    campos: CamposDocumento,
    code: str | None = None,
    recovery_key: str | None = None,
    has_revisions: bool = False,
) -> str:
    """Monta o nome no padrão CHAVE_CODIGO_NOME_COMPLEMENTOS_REV.

    Registro de evento único (ata, laudo, ficha, termo) não leva revisão; só documento
    versionado (projeto, procedimento, plano, planilha de controle) recebe REV.
    """
    lider = _bloco_lider(recovery_key)
    data_txt = campos.data.isoformat() if campos.data else ""  # AAAA-MM-DD ordena certo
    obra_txt = slug(campos.obra)
    pessoa_txt = slug_pessoa(campos.pessoa)

    blocos: list[str] = []
    if lider == "data" and data_txt:
        blocos.append(data_txt)
    elif lider == "pessoa" and pessoa_txt:
        blocos.append(pessoa_txt)
    elif lider == "obra" and obra_txt:
        blocos.append(obra_txt)

    codigo = slug_codigo(code)
    if codigo:
        blocos.append(codigo)

    blocos.append(slug_documento(nome_documento))
    blocos.extend(slug(c) for c in campos.complementos if c)

    # O identificador que não abriu o nome vai para o fim, para não se perder.
    if lider == "data":
        if obra_txt:
            blocos.append(obra_txt)
    else:
        if data_txt:
            blocos.append(data_txt)

    if has_revisions:
        blocos.append(f"REV{(campos.revisao or 0):02d}")

    return "_".join(b for b in blocos if b)


def build_storage_path(*, storage_path: str | None, obra: str | None = None) -> str:
    """Caminho de pasta no drive da empresa. Documento ligado a uma obra ganha a
    subpasta dela, para o acervo não virar uma pasta única com tudo dentro.

    Devolve o caminho mesmo que ele ainda não exista — quem arquiva cria a árvore
    inteira, que é justamente o que evita o documento cair em lugar errado.
    """
    base = (storage_path or "").strip().strip("/")
    partes = [p.strip() for p in base.split("/") if p.strip()]
    if obra:
        partes.append(obra.strip())
    return "/".join(partes)
