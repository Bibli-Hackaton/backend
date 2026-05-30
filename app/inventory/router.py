from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uuid
from datetime import datetime
import io
import csv

from app.core.dependencies import get_db_session, get_current_user
from app.auth.models import User
from app.books.models import Book, BookEstado
from app.inventory.models import SessaoInventario, ItemInventario, InventarioEstado
from app.inventory.schemas import InventarioStartRequest, RegistroLeituraRequest, InventarioRelatorio, FuroInfo
from app.inventory.ws import admin_ws_manager

router = APIRouter(prefix="/inventario", tags=["inventario"])

@router.post("/iniciar", summary="Iniciar Sessão de Inventário", description="Inicia uma nova varredura de acervo. Impede que outra varredura paralela aconteça simultaneamente.")
async def iniciar_inventario(
    request: InventarioStartRequest, 
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    # Verifica se já existe um inventário em andamento
    query = select(SessaoInventario).where(SessaoInventario.estado == InventarioEstado.em_andamento)
    result = await db.execute(query)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Já existe um inventário em andamento.")

    nova_sessao = SessaoInventario(
        iniciado_por=request.iniciado_por,
        estado=InventarioEstado.em_andamento
    )
    db.add(nova_sessao)
    await db.commit()
    await db.refresh(nova_sessao)
    
    return {"status": "success", "sessao_id": str(nova_sessao.id)}

@router.post("/{sessao_id}/registrar-leitura", summary="Registrar Lote de Leituras", description="Recebe um array de tags RFID captadas pelo leitor móvel e registra na sessão atual.")
async def registrar_leitura(
    sessao_id: uuid.UUID,
    request: RegistroLeituraRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    query = select(SessaoInventario).where(SessaoInventario.id == sessao_id)
    sessao = (await db.execute(query)).scalar_one_or_none()
    
    if not sessao or sessao.estado != InventarioEstado.em_andamento:
        raise HTTPException(status_code=400, detail="Sessão de inventário inválida ou já finalizada.")
    
    itens_inseridos = 0
    for tag in request.rfid_tags:
        item = ItemInventario(
            sessao_id=sessao_id,
            rfid_tag=tag
        )
        db.add(item)
        itens_inseridos += 1
        
    await db.commit()
    return {"status": "success", "tags_registradas": itens_inseridos}

@router.post("/{sessao_id}/finalizar", response_model=InventarioRelatorio, summary="Finalizar e Calcular Furos", description="Encerra a sessão, cruza os livros lidos com o banco de dados e calcula os furos (livros desaparecidos). Dispara notificação WebSocket.")
async def finalizar_inventario(
    sessao_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    query_sessao = select(SessaoInventario).where(SessaoInventario.id == sessao_id)
    sessao = (await db.execute(query_sessao)).scalar_one_or_none()
    
    if not sessao or sessao.estado != InventarioEstado.em_andamento:
        raise HTTPException(status_code=400, detail="Sessão inválida.")
        
    sessao.estado = InventarioEstado.concluido
    sessao.finalizado_em = datetime.utcnow()
    
    # 1. Obter todos os livros do banco
    query_books = select(Book)
    books = (await db.execute(query_books)).scalars().all()
    
    # 2. Obter todas as tags lidas nesta sessão
    query_items = select(ItemInventario.rfid_tag).where(ItemInventario.sessao_id == sessao_id)
    tags_lidas = set((await db.execute(query_items)).scalars().all())
    
    total_cadastrado = len(books)
    total_lido = len(tags_lidas)
    presentes = 0
    emprestados = 0
    furos = []
    
    for book in books:
        if book.rfid_tag in tags_lidas:
            presentes += 1
        else:
            if book.estado == BookEstado.emprestado:
                emprestados += 1
            else:
                # É um furo!
                furos.append(FuroInfo(
                    livro_id=str(book.id),
                    titulo=book.titulo,
                    rfid_tag=book.rfid_tag,
                    ultimo_visto_em=None
                ))
    
    relatorio = InventarioRelatorio(
        total_cadastrado=total_cadastrado,
        total_lido=total_lido,
        presentes=presentes,
        emprestados=emprestados,
        furos=furos
    )
    
    # Salvar JSON no banco
    sessao.relatorio_dados = relatorio.model_dump()
    await db.commit()
    
    # Notificar via WebSocket
    await admin_ws_manager.notify_admin("Inventário Concluído", relatorio.model_dump())
    
    return relatorio

@router.get("/{sessao_id}/relatorio", summary="Obter Relatório do Inventário", description="Retorna o resultado consolidado do inventário. Use ?formato=csv para baixar a planilha.")
async def obter_relatorio(
    sessao_id: uuid.UUID,
    formato: str = Query("json", description="json ou csv"),
    db: AsyncSession = Depends(get_db_session)
):
    query = select(SessaoInventario).where(SessaoInventario.id == sessao_id)
    sessao = (await db.execute(query)).scalar_one_or_none()
    
    if not sessao or sessao.estado != InventarioEstado.concluido:
        raise HTTPException(status_code=400, detail="Relatório não disponível.")
        
    dados = sessao.relatorio_dados
    
    if formato == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Resumo"])
        writer.writerow(["Total Cadastrado", dados["total_cadastrado"]])
        writer.writerow(["Total Lido", dados["total_lido"]])
        writer.writerow(["Presentes", dados["presentes"]])
        writer.writerow(["Emprestados", dados["emprestados"]])
        writer.writerow([])
        writer.writerow(["Furos Encontrados"])
        writer.writerow(["Livro ID", "Título", "RFID Tag", "Último Visto"])
        
        for furo in dados["furos"]:
            writer.writerow([furo["livro_id"], furo["titulo"], furo["rfid_tag"], furo.get("ultimo_visto_em", "")])
            
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]), 
            media_type="text/csv", 
            headers={"Content-Disposition": f"attachment; filename=inventario_{sessao_id}.csv"}
        )
        
    return dados
