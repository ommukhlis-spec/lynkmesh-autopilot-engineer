<?php

class TransactionModel
{
    public function getMonthlySummary(string $month): array
    {
        return [
            'transaction_count' => 3,
            // Intentional bug #2 for the self-correction demo:
            // The test expects total_amount, but the model returns amount_total.
            'total_amount' => 1250000,
            'currency' => 'IDR',
        ];
    }
}
