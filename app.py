import streamlit as st
import requests
import time

from ui.display_utils.utils import sample_questions, display_title



# API interaction functions
def post_question(prompt):
    url = "http://localhost:5000/question/"
    data = {"prompt": prompt}
    response = requests.post(url, json=data)
    return response.json().get("task_id")

def get_answer(task_id):
    url = f"http://localhost:5000/answer/{task_id}"
    response = requests.get(url)
    return response.json()

def stream_answer(answer):
    for word in answer.split():
        yield word + " "
        time.sleep(0.02)


def main():
    with open("ui/style.css") as file:
        st.markdown(f"<style>{file.read()}", unsafe_allow_html=True)
    display_title()
    # Sidebar content
    with st.sidebar:
        st.sidebar.title("Multi-Agent Chatbot")
        st.write("A general-purpose chatbot powered by a multi-agent LangGraph architecture.")
    
    # Use the Quick Questions section
    selected_question = sample_questions()
    if selected_question:
        st.session_state.selected_question = selected_question

    # Initialize session state
    if "task_id" not in st.session_state:
        st.session_state.task_id = None
    if "display_history" not in st.session_state:
        st.session_state.display_history = []
    if "selected_question" not in st.session_state:
        st.session_state.selected_question = None
    if "waiting_for_response" not in st.session_state:
        st.session_state.waiting_for_response = False

    # Create a container for chat history
    chat_container = st.container()

    # Get user input
    user_input = st.chat_input("Enter your message:", disabled=st.session_state.waiting_for_response) or st.session_state.selected_question

    # Display chat history in the container
    with chat_container:
        for message in st.session_state.display_history:
            match message["role"]:
                case "user":
                    with st.chat_message("user"):
                        st.write(message["content"])
                case "assistant":
                    with st.chat_message("assistant"):
                        st.write(message["content"])

    # Handle new user input
    if user_input and not st.session_state.waiting_for_response:
        # Immediately add user message to display history
        st.session_state.display_history.append({"role": "user", "content": user_input})
        st.session_state.selected_question = None
        st.session_state.task_id = post_question(user_input)
        st.session_state.waiting_for_response = True
        st.rerun()  # Rerun to show the user message immediately

    # Handle response generation
    if st.session_state.task_id and st.session_state.waiting_for_response:
        with st.spinner("Generating Response..."):
            status = "Pending"
            timeout = 120
            start_time = time.time()

            while status != "Completed" and time.time() - start_time < timeout:
                result = get_answer(st.session_state.task_id)
                status = result.get("status")
                time.sleep(0.7)

            if status == "Completed" and result["result"].get("answer") is not None:
                answer = result["result"].get("answer")
                st.session_state.display_history.append({
                    "role": "assistant",
                    "content": answer
                })
                st.session_state.task_id = None
                st.session_state.waiting_for_response = False

            elif status != "Completed":
                st.error("The response generation took too long. Please try again.")
                st.session_state.waiting_for_response = False
                st.session_state.task_id = None
            else:
                st.error("No answer was generated. Please try again.")
                st.session_state.waiting_for_response = False
                st.session_state.task_id = None
        st.rerun()

if __name__ == "__main__":
    main()