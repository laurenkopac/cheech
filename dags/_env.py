"""
Airflow runs in its own conda env, isolated from `cheech` -- Airflow's
dependency tree conflicts with the pandas<2.0/xgboost pins nfl_data_py
needs (see CLAUDE.md's environment-setup notes). Task logic that needs
`cheech`'s packages (nfl_data_py, xgboost, anthropic, feedparser, ...)
lives in dags/tasks/ and runs via this helper instead of being imported
directly into the Airflow process.
"""
import subprocess
from pathlib import Path

CHEECH_CONDA_ENV = "cheech"
REPO_ROOT = Path(__file__).resolve().parent.parent


def run_in_cheech_env(module: str, func: str) -> None:
    """Run `func` from dags/tasks/{module}.py inside the cheech conda env."""
    subprocess.run(
        ["conda", "run", "-n", CHEECH_CONDA_ENV, "--no-capture-output",
         "python", "-m", f"dags.tasks.{module}", func],
        check=True,
        cwd=REPO_ROOT,
    )
