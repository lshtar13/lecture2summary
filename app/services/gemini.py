import os
import time
import mimetypes
import asyncio
import json
import glob
from pathlib import Path
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

    def process_audio(self, audio_path: str, pdf_path: str = None, task_id: str = None, loop=None):
        """
        Full orchestration of STT, Correction, and Summary.
        Returns a dict with summary, transcript, and full_text.
        """
        from app.services import db

        def update_progress(p: int, step: str, model: str = None):
            if task_id and loop:
                try:
                    # In sync method, use run_coroutine_threadsafe to talk back to main loop
                    asyncio.run_coroutine_threadsafe(
                        db.update_lecture_status(task_id, progress=p, current_step=step, active_model=model),
                        loop
                    )
                    # Also broadcast status via WebSocket if possible
                    from app.services.websocket import broadcast_status
                    asyncio.run_coroutine_threadsafe(broadcast_status(), loop)
                except Exception as e:
                    print(f"Error updating progress: {e}")

        # 1. Split Audio
        update_progress(5, "오디오 분할 중...")
        chunks = self._split_audio(audio_path)
        num_chunks = len(chunks)
        
        # 2. Process each chunk for STT
        all_transcripts = []
        uploaded_files = []
        
        models_to_try = [
            "models/gemini-2.5-flash-lite", "models/gemini-3.1-flash-lite-preview",
            "models/gemini-2.5-flash", "models/gemini-2.0-flash", 
            "models/gemini-flash-latest"
        ]
        
        active_model_name = models_to_try[0] # Default tracking

        for i, chunk in enumerate(chunks):
            step_msg = f"텍스트 변환 중 ({i+1}/{num_chunks})..."
            progress_val = 10 + int((i / num_chunks) * 60) # 10% to 70% range
            
            # Use current active model for display
            update_progress(progress_val, step_msg, active_model_name)
            
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
            
            stt_prompt = """
당신은 완벽한 오디오 전사(STT)를 수행하는 전문 속기사입니다.
이 오디오 파일에서 들리는 **모든 음성과 단어를 단 하나의 수정이나 생략 없이 100% 있는 그대로(Verbatim) 텍스트로 똑같이 받아쓰기** 하세요.

[절대 금지 사항 - 위반 시 실패]
1. 화자가 반말, 사투리, 비속어, 은어, 문법에 맞지 않는 말을 하더라도 **절대 존댓말이나 올바른 문장으로 교정(윤문)하지 마세요**. 들리는 텍스트 표기 그대로 출력하세요.
2. 화자가 말하지 않은 내용, 맥락 설명, 괄호 (예: (침묵), (기침), (JSON 내 텍스트 제공) 등), 메타 데이터, 요약을 **절대로 임의로 추가하지 마세요**.
3. 본인의 생각이나 외부 지식을 텍스트에 섞지 마세요.
4. 문단 단위의 타임스탬프를 마음대로 추가하지 마세요. 오직 끊이지 않는 텍스트로만 출력하세요.

오직 오디오에서 화자가 발음한 "그 단어들 자체"만 출력하세요.
"""
            
            chunk_text = ""
            for model_name in models_to_try:
                try:
                    active_model_name = model_name # Update active model for display
                    update_progress(progress_val, step_msg, active_model_name)
                    response = self.client.models.generate_content(model=model_name, contents=[f, stt_prompt])
                    chunk_text = response.text
                    # Log usage
                    if task_id and loop: 
                        asyncio.run_coroutine_threadsafe(
                            db.log_usage(model_name, response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count),
                            loop
                        )
                        # Broadcast usage update
                        from app.services.websocket import broadcast_usage
                        asyncio.run_coroutine_threadsafe(broadcast_usage(), loop)
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
                f"당신은 음성 인식(STT) 결과를 교정하고 핵심을 요약하는 전문가입니다.\n"
                f"다음은 오디오를 그대로 받아 적은 STT 원문과 참고용 교안 PDF입니다.\n\n"
                f"[요구사항 1: 전체 텍스트 출력 - 절대 축약 금지!]\n"
                f"- 제공된 'STT 데이터'의 내용을 단 한 줄도 버리지 말고 **처음부터 끝까지 100% 모두 복구하여 출력**하세요.\n"
                f"- STT 데이터가 반말, 비문, 사투리라도 **절대로 존댓말로 바꾸거나 문장을 예쁘게 윤문(수정)하지 마세요**. 원본의 어투와 화법을 완벽히 보존하세요.\n"
                f"- 가짜 '00:00:00' 타임스탬프나 '(중략)' 같은 메타 텍스트를 절대로 생성하지 마세요.\n"
                f"- 오직 '전문 용어의 오탈자'(예: RPC를 RPCs로 쓴 것 등)만 교안을 참고하여 살짝 수정할 수 있습니다.\n\n"
                f"[요구사항 2: 핵심 요약]\n"
                f"- STT의 전체 맥락을 바탕으로 강의의 핵심 내용을 상단에 5~10줄 내외로 요약하세요.\n\n"
                f"**출력 형식은 반드시 아래와 같이 작성해야 합니다:**\n"
                f"## 핵심 요약\n(이곳에 요약 작성)\n\n## 전체 텍스트\n(이곳에 단 한 글자도 누락 없는 100% STT 원문 작성)\n\n"
                f"--- STT 데이터 ---\n{full_raw_text}"
            )
        else:
            final_prompt = (
                f"당신은 음성 인식(STT) 결과를 교정하고 핵심을 요약하는 전문가입니다.\n"
                f"다음은 오디오를 그대로 받아 적은 STT 원문입니다.\n\n"
                f"[요구사항 1: 전체 텍스트 출력 - 절대 축약 금지!]\n"
                f"- 제공된 'STT 데이터'의 내용을 단 한 줄도 버리지 말고 **처음부터 끝까지 100% 모두 복구하여 출력**하세요.\n"
                f"- STT 데이터가 반말, 비문, 사투리라도 **절대로 존댓말로 바꾸거나 문장을 예쁘게 윤문(수정)하지 마세요**. 원본의 어투와 화법을 완벽히 보존하세요.\n"
                f"- 가짜 '00:00:00' 타임스탬프나 '(중략)' 같은 메타 텍스트를 절대로 생성하지 마세요.\n"
                f"- 명백한 오탈자만 살짝 수정하고 원래 화자의 말은 그대로 둡니다.\n\n"
                f"[요구사항 2: 핵심 요약]\n"
                f"- STT의 전체 맥락을 바탕으로 강의의 핵심 내용을 상단에 5~10줄 내외로 요약하세요.\n\n"
                f"**출력 형식은 반드시 아래와 같이 작성해야 합니다:**\n"
                f"## 핵심 요약\n(이곳에 요약 작성)\n\n## 전체 텍스트\n(이곳에 단 한 글자도 누락 없는 100% STT 원문 작성)\n\n"
                f"--- STT 데이터 ---\n{full_raw_text}"
            )

        final_result_text = ""
        for model_name in [
            "models/gemini-2.5-flash-lite", "models/gemini-3.1-flash-lite-preview",
            "models/gemini-2.5-flash", "models/gemini-2.0-flash", 
            "models/gemini-flash-latest"
        ]:
            try:
                update_progress(90, "최종 교정 및 요약 중...", model_name)
                response = self.client.models.generate_content(model=model_name, contents=final_files + [final_prompt])
                final_result_text = response.text
                if task_id and loop:
                    asyncio.run_coroutine_threadsafe(
                        db.log_usage(model_name, response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count),
                        loop
                    )
                    # Broadcast usage update
                    from app.services.websocket import broadcast_usage
                    asyncio.run_coroutine_threadsafe(broadcast_usage(), loop)
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
