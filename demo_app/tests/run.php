<?php

require_once __DIR__ . '/../app/Controllers/TransactionController.php';

function assert_equals($expected, $actual, string $label): void
{
    if ($expected !== $actual) {
        throw new Exception("Assertion failed for {$label}. Expected " . var_export($expected, true) . ", got " . var_export($actual, true));
    }
}

try {
    $controller = new TransactionController();
    $response = $controller->index('2026-06');

    assert_equals('GET /transactions', $response['route'], 'route');
    assert_equals('2026-06', $response['month'], 'month');
    assert_equals(3, $response['summary']['transaction_count'], 'transaction_count');
    assert_equals(1250000, $response['summary']['total_amount'], 'total_amount');

    echo "PASS: Transaction summary route works.\n";
    exit(0);
} catch (Throwable $e) {
    fwrite(STDERR, "FAIL: " . $e->getMessage() . "\n");
    exit(1);
}
