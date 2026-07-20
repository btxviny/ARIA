import streamlit as st


def sample_questions() -> str | None:
    """Render the Quick Questions row and return the clicked question (if any)."""
    questions = [
        {"text": "Say Hello", "key": "Hello"},
        {"text": "Explain quantum computing", "key": "Can you explain quantum computing in simple terms?"},
        {"text": "Python vs JavaScript", "key": "What are the main differences between Python and JavaScript?"},
        {"text": "Write a haiku", "key": "Write a haiku about programming."},
        {"text": "Explain recursion", "key": "Explain recursion like I'm five."},
        {"text": "Benefits of exercise", "key": "What are the health benefits of regular exercise?"},
    ]

    st.markdown("### Quick Questions")
    cols = st.columns(3)
    selected = None
    for idx, q in enumerate(questions):
        with cols[idx % 3]:
            if st.button(q["text"], key=f"qq_{idx}", use_container_width=True):
                selected = q["key"]
    return selected
