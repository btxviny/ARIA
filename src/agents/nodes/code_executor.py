import ast
import mimetypes
import re
import subprocess
import textwrap
import uuid
from pathlib import Path
from typing import Any, Dict

from loguru import logger

from src.agents.agents import code_executor_agent
from src.agents.state import GraphState
from src.config import CODE_OUTPUTS_DIR

OUTPUT_BASE = Path(CODE_OUTPUTS_DIR)
MAX_SUPERVISOR_RETRIES = 3


def _clean_code(code: str) -> str:
    """Strip markdown fences, dedent, and normalize to spaces-only indentation."""
    code = re.sub(r"^```[a-zA-Z]*\n", "", code.strip(), flags=re.MULTILINE)
    code = re.sub(r"\n?```$", "", code.strip(), flags=re.MULTILINE)
    code = code.replace("\t", "    ")
    code = textwrap.dedent(code)
    return code.strip()


def code_executor_node(state: GraphState) -> Dict[str, Any]:
    attempt_number = state.get("code_attempt", 0) + 1
    # Reuse the same run directory across retries so generated files persist
    run_id = state.get("code_run_id") or str(uuid.uuid4())
    output_dir = OUTPUT_BASE / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    data_files = state.get("data_files", [])
    data_files_context = (
        "\n".join(f"  - {f['filename']} -> path: {f['path']}" for f in data_files)
        if data_files else "None"
    )

    # Pass the previous attempt's error so the LLM can fix it
    previous_error = state.get("code_error", "")

    inputs = {
        "question": state.get("question", ""),
        "plan": state.get("plan", ""),
        "search_results": state.get("search_results", ""),
        "rag_context": state.get("rag_context", ""),
        "data_files": data_files_context,
        "previous_error": previous_error,
    }

    result = code_executor_agent.invoke(inputs)
    code = _clean_code(result.code)
    description = result.description
    stdout, stderr = "", ""
    error = ""

    try:
        ast.parse(code)
    except SyntaxError as e:
        error = f"SyntaxError: {e}"
        logger.warning(f"Code executor [{run_id}] attempt {attempt_number} syntax error: {e}")

    if not error:
        # Clear artefacts from a previous failed attempt
        for f in output_dir.iterdir():
            if f.name != "script.py":
                f.unlink(missing_ok=True)

        script_path = output_dir / "script.py"
        script_path.write_text(code, encoding="utf-8")
        logger.info(f"Code executor [{run_id}] attempt {attempt_number}: {description}")

        try:
            proc = subprocess.run(
                ["python", str(script_path.resolve())],
                cwd=str(output_dir.resolve()),
                capture_output=True,
                text=True,
                timeout=60,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            if proc.returncode != 0 or stderr:
                error = f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}\nReturn code: {proc.returncode}".strip()
                logger.warning(
                    f"Code executor [{run_id}] attempt {attempt_number} runtime error (rc={proc.returncode}): {stderr[:300] or stdout[:300]}"
                )
            else:
                logger.info(f"Code executor [{run_id}] succeeded on attempt {attempt_number}")
        except subprocess.TimeoutExpired:
            error = "Code execution timed out after 60 seconds."
            logger.warning(f"Code executor [{run_id}] attempt {attempt_number} timed out.")
        except Exception as e:
            error = str(e)
            logger.warning(f"Code executor [{run_id}] attempt {attempt_number} subprocess error: {e}")

    if stdout:
        logger.info(f"Code executor [{run_id}] stdout: {stdout[:500]}")
    if stderr:
        logger.warning(f"Code executor [{run_id}] stderr: {stderr[:300]}")
    if error and attempt_number >= MAX_SUPERVISOR_RETRIES:
        logger.error(f"Code executor [{run_id}] failed all {MAX_SUPERVISOR_RETRIES} supervisor retries")

    files = []
    if not error:
        for f in sorted(output_dir.iterdir()):
            if f.name == "script.py":
                continue
            mime_type, _ = mimetypes.guess_type(f.name)
            files.append({
                "filename": f.name,
                "mime_type": mime_type or "application/octet-stream",
            })

    code_result = f"Description: {description}\n\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}".strip()

    return {
        "code_result": code_result,
        "code_error": error,
        "code_files": files,
        "code_run_id": run_id,
        "code_attempt": attempt_number,
        "executed_agents": state.get("executed_agents", []) + ["code_executor"],
    }
