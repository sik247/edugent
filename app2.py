#!/usr/bin/env python3

import streamlit as st
import asyncio
import json
import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from agents import Agent, Runner

# ─── Load API Keys ───
load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not YOUTUBE_API_KEY or not OPENAI_API_KEY:
    st.error("Please set YOUTUBE_API_KEY and OPENAI_API_KEY in .env")
    st.stop()

# ─── Load problem.json ───
with open("/Users/harrykang/Desktop/edugent/edugent/problem.json", "r", encoding="utf-8") as f:
    problem_data = json.load(f)
problem_dict = {item["index"]: item for item in problem_data}

# ─── YouTube Search ───
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def search_youtube_videos(query: str, max_results: int = 3):
    try:
        req = youtube.search().list(part="snippet", q=query, type="video", maxResults=max_results)
        res = req.execute()
        return [(item["snippet"]["title"], f"https://youtu.be/{item['id']['videoId']}") for item in res.get("items", [])]
    except Exception as e:
        return [("YouTube 검색 실패", str(e))]

# ─── Define Agents ───
hint_agent = Agent(
    name="HintAgent",
    handoff_description="문제 index에 따른 reference 기반 힌트를 생성합니다.",
    instructions=(
        "당신은 수학 선생님입니다. 아래는 문제와 관련된 참조 설명입니다. "
        "참조 설명(reference)을 기반으로 학생에게 단계적으로 힌트를 작성하세요. 반드시 '첫번째', '두번째' 형식으로 시작하세요. "
        "문제의 정답은 말하지 말고, 마지막 풀이 단계 직전까지 안내하세요."
    )
)

triage_agent = Agent(
    name="TriageAgent",
    handoff_description="학생 입력에 따라 Hint 또는 Video 추천을 선택합니다.",
    instructions=(
        "너는 학생의 요청을 읽고, 다음 중 어떤 도움을 원하는지 분류하는 역할을 한다.\n"
        "예시:\n"
        "- '힌트를 원해요', '핵심 개념이 뭔가요?', '풀고 싶은데 감이 안 와요' → HANDOFF: HintAgent\n"
        "- '개념 영상 있나요?', '설명 영상 보고 싶어요', '추천 영상 보여줘' → HANDOFF: VideoAgent\n"
        "학생의 입력을 보고 아래 형식으로만 응답하라:\n"
        "HANDOFF: HintAgent  또는  HANDOFF: VideoAgent"
    )
)

# ─── Streamlit UI ───
st.set_page_config(page_title="📘 Agentic AI Hint Generator", layout="centered")
st.title("📘 문제 힌트 + AI 해설 + YouTube 영상")

index_list = list(problem_dict.keys())
selected_index = st.selectbox("문제 코드를 선택하세요:", index_list, index=index_list.index("D070215ASB"))

if selected_index:
    data = problem_dict[selected_index]
    st.markdown("### ✅ 문제")
    st.markdown(data["problem"])

    if data.get("choices"):
        st.markdown("**선택지:** " + " / ".join(data["choices"]))

    st.markdown("### 🔑 키워드")
    st.write(data["keyword"])

    st.markdown("### 📖 참조 설명 (Reference Data)")
    st.info(data["reference"])

    st.markdown("### 🧑‍🎓 학생 질문 입력")
    user_query = st.text_input("도움을 받고 싶은 내용을 입력하세요:")

    if st.button("도움 요청하기") and user_query:
        with st.spinner("입력 내용을 분석 중입니다..."):
            import asyncio

            try:
                asyncio.get_running_loop()
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())

        decision = Runner.run_sync(triage_agent, user_query).final_output.strip()

        if "HintAgent" in decision:
            st.markdown("#### 💡 생성된 힌트 (Reference 기반)")
            user_input = f"문제: {data['problem']}\n\n키워드: {data['keyword']}\n\n참조 설명: {data['reference']}"
            result = Runner.run_sync(hint_agent, user_input)
            st.write(result.final_output.strip())
        else:
            st.markdown("#### 🎥 추천 YouTube 영상")
            videos = search_youtube_videos(data["keyword"])
            for title, url in videos:
                st.markdown(f"- **{title}**\n  {url}")
                if "youtube.com" in url or "youtu.be" in url:
                    st.video(url)
