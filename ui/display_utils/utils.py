import streamlit as st
import random

def display_title():
    st.markdown("""
    <style>
    /* Title styling */
    .app-title {
        font-size: 36px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 40px;
        font-family: 'Helvetica', sans-serif;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);  /* Subtle shadow for depth */
    }
    </style>
    <div class="app-title">🤖 Competitive Intelligence Assistant</div>
    """, unsafe_allow_html=True)


def sample_questions():
    questions = [
        {"text": "Make a pie chart of sentiment distribution", "key": "make a pie chart of the distribution of news article sentiment."},
        {"text": "Update pie chart colors", "key": "Change the colors of the pie to black, yellow and white"},
        {"text": "Tech-related job posts comparison", "key": "Which company made the most 'tech' related job posts?"},
        {"text": "Which company is looking to hire the most machine learning engineers?", "key": "which company is looking to hire the most machine learning engineers?"},
        {"text": "What does EY vs Deloitte look for in a 'AI Consultant/Engineer'?", "key": "What does EY vs Deloitte look for in a 'AI Consultant/Engineer'?"},
        {"text": "Weather in Berlin", "key": "What is the weather like in Berlin?"},
        {"text": "Say Hello", "key": "Hello"},
        
    ]
    
    st.markdown("### Quick Questions")
    selected_question = None
    cols = st.columns(3)  # Create three columns for better layout

    for idx, question in enumerate(questions):  # Display the first 6 questions
        with st.container():
            with cols[idx % 3]:  # Distribute questions across columns
                if st.button(question["text"]):
                    selected_question = question["key"]
    
    return selected_question



