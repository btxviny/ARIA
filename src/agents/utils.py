import os 
import re
import sqlite3
import subprocess
import pandas as pd

from langchain_core.messages import AIMessage, HumanMessage

SCRIPT_PATH = "./coding/visualization.py"

def get_table_info(df: pd.DataFrame, max_cardinality: int = 20) -> dict:
    """
    Generate a metadata dictionary for a DataFrame with columns as keys 
    and unique values as values, filtered by cardinality threshold.
    If a column has more unique values than the threshold, it will be marked as 'too many values'.
    
    :param df: DataFrame to analyze.
    :param max_cardinality: Maximum number of unique values allowed for a column to list unique values.
    :return: Dictionary with column names as keys and unique values as lists or a placeholder string.
    """
    metadata = {}
    for col in df.columns:
        unique_values = df[col].dropna().unique()
        if len(unique_values) <= max_cardinality:
            metadata[col] = unique_values.tolist()
        else:
            metadata[col] = "too many values"
    return metadata


def load_resources():
    job_posts_df = pd.read_json('./data/job_posts.json')
    news_df = pd.read_json('./data/news.json')
    if not os.path.exists('./db/bigfour.db'):
        connection = sqlite3.connect('./db/bigfour.db')
        job_posts_df.to_sql('job_posts', connection, if_exists='replace', index=False)
        news_df.to_sql('news_articles', connection, if_exists='replace', index=False)
    #table metadata
    job_posts_df_metadata = get_table_info(job_posts_df)
    news_df_metadata = get_table_info(news_df)
    return job_posts_df_metadata, news_df_metadata


def execute_sql_query(sql_query: str, database_path: str = './db/bigfour.db') -> dict:
        try:
            sql_query = re.sub(r"^```(?:sql)?\n?|```$", "", sql_query, flags=re.MULTILINE)
            with sqlite3.connect(database_path) as conn:
                result_df = pd.read_sql_query(sql_query, conn).to_dict(orient='records')
                return {"query_result": result_df, "query": sql_query}
        except Exception as e:
            return {"error": f"Error executing query: {sql_query}. Error: {e}"}


def format_history(messages: list) -> str:
    formated_history = []
    for message in messages:
        if isinstance(message, HumanMessage):
            formated_history.append(f"User: {message.content}")
        elif isinstance(message, AIMessage):
            formated_history.append(f"Assistant: {message.content}")
    return "\n".join(formated_history)

def process_and_run_script(script: str) -> str:
    script =  re.sub(r"^```(?:python)?\n?|```$", "", script, flags=re.MULTILINE)
    with open(SCRIPT_PATH, "w") as f:
        f.write(script)
    subprocess.run(["python", SCRIPT_PATH])