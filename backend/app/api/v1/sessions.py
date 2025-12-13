from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from ...database import get_db
from ... import models, schemas
from ...services.socratic_tutor import SocraticTutor

router = APIRouter()
tutor = SocraticTutor()

@router.post("/", response_model=schemas.Session)
async def create_session(session: schemas.SessionCreate, db: AsyncSession = Depends(get_db)):
    new_session = models.Session(
        title=session.title,
        document_id=session.document_id
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session

@router.get("/{session_id}", response_model=schemas.Session)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    # We need to eagerly load messages if we want them in the response
    # For now, simple get
    query = select(models.Session).where(models.Session.id == session_id)
    result = await db.execute(query)
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/{session_id}/messages", response_model=schemas.Message)
async def create_message(session_id: int, message: schemas.MessageCreate, db: AsyncSession = Depends(get_db)):
    # Verify session exists
    session = await db.get(models.Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Save user message
    user_message = models.Message(
        session_id=session_id,
        role=message.role,
        content=message.content,
        message_type=message.message_type
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)
    
    # Generate Assistant Response
    # 1. Fetch history
    history_query = select(models.Message).where(models.Message.session_id == session_id).order_by(models.Message.timestamp)
    history_result = await db.execute(history_query)
    history_objs = history_result.scalars().all()
    
    history = [{"role": msg.role, "content": msg.content} for msg in history_objs]
    
    # 2. Get context (Placeholder: In real app, fetch relevant chunks from vector DB or document)
    context = "" 
    
    # 3. Call LLM
    response_text = await tutor.generate_response(history, context)
    
    # 4. Save assistant message
    assistant_message = models.Message(
        session_id=session_id,
        role="assistant",
        content=response_text,
        message_type="text"
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)
    
    return assistant_message

@router.get("/{session_id}/messages", response_model=List[schemas.Message])
async def get_messages(session_id: int, db: AsyncSession = Depends(get_db)):
    query = select(models.Message).where(models.Message.session_id == session_id).order_by(models.Message.timestamp)
    result = await db.execute(query)
    messages = result.scalars().all()
    return messages
