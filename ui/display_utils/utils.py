import streamlit as st


def display_title():
    st.markdown("""
    <style>
    .app-title {
        font-size: 36px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 40px;
        font-family: 'Helvetica', sans-serif;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    </style>
    <div class="app-title">Multi-Agent Chatbot</div>
    """, unsafe_allow_html=True)


def sample_questions():
    questions = [
        {"text": "Say Hello", "key": "Hello"},
        {"text": "Explain quantum computing", "key": "Can you explain quantum computing in simple terms?"},
        {"text": "Python vs JavaScript", "key": "What are the main differences between Python and JavaScript?"},
        {"text": "Write a haiku", "key": "Write a haiku about programming."},
        {"text": "Explain recursion", "key": "Explain recursion like I'm five."},
        {"text": "Benefits of exercise", "key": "What are the health benefits of regular exercise?"},
    ]

    st.markdown("### Quick Questions")
    selected_question = None
    cols = st.columns(3)

    for idx, question in enumerate(questions):
        with cols[idx % 3]:
            if st.button(question["text"]):
                selected_question = question["key"]

    return selected_question
