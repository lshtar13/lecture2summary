import os
import sys
import time
from dotenv import load_dotenv
from google import genai

def main(audio_path, pdf_path=None):
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("에러: .env 파일에 GEMINI_API_KEY를 설정해주세요.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # 오디오 파일 업로드
    print(f"오디오 파일 업로드 중: {audio_path}")
    audio_file = client.files.upload(file=audio_path)

    uploaded_files = [audio_file]

    if pdf_path:
        print(f"PDF 파일 업로드 중: {pdf_path}")
        pdf_file = client.files.upload(file=pdf_path)
        uploaded_files.append(pdf_file)
        prompt = "다음 오디오는 강의 녹음 파일이고, PDF는 해당 강의의 교안입니다. 교안의 고유 명사와 내용을 깊이 참고하여 오디오를 텍스트로 완벽하게 변환해 주세요. 또한 전체 내용을 파악하기 쉽게 핵심 요약도 함께 제공해 주세요."
    else:
        prompt = "다음 오디오는 강의 녹음 파일입니다. 오디오를 정확히 텍스트로 변환해 주고, 핵심 요약도 함께 제공해 주세요."

    # 파일 처리 대기
    print("파일 처리 대기 중...")
    for f in uploaded_files:
        curr = client.files.get(name=f.name)
        while curr.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(2)
            curr = client.files.get(name=f.name)
        if curr.state.name != "ACTIVE":
            raise Exception(f"File {f.name} failed to process (state: {curr.state.name})")
    print(" 완료!")

    # Gemini 2.5 Flash로 분석 요청
    print("\nGemini 2.5 Flash에 분석 요청 중... (오디오 길이에 따라 1~5분 이상 소요될 수 있습니다)")

    contents = uploaded_files + [prompt]

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )
        print("\n" + "=" * 50)
        print("[ 결과 출력 ]")
        print("=" * 50)
        print(response.text)

        # 파일로 결과 저장
        with open("result.txt", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("\n>> 결과가 result.txt 에 저장되었습니다.")

    except Exception as e:
        print(f"생성 중 에러 발생: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python test_stt.py <오디오_파일_경로> [PDF_교안_경로]")
        print("예시: python test_stt.py sample.mp3")
        sys.exit(1)

    audio_path = sys.argv[1]
    pdf_path = sys.argv[2] if len(sys.argv) > 2 else None
    main(audio_path, pdf_path)
