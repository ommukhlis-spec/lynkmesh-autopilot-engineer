<?php

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
        return $this->transactionModel->getMonthlySummary($month);
    }
}
