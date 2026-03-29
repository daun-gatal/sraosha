"""Airflow provider metadata for Sraosha."""


def get_provider_info() -> dict:
    return {
        "package-name": "sraosha",
        "name": "Sraosha",
        "description": "Enforcement and governance runtime for data contracts",
        "connection-types": [],
        "extra-links": [],
        "operators": [
            {
                "integration-name": "Sraosha",
                "python-modules": ["sraosha.hooks.airflow.operator"],
            }
        ],
        "versions": ["0.1.0"],
    }
