#!/usr/bin/env python3
"""
Interactive Math helper with a preset problem → optional keyword input (or auto‐generate)
→ few‐shot triage → hint or video, looping until the user types 'exit'.

Prerequisites:
  pip install openai-agents google-api-python-client python-dotenv
  export OPENAI_API_KEY="your_openai_api_key"
  export YOUTUBE_API_KEY="your_youtube_api_key"
"""

import os
from dotenv import load_dotenv
from agents import Agent, Runner
from googleapiclient.discovery import build

# ————— Load environment variables —————
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY   = os.getenv("YOUTUBE_API_KEY")
if not OPENAI_API_KEY or not YOUTUBE_API_KEY:
    raise RuntimeError("Please set both OPENAI_API_KEY and YOUTUBE_API_KEY in your environment")

# ————— YouTube search helper —————
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
def search_youtube_videos(query: str, max_results: int = 3):
    req = youtube.search().list(part="snippet", q=query, type="video", maxResults=max_results)
    res = req.execute()
    return [
        (item["snippet"]["title"], f"https://youtu.be/{item['id']['videoId']}")
        for item in res.get("items", [])
    ]

# ————— Agent definitions —————

keyword_gen_agent = Agent(
    name="KeywordGen Agent",
    handoff_description="Extracts the core solving method as a keyword",
    instructions=(
        "You are KeywordGen Agent. Given the preset middle-school math problem, "
        "respond with exactly one concise keyword or short phrase capturing its main solving method."
    ),
)

hint_agent = Agent(
    name="HintAgent",
    handoff_description="Provides a concise 1–2 sentence hint for a keyword",
    instructions=(
        "You are HintAgent. When given a single keyword, respond with a 1–2 sentence hint "
        "that guides the student toward the solution without revealing it entirely."
    ),
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

Example 3:
  Student: "A bit stuck, perhaps a simple tip would help."
  → HANDOFF: HintAgent

Example 4:
  Student: "A visual demo would be great."
  → HANDOFF: VideoAgent

Now process the student’s exact input and output **exactly one line**:
  HANDOFF: HintAgent
or
  HANDOFF: VideoAgent
""",
    handoffs=[hint_agent, video_agent],
)

# ————— Main application loop —————

def main():
    preset_problem = "Twice a number plus five equals seventeen. What is the number?"
    print("Welcome to the Math Helper! Type 'exit' at any prompt to quit.")

    while True:
        # 1) Show the preset problem
        print(f"\nProblem:\n  {preset_problem}\n")

        # 2) Ask for a keyword or auto-generate
        key_input = input(
            "Enter a keyword summarizing the solving method,\nor press Enter to auto-generate:\n> "
        ).strip()
        if key_input.lower() == "exit":
            break

        if key_input:
            keyword = key_input
            print(f"\n🔑 Using provided keyword: {keyword}\n")
        else:
            gen = Runner.run_sync(keyword_gen_agent, preset_problem)
            keyword = gen.final_output.strip()
            print(f"\n🔑 Generated keyword: {keyword}\n")

        # 3) Ask student preference
        choice = input("Would you like a quick hint or a video explanation?\n> ").strip()
        if choice.lower() == "exit":
            break

        # 4) Few-shot triage handoff
        triage_res = Runner.run_sync(triage_agent, choice)
        decision = triage_res.final_output.strip()

        # 5) Invoke the chosen agent with the keyword
        if decision == "HANDOFF: HintAgent":
            hint_res = Runner.run_sync(hint_agent, keyword)
            print(f"\n💡 Hint:\n  {hint_res.final_output.strip()}\n")
        else:  # HANDOFF: VideoAgent
            video_res = Runner.run_sync(video_agent, keyword)
            print(f"\n🎥 Video Recommendation:\n  {video_res.final_output.strip()}\n")
            print("📹 Additional YouTube search results:")
            for title, url in search_youtube_videos(keyword):
                print(f"- {title}\n  {url}")
            print()

    print("Goodbye!")

if __name__ == "__main__":
    main()
