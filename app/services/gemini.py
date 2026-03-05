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

    def process_audio(self, audio_path: str, pdf_path: str | None = None) -> dict:
        """Process audio file with optional PDF for correction."""
        # Determine audio mime type config if possible
        audio_mime = self._get_mime_type(audio_path)
        audio_kwargs = {"file": audio_path}
        if audio_mime:
            audio_kwargs["config"] = {"mime_type": audio_mime}

        # Upload audio
        audio_file = self.client.files.upload(**audio_kwargs)
        uploaded_files = [audio_file]

        if pdf_path:
            pdf_mime = self._get_mime_type(pdf_path)
            pdf_kwargs = {"file": pdf_path}
            if pdf_mime:
                pdf_kwargs["config"] = {"mime_type": pdf_mime}
            pdf_file = self.client.files.upload(**pdf_kwargs)
            uploaded_files.append(pdf_file)
            prompt = (
                "다음 오디오는 강의 녹음 파일이고, PDF는 해당 강의의 교안입니다.\n\n"
                "아래 두 가지를 수행해 주세요:\n\n"
                "1. **핵심 요약**: 강의 전체 내용을 파악하기 쉽게 핵심 요약을 제공해 주세요.\n"
                "2. **전체 텍스트 변환**: 교안의 고유 명사, 전문 용어, 내용을 깊이 참고하여 "
                "오디오를 텍스트로 완벽하게 변환해 주세요. **'어...', '음...', '그...'와 같은 불필요한 추임새나 중복되는 말들은 생략하고** "
                "강의 문맥에 맞게 깔끔하게 교정된 텍스트를 제공해 주세요. "
                "타임스탬프(MM:SS 형식)도 포함해 주세요.\n\n"
                "출력 형식:\n"
                "## 핵심 요약\n(요약 내용)\n\n"
                "## 전체 텍스트\n(타임스탬프 포함 텍스트)"
            )
        else:
            prompt = (
                "다음 오디오는 강의 녹음 파일입니다.\n\n"
                "아래 두 가지를 수행해 주세요:\n\n"
                "1. **핵심 요약**: 강의 전체 내용을 파악하기 쉽게 핵심 요약을 제공해 주세요.\n"
                "2. **전체 텍스트 변환**: 오디오를 정확히 텍스트로 변환해 주세요. "
                "**'어...', '음...', '그...'와 같은 불필요한 추임새나 반복되는 말들은 모두 제거하고** "
                "문장이 매끄럽게 이어지도록 교정해 주세요. "
                "타임스탬프(MM:SS 형식)도 포함해 주세요.\n\n"
                "출력 형식:\n"
                "## 핵심 요약\n(요약 내용)\n\n"
                "## 전체 텍스트\n(타임스탬프 포함 텍스트)"
            )

        # Wait for files to be processed
        for f in uploaded_files:
            curr = self.client.files.get(name=f.name)
            while curr.state.name == "PROCESSING":
                time.sleep(2)
                curr = self.client.files.get(name=f.name)
            if curr.state.name != "ACTIVE":
                raise Exception(f"File {f.name} failed to process (state: {curr.state.name})")

        # Generate content with fallback logic
        # Using exact model IDs verified from the environment
        models_to_try = [
            "gemini-2.5-flash",
            "gemini-2.0-flash", 
            "gemini-2.0-flash-lite", 
            "gemini-3-flash-preview", 
            "gemini-2.5-flash-lite"
        ]
        last_exception = None
        result_text = None

        for model_name in models_to_try:
            try:
                print(f"Attempting generation with {model_name}...")
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=uploaded_files + [prompt],
                )
                result_text = response.text
                break # Success!
            except Exception as e:
                last_exception = e
                # If it's a quota error, try the next model
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    print(f"Quota exceeded for {model_name}. Trying fallback...")
                    continue
                else:
                    # For other errors, raise immediately
                    raise e
        
        if result_text is None:
            raise last_exception

        # Try to split summary and transcript
        summary = ""
        transcript = result_text
        if "## 핵심 요약" in result_text and "## 전체 텍스트" in result_text:
            parts = result_text.split("## 전체 텍스트")
            summary_part = parts[0]
            summary = summary_part.replace("## 핵심 요약", "").strip()
            transcript = parts[1].strip() if len(parts) > 1 else ""

        # Cleanup uploaded files
        for f in uploaded_files:
            try:
                self.client.files.delete(name=f.name)
            except Exception:
                pass

        return {
            "full_text": result_text,
            "summary": summary,
            "transcript": transcript,
        }
