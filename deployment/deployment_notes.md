# Deployment Notes

Use systemd to run uvicorn on localhost and Nginx as the public reverse proxy. Keep the SQLite database backed up before each ingestion update. For HROM, rebuild with the same script using `--dataset HROM` or a versioned replacement workflow. Roll back by restoring the previous SQLite file and restarting the service.
