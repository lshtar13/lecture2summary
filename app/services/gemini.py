import os
import time
import mimetypes
from google import genai

# Ensure mimetypes for audio files are known to the system so Gemini SDK doesn't fail
mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/webm", ".webm")
mimetypes.add_type("audio/ogg", ".ogg")

class GeminiService:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set")
        self.client = genai.Client(api_key=api_key)

    def _get_mime_type(self, path: str) -> str | None:
        ext = path.lower().split(".")[-1]
        if ext in ["m4a", "mp4"]:
            return "audio/mp4"
        if ext == "mp3":
            return "audio/mp3"
        if ext == "wav":
            return "audio/wav"
        if ext == "webm":
            return "audio/webm"
        if ext == "ogg":
            return "audio/ogg"
        if ext == "pdf":
            return "application/pdf"
        return None

    def _split_audio(self, audio_path: str, chunk_length_sec: int = 600) -> list[str]:
        """Split audio into chunks of specified length using ffmpeg."""
        import subprocess
        from pathlib import Path
        
        output_pattern = str(Path(audio_path).parent / f"chunk_%03d_{Path(audio_path).name}")
        # Command: ffmpeg -i input -f segment -segment_time 600 -c copy output%03d.mp4
        # Note: -c copy is fast but segmenting might not be precise on some codecs. 
        # For precision we could re-encode, but let's try copy first for speed.
        cmd = [
            "ffmpeg", "-i", audio_path, 
            "-f", "segment", 
            "-segment_time", str(chunk_length_sec), 
            "-c", "copy", 
            output_pattern
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Get list of generated files
        import glob
        chunks = sorted(glob.glob(str(Path(audio_path).parent / f"chunk_*_{Path(audio_path).name}")))
        return chunks

    def process_audio(self, audio_path: str, pdf_path: str | None = None, task_id: str | None = None) -> dict:
        """Process audio file in chunks with multi-step correction and progress tracking."""
        import asyncio
        from app.services import db

        async def update_progress(p: int, step: str, model: str = None):
            if task_id:
                try:
                    # In sync method, use run_coroutine_threadsafe or create_task if loop exists
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(db.update_lecture_status(task_id, progress=p, current_step=step, active_model=model))
                except: pass

        # 1. Split Audio
        update_progress(5, "오디오 분할 중...")
        chunks = self._split_audio(audio_path)
        num_chunks = len(chunks)
        
        # 2. Process each chunk for STT
        all_transcripts = []
        uploaded_files = []
        
        models_to_try = [
            "gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite", 
            "gemini-3-flash-preview", "gemini-2.5-flash-lite"
        ]

        for i, chunk in enumerate(chunks):
            step_msg = f"텍스트 변환 중 ({i+1}/{num_chunks})..."
            progress_val = 10 + int((i / num_chunks) * 60) # 10% to 70% range
            
            audio_mime = self._get_mime_type(chunk)
            audio_kwargs = {"file": chunk}
            if audio_mime: audio_kwargs["config"] = {"mime_type": audio_mime}
            
            f = self.client.files.upload(**audio_kwargs)
            uploaded_files.append(f)
            
            # Wait for file
            curr = self.client.files.get(name=f.name)
            while curr.state.name == "PROCESSING":
                time.sleep(1)
                curr = self.client.files.get(name=f.name)
            
            stt_prompt = "이 오디오의 내용을 타임스탬프없이 있는 그대로 텍스트로 변환해주세요. 불필요한 추임새는 제거하고 문장 단위로 끊어주세요."
            
            chunk_text = ""
            for model_name in models_to_try:
                try:
                    update_progress(progress_val, step_msg, model_name)
                    response = self.client.models.generate_content(model=model_name, contents=[f, stt_prompt])
                    chunk_text = response.text
                    # Log usage
                    if task_id: 
                        loop = asyncio.get_event_loop()
                        loop.create_task(db.log_usage(model_name, response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count))
                    break
                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e): continue
                    raise e
            
            all_transcripts.append(chunk_text)
            # Cleanup chunk file object immediately to free space/quota
            try: self.client.files.delete(name=f.name)
            except: pass
            if os.path.exists(chunk): os.remove(chunk)

        full_raw_text = "\n".join(all_transcripts)

        # 3. Final Correction & Summary
        update_progress(80, "최종 교정 및 요약 중...")
        
        final_files = []
        final_prompt = ""
        
        if pdf_path:
            pdf_mime = self._get_mime_type(pdf_path)
            pdf_f = self.client.files.upload(file=pdf_path, config={"mime_type": pdf_mime} if pdf_mime else None)
            final_files.append(pdf_f)
            # Wait for PDF
            curr = self.client.files.get(name=pdf_f.name)
            while curr.state.name == "PROCESSING":
                time.sleep(1)
                curr = self.client.files.get(name=pdf_f.name)
            
            final_prompt = (
                f"다음은 강의의 전체 STT 결과와 교안 PDF입니다. 교안의 전문 용어와 맥락을 참고하여 "
                f"STT 결과를 깔끔한 문장으로 교정하고 핵심 내용을 요약해주세요.\n\n"
                f"**지침**:\n"
                f"- '음', '어', '이거 이거' 등 반복어와 추임새 완벽 제거.\n"
                f"- 메타 데이터나 인사말 없이 본문만 출력.\n"
                f"- 5분 단위로 타임스탬프(MM:SS)를 삽입하며 구조화하세요.\n\n"
                f"## 핵심 요약\n\n## 전체 텍스트\n\n--- STT 데이터 ---\n{full_raw_text}"
            )
        else:
            final_prompt = (
                f"다음은 강의의 전체 STT 결과입니다. 내용을 깔끔한 문장으로 교정하고 핵심 내용을 요약해주세요.\n\n"
                f"**지침**:\n"
                f"- '음', '어', '이거 이거' 등 반복어와 추임새 완벽 제거.\n"
                f"- 메타 데이터나 인사말 없이 본문만 출력.\n"
                f"- 5분 단위로 타임스탬프(MM:SS)를 삽입하며 구조화하세요.\n\n"
                f"## 핵심 요약\n\n## 전체 텍스트\n\n--- STT 데이터 ---\n{full_raw_text}"
            )

        final_result_text = ""
        for model_name in models_to_try:
            try:
                update_progress(90, "최종 교정 및 요약 중...", model_name)
                response = self.client.models.generate_content(model=model_name, contents=final_files + [final_prompt])
                final_result_text = response.text
                if task_id:
                    loop = asyncio.get_event_loop()
                    loop.create_task(db.log_usage(model_name, response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count))
                break
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e): continue
                raise e

        # Cleanup PDF file object
        for f in final_files:
            try: self.client.files.delete(name=f.name)
            except: pass

        # Split final output
        summary = ""
        transcript = final_result_text
        if "## 핵심 요약" in final_result_text and "## 전체 텍스트" in final_result_text:
            parts = final_result_text.split("## 전체 텍스트")
            summary = parts[0].replace("## 핵심 요약", "").strip()
            transcript = parts[1].strip()

        update_progress(100, "분석 완료")
        
        return {
            "full_text": final_result_text,
            "summary": summary,
            "transcript": transcript,
        }
