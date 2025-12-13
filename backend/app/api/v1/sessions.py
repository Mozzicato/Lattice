from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from ...database import get_db
from ... import models, schemas
from ...services.socratic_tutor import SocraticTutor
from ...services.mental_model_builder import MentalModelBuilder
from ...services.voice_service import VoiceService
from fastapi import UploadFile, File

router = APIRouter()
tutor = SocraticTutor()
model_builder = MentalModelBuilder()
voice_service = VoiceService()

@router.post("/", response_model=schemas.Session)
async def create_session(session: schemas.SessionCreate, db: AsyncSession = Depends(get_db)):
    new_session = models.Session(
        title=session.title,
        document_id=session.document_id
    )
    db.add(new_session)
    await db.commit()
    
    # Re-fetch with eager load to avoid MissingGreenlet error
    query = select(models.Session).where(models.Session.id == new_session.id).options(selectinload(models.Session.messages))
    result = await db.execute(query)
    new_session = result.scalar_one()
    
    return new_session

@router.get("/{session_id}", response_model=schemas.Session)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    # Eagerly load messages
    query = select(models.Session).where(models.Session.id == session_id).options(selectinload(models.Session.messages))
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

@router.post("/{session_id}/explain-differently", response_model=schemas.Message)
async def explain_differently(session_id: int, db: AsyncSession = Depends(get_db)):
    # Verify session exists
    session = await db.get(models.Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Record the "I'm Lost" signal from the user
    user_message = models.Message(
        session_id=session_id,
        role="user",
        content="I'm lost. Explain differently.",
        message_type="command" # Distinguish from normal text
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)
    
    # Generate Simplified Response
    # 1. Fetch history
    history_query = select(models.Message).where(models.Message.session_id == session_id).order_by(models.Message.timestamp)
    history_result = await db.execute(history_query)
    history_objs = history_result.scalars().all()
    
    history = [{"role": msg.role, "content": msg.content} for msg in history_objs]
    
    # 2. Get context
    context = "" 
    
    # 3. Call LLM with simplification
    response_text = await tutor.generate_simplified_explanation(history, context)
    
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

@router.post("/{session_id}/mental-model", response_model=schemas.Message)
async def generate_mental_model(session_id: int, db: AsyncSession = Depends(get_db)):
    # Verify session exists
    session = await db.get(models.Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Record user request
    user_message = models.Message(
        session_id=session_id,
        role="user",
        content="Help me build a mental model of this.",
        message_type="command"
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)
    
    # Get context (Placeholder)
    context = "The concept of a Damped Harmonic Oscillator: mx'' + cx' + kx = 0" 
    
    # Generate Mental Model
    response_text = await model_builder.build_mental_model(context)
    
    # Save assistant message
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

@router.post("/{session_id}/voice-message", response_model=schemas.Message)
async def create_voice_message(
    session_id: int, 
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    # Verify session exists
    session = await db.get(models.Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 1. Save Audio File (Mock save)
    # In real app: save to disk/S3
    # audio_path = f"uploads/voice_{session_id}_{file.filename}"
    # with open(audio_path, "wb") as f:
    #     shutil.copyfileobj(file.file, f)
    audio_path = "mock_audio_path.mp3"
    
    # 2. Transcribe (STT)
    transcribed_text = await voice_service.speech_to_text(audio_path)
    
    # 3. Save User Message
    user_message = models.Message(
        session_id=session_id,
        role="user",
        content=transcribed_text,
        message_type="audio_transcription"
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)
    
    # 4. Generate Assistant Response (Socratic)
    # Fetch history
    history_query = select(models.Message).where(models.Message.session_id == session_id).order_by(models.Message.timestamp)
    history_result = await db.execute(history_query)
    history_objs = history_result.scalars().all()
    
    history = [{"role": msg.role, "content": msg.content} for msg in history_objs]
    
    context = "" # Placeholder
    
    response_text = await tutor.generate_response(history, context)
    
    # 5. Save Assistant Message
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
