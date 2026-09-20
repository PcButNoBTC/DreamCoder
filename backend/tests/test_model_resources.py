import model_lab

def test_model_lab_resource_bounds():
    assert model_lab._BENCHMARK_CONCURRENCY >= 1
    assert model_lab._BENCHMARK_TIMEOUT >= 10
