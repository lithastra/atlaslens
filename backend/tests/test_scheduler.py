from unittest.mock import AsyncMock, patch

import pytest

from tests.mock_db import MockDB


class TestScheduler:
    @pytest.mark.asyncio
    async def test_run_all_audit_no_credentials(self) -> None:
        from atlaslens.ingest.scheduler import run_all_audit

        db = MockDB()
        with patch("atlaslens.ingest.scheduler.settings") as mock_settings:
            mock_settings.atlassian_site = ""
            mock_settings.atlassian_cloud_id = ""
            mock_settings.jira_api_token = ""
            mock_settings.confluence_api_token = ""
            mock_settings.bitbucket_api_token = ""
            mock_settings.atlassian_email = ""
            mock_settings.atlassian_org_id = ""
            results = await run_all_audit(db)  # type: ignore[arg-type]

        assert "bitbucket:audit" in results

    @pytest.mark.asyncio
    async def test_run_all_activity_no_credentials(self) -> None:
        from atlaslens.ingest.scheduler import run_all_activity

        db = MockDB()
        with patch("atlaslens.ingest.scheduler.settings") as mock_settings:
            mock_settings.atlassian_site = ""
            mock_settings.atlassian_cloud_id = ""
            mock_settings.jira_api_token = ""
            mock_settings.confluence_api_token = ""
            mock_settings.bitbucket_api_token = ""
            mock_settings.atlassian_email = ""
            mock_settings.atlassian_org_id = ""
            mock_settings.bitbucket_workspace = ""
            results = await run_all_activity(db)  # type: ignore[arg-type]

        assert results == {}

    @pytest.mark.asyncio
    async def test_run_all_combines_audit_and_activity(self) -> None:
        from atlaslens.ingest.scheduler import run_all

        db = MockDB()
        with (
            patch(
                "atlaslens.ingest.scheduler.run_all_audit",
                new_callable=AsyncMock,
                return_value={"jira:audit": 5},
            ),
            patch(
                "atlaslens.ingest.scheduler.run_all_activity",
                new_callable=AsyncMock,
                return_value={"jira:activity": 3},
            ),
            patch(
                "atlaslens.ingest.scheduler.run_group_sync",
                new_callable=AsyncMock,
                return_value={"groups:sync": 2},
            ),
        ):
            results = await run_all(db)  # type: ignore[arg-type]

        assert results == {
            "jira:audit": 5,
            "jira:activity": 3,
            "groups:sync": 2,
        }

    @pytest.mark.asyncio
    async def test_run_all_activity_with_credentials(self) -> None:
        from atlaslens.ingest.scheduler import run_all_activity

        db = MockDB()
        with (
            patch("atlaslens.ingest.scheduler.settings") as mock_settings,
            patch(
                "atlaslens.ingest.scheduler.run_connector",
                new_callable=AsyncMock,
                return_value=10,
            ) as mock_run,
        ):
            mock_settings.atlassian_site = "mysite"
            mock_settings.atlassian_cloud_id = "test-cloud-id"
            mock_settings.jira_api_token = "jira-tok"
            mock_settings.confluence_api_token = "conf-tok"
            mock_settings.bitbucket_api_token = "bb-tok"
            mock_settings.atlassian_email = "a@b.com"
            mock_settings.bitbucket_workspace = "ws"
            results = await run_all_activity(db)  # type: ignore[arg-type]

        assert results == {
            "jira:activity": 10,
            "confluence:activity": 10,
            "jsm:activity": 10,
            "bitbucket:activity": 10,
        }
        assert mock_run.call_count == 4

    @pytest.mark.asyncio
    async def test_failing_connector_isolated(self) -> None:
        from atlaslens.ingest.scheduler import run_all_activity

        call_count = 0

        async def mock_run(db, connector, pipeline):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if connector.product == "jira":
                raise RuntimeError("Jira down")
            return 5

        db = MockDB()
        with (
            patch("atlaslens.ingest.scheduler.settings") as mock_settings,
            patch(
                "atlaslens.ingest.scheduler.run_connector",
                side_effect=mock_run,
            ),
        ):
            mock_settings.atlassian_site = "mysite"
            mock_settings.atlassian_cloud_id = "test-cloud-id"
            mock_settings.jira_api_token = "jira-tok"
            mock_settings.confluence_api_token = "conf-tok"
            mock_settings.bitbucket_api_token = "bb-tok"
            mock_settings.atlassian_email = "a@b.com"
            mock_settings.bitbucket_workspace = ""
            results = await run_all_activity(db)  # type: ignore[arg-type]

        assert call_count == 3
        assert "error" in str(results["jira:activity"])
        assert results["confluence:activity"] == 5
        assert results["jsm:activity"] == 5
