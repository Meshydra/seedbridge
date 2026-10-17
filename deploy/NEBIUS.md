# Deploying SeedBridge on Nebius

The models already run on **Nebius Token Factory**, so the web app itself only needs a small CPU container.
It runs as a **Nebius Serverless Endpoint**, and the matching and re-review work runs as a **Nebius Serverless Job**.

Commands follow the Nebius docs ([endpoints](https://docs.nebius.com/serverless/endpoints/manage),
[jobs](https://docs.nebius.com/serverless/quickstart/jobs)). Check `nebius ai endpoint create --help` for flags added since.

## 1. Build and push the image

```bash
docker build -t <registry>/seedbridge:latest .
docker push <registry>/seedbridge:latest
```

Use Nebius Container Registry or any registry the endpoint can pull from. For a private registry, add the registry credentials when you create the endpoint.

## 2. Create the endpoint

```bash
nebius ai endpoint create \
  --name seedbridge \
  --image <registry>/seedbridge:latest \
  --container-port 8000 \
  --platform cpu-d3 \
  --preset 4vcpu-16gb \
  --env NEBIUS_API_KEY=<token-factory-key> \
  --env TAVILY_API_KEY=<tavily-key> \
  --env SEEDBRIDGE_SECRET=<long-random-string> \
  --public
```

`SEEDBRIDGE_SEED_ON_START=1` is set in the Dockerfile, so a fresh container loads the demo founders, funders and programs and reviews them with the live models. Judges then land on a populated app.

Get the HTTPS URL:

```bash
nebius ai endpoint get <endpoint_ID> --format json \
  | jq -r '.status.public_endpoints[] | select(startswith("https://"))' | head -1
```

Leave endpoint auth off for the public demo. The app has its own logins.

## 3. Background matching as a job

```bash
nebius ai create \
  --type job \
  --name seedbridge-rematch \
  --image <registry>/seedbridge:latest \
  --container-command python \
  --args "-m app.jobs rematch" \
  --platform cpu-d3 \
  --preset 4vcpu-16gb \
  --timeout 1h
```

`python -m app.jobs pending` re-reviews any ideas left unfinished, for example after a restart.

> SQLite lives in `/data` inside the container. That's fine for the hackathon demo, which re-seeds on start. For production, mount a volume (`--volume`) or swap `app/db.py` to Postgres.
