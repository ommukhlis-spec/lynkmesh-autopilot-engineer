from __future__ import annotations

from pathlib import Path


SERVICE_BASELINE = '''<?php

require_once __DIR__ . '/../Models/TransactionModel.php';

class TransactionService
{
    private TransactionModel $transactionModel;

    public function __construct()
    {
        $this->transactionModel = new TransactionModel();
    }

    public function getMonthlySummary(string $month): array
    {
        // Intentional bug #1 for the hackathon demo:
        // The model method is spelled getMonthlySummary(), but this calls getMontlySummary().
        return $this->transactionModel->getMontlySummary($month);
    }
}
'''


MODEL_BASELINE = '''<?php

class TransactionModel
{
    public function getMonthlySummary(string $month): array
    {
        return [
            'transaction_count' => 3,
            // Intentional bug #2 for the self-correction demo:
            // The test expects total_amount, but the model returns amount_total.
            'amount_total' => 1250000,
            'currency' => 'IDR',
        ];
    }
}
'''


def reset_demo_app(demo_app_dir: Path) -> list[str]:
    """Reset the demo app to a known broken state before every agent run.

    This makes the hackathon demo deterministic. The agent can be run repeatedly
    and will always start from the same two-bug scenario:
    1. Undefined method call in TransactionService.
    2. Wrong summary key in TransactionModel, discovered after the first fix.
    """
    targets = {
        demo_app_dir / "app" / "Services" / "TransactionService.php": SERVICE_BASELINE,
        demo_app_dir / "app" / "Models" / "TransactionModel.php": MODEL_BASELINE,
    }
    changed: list[str] = []
    for path, content in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        changed.append(str(path.relative_to(demo_app_dir.parent)).replace("\\", "/"))
    return changed
