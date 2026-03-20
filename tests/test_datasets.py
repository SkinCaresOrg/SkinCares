from importlib import import_module


def test_datasets_package_importable():
    module = import_module("skincarelib.datasets")
    assert module is not None
