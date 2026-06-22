import importlib


def test_future_phase_modules_are_importable():
    for module_name in [
        "fraud_demo.generate_data",
        "fraud_demo.ingest",
        "fraud_demo.profile",
        "fraud_demo.features",
        "fraud_demo.scoring",
        "fraud_demo.graph_builder",
        "fraud_demo.clusters",
        "fraud_demo.alerts",
        "fraud_demo.okf_exporter",
        "fraud_demo.okf_validator",
        "fraud_demo.monitoring",
        "fraud_demo.manifests",
        "fraud_demo.privacy",
    ]:
        assert importlib.import_module(module_name)
