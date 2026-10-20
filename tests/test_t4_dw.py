
import subprocess

import pytest


EXPECTED_COUNTS = {
    "dim_customer": 96096,
    "dim_date": 1314,
    "dim_geo": 19011,
    "dim_product": 32951,
    "dim_seller": 3095,
    "fact_order": 99441,
    "fact_order_item": 112650,
    "fact_payment": 103886,
    "fact_review": 98673,
}


def run_sql(sql):
    command = [
        "docker", "compose", "exec", "-T", "postgres",
        "psql", "-X", "-A", "-t",
        "-v", "ON_ERROR_STOP=1",
        "-U", "olist", "-d", "olist",
        "-c", sql,
    ]

    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"SQL execution failed.\n"
            f"SQL:\n{sql}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
         

    return result.stdout.strip()


@pytest.mark.parametrize(
    ("table_name", "expected_count"),
    EXPECTED_COUNTS.items(),
)
def test_dw_table_row_counts(table_name, expected_count):
    actual = int(
        run_sql(f"SELECT COUNT(*) FROM dw.{table_name}")
    )
    assert actual == expected_count


def test_fact_order_item_has_no_duplicate_grain():
    duplicates = int(
        run_sql("""
            SELECT COUNT(*)
            FROM (
                SELECT order_id, order_item_id
                FROM dw.fact_order_item
                GROUP BY order_id, order_item_id
                HAVING COUNT(*) > 1
            ) AS d
        """)
    )
    assert duplicates == 0


def test_fact_review_has_one_row_per_order():
    duplicates = int(
        run_sql("""
            SELECT COUNT(*)
            FROM (
                SELECT order_id
                FROM dw.fact_review
                GROUP BY order_id
                HAVING COUNT(*) > 1
            ) AS d
        """)
    )
    assert duplicates == 0


def test_all_foreign_keys_are_validated():
    unvalidated = int(
        run_sql("""
            SELECT COUNT(*)
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE n.nspname = 'dw'
              AND c.contype = 'f'
              AND NOT c.convalidated
        """)
    )
    assert unvalidated == 0


def test_dw_has_expected_primary_and_foreign_keys():
    primary_keys = int(
        run_sql("""
            SELECT COUNT(*)
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE n.nspname = 'dw'
              AND c.contype = 'p'
        """)
    )
    foreign_keys = int(
        run_sql("""
            SELECT COUNT(*)
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE n.nspname = 'dw'
              AND c.contype = 'f'
        """)
    )

    assert primary_keys == 9
    assert foreign_keys == 18


def test_no_invalid_is_late_rows():
    invalid = int(
        run_sql("""
            SELECT COUNT(*)
            FROM dw.fact_order
            WHERE is_late IS NOT NULL
              AND (
                  order_status <> 'delivered'
                  OR order_delivered_customer_date IS NULL
                  OR order_estimated_delivery_date IS NULL
              )
        """)
    )
    assert invalid == 0
