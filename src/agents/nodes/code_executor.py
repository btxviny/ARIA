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
MAX_CODEGEN_RETRIES = 3


def _clean_code(code: str) -> str:
    """Strip markdown fences, dedent, and normalize to spaces-only indentation."""
    code = re.sub(r"^```[a-zA-Z]*\n", "", code.strip(), flags=re.MULTILINE)
    code = re.sub(r"\n?```$", "", code.strip(), flags=re.MULTILINE)
    code = code.replace("\t", "    ")
    code = textwrap.dedent(code)
    return code.strip()


def code_executor_node(state: GraphState) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    output_dir = OUTPUT_BASE / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    data_files = state.get("data_files", [])
    data_files_context = (
        "\n".join(f"  - {f['filename']} -> path: {f['path']}" for f in data_files)
        if data_files else "None"
    )

    base_inputs = {
        "question": state.get("question", ""),
        "plan": state.get("plan", ""),
        "search_results": state.get("search_results", ""),
        "rag_context": state.get("rag_context", ""),
        "data_files": data_files_context,
    }

    last_error = ""
    description = ""
    stdout, stderr = "", ""
    timed_out = False

    for attempt in range(1, MAX_CODEGEN_RETRIES + 1):
        inputs = dict(base_inputs)
        if last_error:
            inputs["question"] = (
                f"{base_inputs['question']}\n\n"
                f"Attempt {attempt - 1} failed with this error:\n{last_error}\n"
                f"Fix the issue and return corrected Python code."
            )

        result = code_executor_agent.invoke(inputs)
        code = _clean_code(result.code)
        description = result.description

        try:
            ast.parse(code)
        except SyntaxError as e:
            last_error = f"SyntaxError: {e}"
            logger.warning(f"Code executor [{run_id}] attempt {attempt} syntax error: {e}")
            continue

        # Clear any artefacts left by a previous failed attempt
        for f in output_dir.iterdir():
            if f.name != "script.py":
                f.unlink(missing_ok=True)

        script_path = output_dir / "script.py"
        script_path.write_text(code, encoding="utf-8")
        logger.info(f"Code executor [{run_id}] attempt {attempt}: {description}")

        stdout, stderr = "", ""
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
        except subprocess.TimeoutExpired:
            stderr = "Code execution timed out after 60 seconds."
            timed_out = True
            break
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Code executor [{run_id}] attempt {attempt} subprocess error: {e}")
            continue

        if proc.returncode != 0 and stderr:
            last_error = stderr
            logger.warning(
                f"Code executor [{run_id}] attempt {attempt} runtime error: {stderr[:300]}"
            )
            continue

        # Success
        logger.info(f"Code executor [{run_id}] succeeded on attempt {attempt}")
        last_error = ""
        break

    if last_error and not timed_out:
        logger.error(f"Code executor [{run_id}] failed all {MAX_CODEGEN_RETRIES} attempts")

    if stdout:
        logger.info(f"Code executor [{run_id}] stdout: {stdout[:500]}")
    if stderr:
        logger.warning(f"Code executor [{run_id}] stderr: {stderr[:300]}")

    files = []
    if not last_error:
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
        "code_files": files,
        "code_run_id": run_id,
        "executed_agents": state.get("executed_agents", []) + ["code_executor"],
    }
