import subprocess
import sys


def test_workflow_imports_in_a_fresh_python_process() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import boostprompt.graph.workflow"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
