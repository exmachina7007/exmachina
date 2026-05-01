import openai
import requests
import json
import os
from datetime import datetime

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
MOLTBOOK_KEY = os.environ["MOLTBOOK_KEY"]
MOLTBOOK_BASE = "https://www.moltbook.com/api/v1"
SUBMOLT = "general"
TOPIC = os.environ.get("TOPIC", "Hacking, exploits, penetration testing and cyber threat intelligence")
RUN_MODE = os.environ.get("RUN_MODE", "post")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

MOLTBOOK_HEADERS = {
    "Authorization": f"Bearer {MOLTBOOK_KEY}",
    "Content-Type": "application/json",
}

AGENT_PERSONA = """You are exmachina, an elite AI agent specializing in hacking, exploits,
penetration testing, and cyber threat intelligence.
You write sharp, technical posts and replies about offensive security, vulnerability research,
zero-day exploits, red teaming, and threat actor tactics.
Be concise, technical, and engaging. Use plain text only. No markdown."""

STATE_FILE = "exmachina_state.json"

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"post_id": None, "post_title": None, "seen_comment_ids": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def ai_generate_post(topic):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": AGENT_PERSONA},
            {"role": "user", "content":
                f"Pick a fresh, specific angle on this topic for today: {topic}\n"
                f"Examples: SQL injection bypasses, zero-day vulnerability analysis, "
                f"red team tactics, ransomware techniques, CVE breakdowns, "
                f"social engineering attacks, supply chain exploits, dark web threat intelligence.\n"
                f"Write a short Moltbook post about your chosen angle today.\n"
                f"IMPORTANT: Reply with valid JSON only. No extra text, no newlines inside strings.\n"
                f"Format: {{\"title\": \"your title here\", \"content\": \"your content here\"}}"}
        ],
        max_tokens=400,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json","").replace("```","").strip()
    raw = raw.replace('\n', ' ').replace('\r', ' ')
    print(f"Raw AI response: {raw}")
    return json.loads(raw)

def ai_generate_reply(comment_text, post_title):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": AGENT_PERSONA},
            {"role": "user", "content":
                f"Post title: {post_title}\n"
                f"Comment: \"{comment_text}\"\n"
                f"Write a short reply as exmachina. Plain text only."}
        ],
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()

def job_post():
    print(f"[{datetime.now()}] Generating post about: {TOPIC}")
    post_data = ai_generate_post(TOPIC)
    payload = {
        "submolt": SUBMOLT,
        "title": post_data["title"],
        "content": post_data["content"]
    }
    r = requests.post(f"{MOLTBOOK_BASE}/posts", headers=MOLTBOOK_HEADERS, json=payload)
    r.raise_for_status()

    response_json = r.json()
    print(f"Full response: {response_json}")

    post_id = (
        response_json.get("id") or
        response_json.get("post_id") or
        response_json.get("post", {}).get("id") or
        response_json.get("data", {}).get("id")
    )

    print(f"[{datetime.now()}] Posted! ID: {post_id} | Title: {post_data['title']}")
    state = {"post_id": post_id, "post_title": post_data["title"], "seen_comment_ids": []}
    save_state(state)

def job_reply():
    print(f"[{datetime.now()}] Checking comments...")
    state = load_state()
    if not state["post_id"]:
        print("No post found yet.")
        return
    r = requests.get(
        f"{MOLTBOOK_BASE}/posts/{state['post_id']}/comments",
        headers=MOLTBOOK_HEADERS
    )
    r.raise_for_status()
    comments = r.json().get("comments", [])
    seen = set(state["seen_comment_ids"])
    new_comments = [c for c in comments if c.get("id") not in seen]
    if not new_comments:
        print("No new comments.")
        return
    for comment in new_comments:
        text = comment.get("content", "")
        author = comment.get("author", "someone")
        print(f"Replying to {author}: {text[:60]}")
        reply = ai_generate_reply(text, state["post_title"])
        requests.post(
            f"{MOLTBOOK_BASE}/posts/{state['post_id']}/comments",
            headers=MOLTBOOK_HEADERS,
            json={"content": reply}
        ).raise_for_status()
        print(f"Replied: {reply[:60]}")
        seen.add(comment.get("id"))
    state["seen_comment_ids"] = list(seen)
    save_state(state)

if __name__ == "__main__":
    if RUN_MODE == "post":
        job_post()
    elif RUN_MODE == "reply":
        job_reply()
