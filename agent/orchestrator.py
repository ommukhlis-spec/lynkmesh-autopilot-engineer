from __future__ import annotations

from .config import AgentConfig
from .demo_reset import reset_demo_app
from .lynkmesh_adapter import LynkMeshAdapter
from .patch_engine import PatchEngine
from .qwen_client import QwenClient
from .report_writer import ReportWriter
from .test_runner import TestRunner


class AutopilotOrchestrator:
    def __init__(self, config: AgentConfig, mock_qwen: bool = True) -> None:
        self.config = config
        self.lynkmesh = LynkMeshAdapter(config.context_json)
        self.qwen = QwenClient(mock=mock_qwen, root_dir=config.root_dir)
        self.patch_engine = PatchEngine(config)
        self.test_runner = TestRunner(config.demo_app_dir)
        self.report_writer = ReportWriter(config.runs_dir)

    def run(self) -> dict:
        reset_files = reset_demo_app(self.config.demo_app_dir)
        print(f"[DEMO RESET] restored broken baseline files={len(reset_files)}")

        failure_log = self.config.failure_log.read_text(encoding="utf-8")

        test_before = self.test_runner.run()
        print(f"[TEST BEFORE] {'passed' if test_before.passed else 'failed'}")

        context = self.lynkmesh.get_context_for_failure(failure_log)
        print("[LYNKMESH CONTEXT] loaded")

        retry_feedback = None
        patch_plan = None
        changed_files_all: list[str] = []
        test_after = None
        attempts: list[dict] = []

        for attempt_index in range(self.config.max_retries + 1):
            attempt_number = attempt_index + 1
            patch_plan = self.qwen.generate_patch_plan(
                failure_log,
                context,
                retry_feedback=retry_feedback,
            )
            patch_plan["attempt"] = attempt_number
            print(f"[QWEN PATCH] generated attempt={attempt_number}")

            changed_files = self.patch_engine.apply_patch_plan(patch_plan)
            changed_files_all.extend(changed_files)
            print(f"[PATCH] applied attempt={attempt_number} files={len(changed_files)}")

            test_after = self.test_runner.run()
            print(f"[TEST AFTER attempt={attempt_number}] {'passed' if test_after.passed else 'failed'}")

            attempts.append(
                {
                    "attempt": attempt_number,
                    "patch_plan": patch_plan,
                    "changed_files": changed_files,
                    "test_result": {
                        "passed": test_after.passed,
                        "returncode": test_after.returncode,
                        "output": test_after.combined_output,
                    },
                    "retry_feedback_used": retry_feedback,
                }
            )

            if test_after.passed:
                break

            retry_feedback = test_after.combined_output
            print("[SELF-CORRECTION] starting retry")
        else:
            print("[SELF-CORRECTION] max retries exhausted")

        unique_changed_files = list(dict.fromkeys(changed_files_all))
        payload = {
            "status": "passed" if test_after and test_after.passed else "failed",
            "qwen_mode": "mock" if self.qwen.mock else "real",
            "qwen_model": self.qwen.model,
            "reset_files": reset_files,
            "context": context,
            "attempts": attempts,
            "patch_plan": patch_plan or {},
            "changed_files": unique_changed_files,
            "test_before": {
                "passed": test_before.passed,
                "returncode": test_before.returncode,
                "output": test_before.combined_output,
            },
            "test_after": {
                "passed": test_after.passed if test_after else False,
                "returncode": test_after.returncode if test_after else -1,
                "output": test_after.combined_output if test_after else "No test result.",
            },
        }

        report_path = self.report_writer.write(payload)
        print(f"[REPORT] {report_path.relative_to(self.config.root_dir)}")
        return payload
