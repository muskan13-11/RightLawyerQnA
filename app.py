import streamlit as st
import json
from pathlib import Path
import uuid

# Import the Perplexity backend function
from backend import get_divorce_assistant_response

# ---------- Persistent Multi-Chat History Management ----------
HISTORY_FOLDER = Path("chat_histories")
HISTORY_FOLDER.mkdir(exist_ok=True)

# Unique user session
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

user_folder = HISTORY_FOLDER / st.session_state.session_id
user_folder.mkdir(exist_ok=True)

# Load all chats metadata
if 'chats' not in st.session_state:
    st.session_state.chats = []
    for file in sorted(user_folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(file.read_text())
            st.session_state.chats.append({
                "id": file.stem,
                "title": data.get("title", "New Chat"),
                "messages": data.get("messages", [])
            })
        except:
            pass

    # If no chats, create one
    if not st.session_state.chats:
        new_id = str(uuid.uuid4())
        st.session_state.chats.append({"id": new_id, "title": "New Chat", "messages": []})
        st.session_state.current_chat_id = new_id
    else:
        # Load the most recent chat by default
        st.session_state.current_chat_id = st.session_state.chats[0]["id"]

# Ensure current messages are in sync with current_chat_id
if 'current_chat_id' in st.session_state:
    current_chat = next((c for c in st.session_state.chats if c["id"] == st.session_state.current_chat_id), None)
    if current_chat:
        st.session_state.messages = current_chat["messages"]
    else:
        # Fallback if something went wrong
        st.session_state.current_chat_id = st.session_state.chats[0]["id"]
        st.session_state.messages = st.session_state.chats[0]["messages"]

# Helper functions
def save_current_chat():
    for chat in st.session_state.chats:
        if chat["id"] == st.session_state.current_chat_id:
            chat["messages"] = st.session_state.messages
            break
    file_path = user_folder / f"{st.session_state.current_chat_id}.json"
    data = {
        "title": next(c["title"] for c in st.session_state.chats if c["id"] == st.session_state.current_chat_id),
        "messages": st.session_state.messages
    }
    file_path.write_text(json.dumps(data, indent=2))

def create_new_chat():
    new_id = str(uuid.uuid4())
    new_chat = {"id": new_id, "title": "New Chat", "messages": []}
    st.session_state.chats.insert(0, new_chat)  # newest on top
    st.session_state.current_chat_id = new_id
    st.session_state.messages = []
    save_current_chat()
    st.rerun()

def switch_to_chat(chat_id):
    save_current_chat()  # Save current before switching
    st.session_state.current_chat_id = chat_id
    selected_chat = next(c for c in st.session_state.chats if c["id"] == chat_id)
    st.session_state.messages = selected_chat["messages"]
    st.rerun()

def delete_chat(chat_id):
    if len(st.session_state.chats) == 1:
        st.warning("You cannot delete your last chat.")
        return
    st.session_state.chats = [c for c in st.session_state.chats if c["id"] != chat_id]
    (user_folder / f"{chat_id}.json").unlink(missing_ok=True)
    if st.session_state.current_chat_id == chat_id:
        st.session_state.current_chat_id = st.session_state.chats[0]["id"]
        st.session_state.messages = st.session_state.chats[0]["messages"]
    st.rerun()

# Auto-generate title from first user message
if (st.session_state.messages and 
    st.session_state.messages[0]["role"] == "user" and
    next(c["title"] for c in st.session_state.chats if c["id"] == st.session_state.current_chat_id) == "New Chat"):
    first_message = st.session_state.messages[0]["content"]
    new_title = first_message[:60] + "..." if len(first_message) > 60 else first_message
    for chat in st.session_state.chats:
        if chat["id"] == st.session_state.current_chat_id:
            chat["title"] = new_title
            break
    save_current_chat()

# ----------------------------------------------------------

st.set_page_config(page_title="RightLawyers Nevada Divorce Assistant", layout="centered")
st.title("🗽 RightLawyers")

st.markdown("""
Welcome! I'm here to provide **general information** about Nevada divorce laws and help guide you through the process.
""")

# === Sidebar: Chat History List ===
with st.sidebar:
    st.markdown("### Your Chats")

    if st.button("✨ New Chat", use_container_width=True, type="primary"):
        create_new_chat()

    st.markdown("---")

    for chat in st.session_state.chats:
        is_active = chat["id"] == st.session_state.current_chat_id
        title_display = chat["title"]

        col1, col2 = st.columns([0.85, 0.15])

        with col1:
            if is_active:
                st.markdown(f"**➜ {title_display}**")
            else:
                if st.button(title_display, key=f"switch_{chat['id']}", use_container_width=True):
                    switch_to_chat(chat["id"])

        with col2:
            if not is_active:  # Don't allow delete on active chat
                if st.button("🗑️", key=f"del_{chat['id']}"):
                    delete_chat(chat["id"])

    st.markdown("---")
    st.caption("Click a chat to switch • 🗑️ to delete")

# === Main Chat Interface ===
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "citations" in message and message["citations"]:
            with st.expander("Sources/Citations"):
                for cit in message["citations"]:
                    st.caption(cit)

# === Chat Input ===
if prompt := st.chat_input("Ask me about Nevada divorce laws, procedures, or attorney matching..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_current_chat()

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        citation_placeholder = st.empty()

        with st.spinner("Thinking..."):
            answer, citations = get_divorce_assistant_response(st.session_state.messages)

            response_placeholder.markdown(answer)

            if citations:
                with citation_placeholder.expander("Citations"):
                    for cit in citations:
                        st.caption(cit)

        msg_dict = {"role": "assistant", "content": answer}
        if citations:
            msg_dict["citations"] = citations
        st.session_state.messages.append(msg_dict)
        save_current_chat()

st.caption("Developed by RightLawyers")