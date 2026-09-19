from github_sync import GitHubSync


def test_github_sync_status_without_configuration():
    sync = GitHubSync(repo="", branch="main", token="", enabled=True)
    status = sync.status()
    assert status["configured"] is False
    assert status["auth"] is False


def test_github_sync_rejects_invalid_paths():
    sync = GitHubSync(repo="owner/repo", branch="main", token="x")
    import asyncio
    result = asyncio.run(sync.sync_file("../secret.txt", "nope"))
    assert result["skipped"] is True
