import model_lab

def test_benchmark_catalog_covers_project_stack():
    ids={x["id"] for x in model_lab.benchmark_catalog()}
    assert {"typescript-implementation","react-component-design","api-contract","sql-design","docker-build-design","git-workflow"} <= ids
