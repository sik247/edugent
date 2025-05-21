#!/usr/bin/env python3

import os
import re
import asyncio
from dotenv import load_dotenv
import streamlit as st
from agents import Agent, Runner
from googleapiclient.discovery import build

# ─── Ensure asyncio loop ───
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# ─── Load API keys ───
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if not OPENAI_API_KEY or not YOUTUBE_API_KEY:
    st.error("Please set OPENAI_API_KEY and YOUTUBE_API_KEY in your environment.")
    st.stop()

# ─── YouTube Search Helper ───
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
def search_youtube_videos(query: str, max_results: int = 3):
    req = youtube.search().list(part="snippet", q=query, type="video", maxResults=max_results)
    res = req.execute()
    return [(item["snippet"]["title"], f"https://youtu.be/{item['id']['videoId']}") for item in res.get("items", [])]

# ─── Agents ───
keyword_gen_agent = Agent(
    name="KeywordGen Agent",
    handoff_description="Extracts the core solving method as a keyword",
    instructions=(
        "You are KeywordGen Agent. Given a middle-school math problem, "
        "respond with exactly one concise keyword or short phrase capturing its main solving method."
    ),
)

hint_agent = Agent(
    name="HintAgent",
    handoff_description="수학 키워드 기반으로 단계별 사고 흐름을 제공합니다",
    instructions=(
        "당신은 HintAgent입니다. 중학생을 대상으로 수학 개념이나 풀이 방법을 설명하는 선생님입니다. "
        "학생이 입력한 수학 키워드(예: '공약수의 개수의 의미', '비례식의 성질', '일차방정식 풀이')에 대해 다음 지침에 따라 힌트를 작성하세요:\n\n"
        "1. 해당 개념을 **두 단계 이상**으로 나누어 설명합니다. 각 단계는 '첫번째', '두번째'처럼 시작하세요.\n"
        "2. 개념을 설명할 때는 **핵심 원리, 정의, 적용 절차**를 포함시키고, 필요한 경우 **수학적 표현, 정량적 방법(예: 소인수분해, 지수 비교, 방정식 변형)**을 사용하세요.\n"
        "3. 설명은 중학생이 이해할 수 있도록 **친절하고 간결하게**, 하지만 **내용은 충분히 깊이 있게** 서술합니다.\n"
        "4. 정답을 직접 제시하지는 말고, **풀이 흐름의 마지막 직전까지** 도달하도록 안내하세요.\n\n"
        "예시 응답 형식:\n"
        "첫번째, [여기에 해당 키워드의 원리 또는 개념 설명].\n"
        "두번째, [이 개념을 문제에 적용하기 위한 절차 또는 정량적 판단 설명].\n\n"
        "※ 예시 키워드: '공약수의 개수의 의미'일 경우\n"
        "→ 첫번째, 세 수의 공약수 개수는 최대공약수의 약수 개수와 같다는 걸 이해해야 해.\n"
        "→ 두번째, 최대공약수를 구하려면 세 수를 소인수분해하고, 공통인 소인수를 찾은 다음, 각 지수 중 가장 작은 수를 선택해서 곱하면 돼.\n\n"
        "이러한 형식을 기반으로, 입력된 키워드에 맞춰 힌트를 작성하세요."
    )
)


video_agent = Agent(
    name="VideoAgent",
    handoff_description="Recommends a YouTube video based on a keyword",
    instructions=(
        "You are VideoAgent. Given a keyword or topic, return a YouTube video title and URL "
        "that explains that concept at a middle-school level."
    ),
)

triage_agent = Agent(
    name="TriageAgent",
    handoff_description="Decides whether to give a hint or a video based on the student's request",
    instructions="""
You are the Triage Agent. Route the student's request according to these examples:

Example 1:
  Student: "I just need a quick hint to get started."
  → HANDOFF: HintAgent

Example 2:
  Student: "I don't get it at all, can I watch a video?"
  → HANDOFF: VideoAgent

Now process the student’s exact input and output exactly one line:
  HANDOFF: HintAgent
or
  HANDOFF: VideoAgent
""",
    handoffs=[hint_agent, video_agent],
)

# ─── Streamlit UI ───
st.set_page_config(page_title="Math Helper", layout="centered")
st.title("🧮 Math Helper")

if "step" not in st.session_state:
    st.session_state.step = 1

# Step 1: Problem Input
# Step 1: Problem Input
if st.session_state.step == 1:
    st.subheader("Step 1: 문제 입력 또는 편집")

    default_problem = (
        "다음 세 수 100, 2²×3×5, 2×5²×7의 공약수 개수를 구하는 문제입니다.\n\n"
        "① 3개   ② 4개   ③ 5개   ④ 6개   ⑤ 7개"
    )
    if "problem" not in st.session_state:
        st.session_state.problem = default_problem

    st.session_state.problem = st.text_area(
        "문제를 자유롭게 수정할 수 있습니다:",
        value=st.session_state.problem,
        height=160,
        key="problem_input"
    ).strip()

    if st.button("다음"):
        if st.session_state.problem:
            st.session_state.step = 2
        else:
            st.warning("문제를 입력해주세요.")


# Step 2: Keyword Input
elif st.session_state.step == 2:
    st.subheader("Step 2: 키워드 입력 또는 자동 생성")
    st.write(f"🔍 문제: {st.session_state.problem}")

    default_keyword = "공약수의 개수의 의미"
    key_input = st.text_input(
        "해결 방법을 요약하는 키워드를 입력하거나 그대로 두세요:",
        value=default_keyword,
        key="keyword_input"
    ).strip()

    if st.button("키워드 사용"):
        st.session_state.keyword = key_input or default_keyword
        st.session_state.step = 3

# Step 3: Triage
elif st.session_state.step == 3:
    st.subheader("Step 3: 어떤 도움이 필요하신가요?")
    st.write(f"🔑 **키워드:** {st.session_state.keyword}")
    choice = st.radio("원하시는 옵션을 선택하세요:", ["힌트 보기", "영상 설명 보기"])
    if st.button("계속"):
        triage_input = "quick hint" if choice == "힌트 보기" else "video"
        triage_res = Runner.run_sync(triage_agent, triage_input)
        decision = triage_res.final_output.strip()
        st.session_state.decision = decision
        st.session_state.step = 4

# Step 4: Show Result
elif st.session_state.step == 4:
    if st.session_state.decision == "HANDOFF: HintAgent":
        st.subheader("💡 힌트")
        hint_res = Runner.run_sync(hint_agent, st.session_state.keyword)
        st.write(hint_res.final_output.strip())
    else:
        st.subheader("🎥 추천 영상")
        video_res = Runner.run_sync(video_agent, st.session_state.keyword)
        out = video_res.final_output.strip()
        st.write(out)

        urls = re.findall(r"https?://[^\s\)]*", out)
        url = urls[0] if urls else ""
        if url:
            st.video(url)
        else:
            st.warning("⚠️ 유효한 영상 링크를 찾을 수 없습니다.")

        st.subheader("📹 추가 유튜브 결과")
        for title, vid_url in search_youtube_videos(st.session_state.keyword):
            st.markdown(f"- **{title}**\n  {vid_url}")

    if st.button("처음부터 시작"):
        for key in ["step", "keyword", "problem", "decision"]:
            st.session_state.pop(key, None)
        st.session_state.step = 1
