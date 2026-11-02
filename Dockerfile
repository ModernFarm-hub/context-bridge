# Runs the stdio MCP server with an empty library, e.g. for MCP directory checks.
# Real use imports private exports on the host; see README.md.
FROM python:3.12-slim
COPY . /src
RUN pip install --no-cache-dir /src && rm -rf /src && useradd --create-home app
USER app
ENV CONTEXT_BRIDGE_HOME=/home/app/context-bridge
ENTRYPOINT ["context-bridge", "mcp"]
