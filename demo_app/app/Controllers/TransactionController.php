<?php

require_once __DIR__ . '/../Services/TransactionService.php';

class TransactionController
{
    private TransactionService $service;

    public function __construct()
    {
        $this->service = new TransactionService();
    }

    public function index(string $month): array
    {
        return [
            'route' => 'GET /transactions',
            'month' => $month,
            'summary' => $this->service->getMonthlySummary($month),
        ];
    }
}
