import os
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, Text, DateTime, select, delete
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://admin:admin123@db:5432/lecture2summary")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Lecture(Base):
    __tablename__ = "lectures"

    id = Column(String, primary_key=True)
    title = Column(String)
    audio_filename = Column(String)
    pdf_filename = Column(String)
    status = Column(String, default="processing")
    summary = Column(Text, nullable=True)
    transcript = Column(Text, nullable=True)
    full_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        # For testing, we might want to drop and recreate, but normally we'd use migrations
        # await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

async def create_lecture(task_id: str, title: str, audio_filename: str, pdf_filename: str):
    async with AsyncSessionLocal() as session:
        lecture = Lecture(
            id=task_id,
            title=title,
            audio_filename=audio_filename,
            pdf_filename=pdf_filename,
            status="processing"
        )
        session.add(lecture)
        await session.commit()

async def update_lecture_result(task_id: str, summary: str, transcript: str, full_text: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Lecture).where(Lecture.id == task_id))
        lecture = result.scalar_one_or_none()
        if lecture:
            lecture.status = "completed"
            lecture.summary = summary
            lecture.transcript = transcript
            lecture.full_text = full_text
            await session.commit()

async def update_lecture_error(task_id: str, error_msg: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Lecture).where(Lecture.id == task_id))
        lecture = result.scalar_one_or_none()
        if lecture:
            lecture.status = "error"
            lecture.summary = f"Error: {error_msg}"
            await session.commit()

async def get_lecture(task_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Lecture).where(Lecture.id == task_id))
        lecture = result.scalar_one_or_none()
        if lecture:
            return {
                "id": lecture.id,
                "title": lecture.title,
                "audio_filename": lecture.audio_filename,
                "pdf_filename": lecture.pdf_filename,
                "status": lecture.status,
                "summary": lecture.summary,
                "transcript": lecture.transcript,
                "full_text": lecture.full_text,
                "created_at": lecture.created_at.isoformat()
            }
        return None

async def get_all_lectures():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Lecture).order_by(Lecture.created_at.desc()))
        lectures = result.scalars().all()
        return [
            {
                "id": l.id,
                "title": l.title,
                "audio_filename": l.audio_filename,
                "pdf_filename": l.pdf_filename,
                "status": l.status,
                "summary": f"{l.summary[:100]}..." if l.summary else None,
                "created_at": l.created_at.isoformat()
            }
            for l in lectures
        ]

async def delete_lecture(task_id: str):
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Lecture).where(Lecture.id == task_id))
        await session.commit()
