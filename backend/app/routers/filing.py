"""Arquivamento em dois tempos: o sistema propõe, a pessoa confirma com um toque.

O engenheiro termina a concretagem, fotografa a rastreabilidade e envia. O sistema lê,
identifica, nomeia no padrão do RQ 15 e mostra onde vai guardar. Um toque e está
arquivado — sem abrir pasta, sem digitar nome, sem lembrar do procedimento.

A confirmação nunca é dispensada: um laudo arquivado como ata é um documento que
ninguém encontra no dia da auditoria.
"""

import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from app.auth import Principal, get_principal
from app.models import Document, DocumentType, PendingFiling
from app.services import filing as filing_service
from app.services.access import authorized_session, resolve_upload_families
from app.services.classification import classify_document, format_proposal

router = APIRouter(prefix="/filing", tags=["filing"])


@router.post("/propose")
async def propose(
    file: UploadFile = File(...),
    hint: str | None = Form(None),
    principal: Principal = Depends(get_principal),
):
    """Recebe o documento, classifica e devolve a proposta para confirmação."""
    conteudo = await file.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo vazio")

    async with authorized_session(principal) as (db, _familias):
        familias_upload = await resolve_upload_families(
            db, user_id=principal.user_id, is_admin=principal.is_admin
        )
        if not familias_upload:
            raise HTTPException(
                status_code=403, detail="Você não tem permissão para arquivar documentos"
            )

        proposta = await classify_document(
            db,
            company_id=principal.company_id,
            families=familias_upload,
            file_bytes=conteudo,
            content_type=file.content_type or "application/octet-stream",
            user_hint=hint,
        )

        if not proposta.mapeado:
            # Não guardamos nem propomos destino para documento fora da taxonomia:
            # inventar pasta é exatamente o que faria o documento se perder.
            return {
                "mapeado": False,
                "mensagem": format_proposal(proposta),
                "justificativa": proposta.justificativa,
            }

        staged = filing_service.stage_file(principal.company_id, file.filename or "documento", conteudo)
        pendente = PendingFiling(
            company_id=principal.company_id,
            family=proposta.tipo.family,
            document_type_id=proposta.tipo.id,
            created_by=principal.user_id,
            proposal={
                "nome_arquivo": proposta.nome_arquivo,
                "caminho": proposta.caminho,
                "confianca": proposta.confianca,
                "justificativa": proposta.justificativa,
                "data_validade": proposta.data_validade.isoformat() if proposta.data_validade else None,
                "exige_via_fisica": proposta.exige_via_fisica,
                "local_fisico": proposta.local_fisico,
                "campos": {**asdict(proposta.campos), "data": (
                    proposta.campos.data.isoformat() if proposta.campos.data else None
                )},
            },
            staged_path=staged,
            original_filename=file.filename,
            content_type=file.content_type,
        )
        db.add(pendente)
        await db.flush()

        resposta = {
            "mapeado": True,
            "pendencia_id": str(pendente.id),
            "mensagem": format_proposal(proposta),
            "tipo": proposta.tipo.name,
            "codigo": proposta.tipo.code,
            "nome_arquivo": proposta.nome_arquivo,
            "caminho": proposta.caminho,
            "confianca": proposta.confianca,
        }
    return resposta


@router.post("/{pendencia_id}/confirm")
async def confirm(pendencia_id: uuid.UUID, principal: Principal = Depends(get_principal)):
    """Confirmação de um toque: grava no destino e registra o documento no acervo."""
    async with authorized_session(principal) as (db, _familias):
        pendente = (
            await db.execute(select(PendingFiling).where(PendingFiling.id == pendencia_id))
        ).scalar_one_or_none()
        if pendente is None:
            raise HTTPException(status_code=404, detail="Pendência não encontrada")
        if pendente.status != "aguardando":
            raise HTTPException(status_code=409, detail=f"Pendência já {pendente.status}")

        origem = Path(pendente.staged_path)
        if not origem.exists():
            raise HTTPException(status_code=410, detail="Arquivo da pendência não está mais disponível")
        conteudo = origem.read_bytes()

        tipo = (
            await db.execute(select(DocumentType).where(DocumentType.id == pendente.document_type_id))
        ).scalar_one_or_none()
        if tipo is None:
            raise HTTPException(status_code=409, detail="Tipo de documento não está mais disponível")

        proposta = pendente.proposal
        salvo = await filing_service.arquivar(
            db,
            company_id=principal.company_id,
            caminho_pasta=proposta.get("caminho") or "",
            nome_arquivo=proposta["nome_arquivo"],
            conteudo=conteudo,
            content_type=pendente.content_type or "application/octet-stream",
        )

        documento = Document(
            company_id=principal.company_id,
            title=proposta["nome_arquivo"],
            category=tipo.name,
            kind="administrativo",
            family=tipo.family,
            document_type_id=tipo.id,
            file_path=salvo.file_path,
            source_type="onedrive" if salvo.onde == "onedrive" else "upload",
            external_id=salvo.external_id,
            external_url=salvo.external_url,
            uploaded_by=principal.user_id,
            status="active",
        )
        db.add(documento)
        await db.flush()

        pendente.status = "confirmado"
        pendente.resolved_at = datetime.now(timezone.utc)
        pendente.document_id = documento.id

        origem.unlink(missing_ok=True)

        mensagem = f"✅ Arquivado como {proposta['nome_arquivo']}"
        if proposta.get("caminho"):
            mensagem += f"\n📁 {salvo.caminho}"
        if proposta.get("exige_via_fisica") and proposta.get("local_fisico"):
            # A pendência da via em papel continua aberta: o sistema não guarda papel,
            # mas sabe onde ele deveria estar e vai cobrar.
            mensagem += f"\n\n📌 Não esqueça: a via original vai para {proposta['local_fisico']}"

        resposta = {"documento_id": str(documento.id), "onde": salvo.onde, "mensagem": mensagem}
    return resposta


@router.post("/{pendencia_id}/reject")
async def reject(pendencia_id: uuid.UUID, principal: Principal = Depends(get_principal)):
    """A pessoa disse que não é aquilo. Nada é arquivado, e a recusa fica registrada —
    é o sinal de onde a taxonomia ou a classificação precisa melhorar."""
    async with authorized_session(principal) as (db, _familias):
        pendente = (
            await db.execute(select(PendingFiling).where(PendingFiling.id == pendencia_id))
        ).scalar_one_or_none()
        if pendente is None:
            raise HTTPException(status_code=404, detail="Pendência não encontrada")

        pendente.status = "recusado"
        pendente.resolved_at = datetime.now(timezone.utc)
        Path(pendente.staged_path).unlink(missing_ok=True)

    return {
        "mensagem": (
            "Certo, não arquivei. Diga que documento é este e eu tento de novo, "
            "ou fale com o responsável pela qualidade."
        )
    }
