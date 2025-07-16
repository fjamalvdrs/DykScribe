# Secure Secrets Management for Streamlit Deployment

## Using Streamlit Secrets

1. Create a `.streamlit/secrets.toml` file in your project root (create the `.streamlit` folder if it doesn't exist).
2. Add your credentials like this:

```toml
db_server = "your_server.database.windows.net"
db_user = "your_db_user"
db_password = "your_db_password"
db_name = "PowerAppsDatabase"
openai_api_key = "sk-..."
```

3. On Streamlit Cloud, add these secrets via the web UI under **App settings > Secrets**.

## Using Environment Variables (for local dev)

Set the following environment variables in your shell or `.env` file:

- `DB_SERVER`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `OPENAI_API_KEY`

The app will automatically use Streamlit secrets if available, otherwise it will fall back to environment variables.

## Why?
- **Never hardcode secrets in your code.**
- This approach keeps your credentials safe for both local and cloud deployments. 