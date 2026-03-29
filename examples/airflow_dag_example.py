"""Example Airflow DAG using SraoshaOperator."""

from datetime import datetime

# Requires: pip install sraosha[airflow]
from airflow import DAG
from airflow.operators.python import PythonOperator

from sraosha.hooks.airflow.operator import SraoshaOperator

default_args = {
    "owner": "data-platform",
    "start_date": datetime(2024, 1, 1),
    "retries": 0,
}

with DAG(
    dag_id="orders_pipeline_with_contract",
    default_args=default_args,
    schedule="@hourly",
    catchup=False,
) as dag:

    def load_orders():
        print("Loading orders data...")

    def transform_orders():
        print("Transforming orders data...")

    load_task = PythonOperator(task_id="load_orders", python_callable=load_orders)

    validate_contract = SraoshaOperator(
        task_id="validate_orders_contract",
        contract_path="contracts/orders.yaml",
        enforcement_mode="block",
        server="production",
    )

    transform_task = PythonOperator(task_id="transform_orders", python_callable=transform_orders)

    load_task >> validate_contract >> transform_task
