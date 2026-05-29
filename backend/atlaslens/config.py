from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "atlaslens"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    encryption_key: str = ""

    atlassian_site: str = ""
    atlassian_cloud_id: str = ""
    atlassian_org_id: str = ""
    atlassian_email: str = ""
    jira_api_token: str = ""
    confluence_api_token: str = ""
    bitbucket_api_token: str = ""
    atlassian_oauth_client_id: str = ""
    atlassian_oauth_client_secret: str = ""

    bitbucket_workspace: str = ""

    cors_origins: list[str] = ["http://localhost:5173"]

    ingest_interval_minutes: int = 15
    report_output_dir: str = "reports"

    model_config = {"env_prefix": "ATLASLENS_", "env_file": ".env"}


settings = Settings()
