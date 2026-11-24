# Local environment setup

The platform runs locally (OD-2). This guide sets up the container runtime and the Python workspace on a Windows machine.

## 1. Container runtime: Rancher Desktop (OD-21)

Chosen by the project owner on 2026-11-24.

| Option | Licence (from `winget show`, 2026-11-24) | Decision |
|---|---|---|
| Rancher Desktop 1.25.0 (`SUSE.RancherDesktop`) | Apache-2.0 | **Chosen.** Gives the `docker` CLI and `docker compose` with the moby engine, and k3s for Kubernetes (plan §4.3: "Kubernetes (k3s for dev)") |
| Docker Desktop 4.100.1 (`Docker.DockerDesktop`) | Proprietary, Docker Subscription Service Agreement | Not used. Plan §4.3 lists "Docker" as Apache 2.0, which is true of the Docker Engine but not of Docker Desktop |
| Podman Desktop 1.31.0 (`RedHat.Podman-Desktop`) | Apache License 2.0 | Not used |

### Steps (need an **administrator** PowerShell and one reboot)

The development machine had no WSL and no admin rights in the AI-assisted session, so these steps are run by hand.

1. Install WSL 2. Rancher Desktop brings its own Linux distribution, so none is needed:

   ```powershell
   wsl --install --no-distribution
   ```

   Reboot when asked.

2. Install Rancher Desktop:

   ```powershell
   winget install --id SUSE.RancherDesktop --exact
   ```

3. Start Rancher Desktop. In **Preferences → Container Engine**, select **dockerd (moby)** so the standard `docker` and `docker compose` commands work. Kubernetes can stay off until it is needed (`deploy/`, plan §4.3).

4. Check from a normal terminal:

   ```powershell
   docker version
   docker compose version
   docker run --rm hello-world
   ```

When all three work, mark OD-21 as done in [PROGRESS.md](../progress/PROGRESS.md). Phase 1 can then start once OD-10 (event bus) is confirmed.

## 2. Python workspace

Python 3.11 or newer.

```bash
cp .env.example .env              # then add OPENAI_API_KEY; never commit .env
uv sync                           # or: pip install -r requirements-dev.txt (from the repo root)
bash scripts/ci/run_ci.sh         # lint, types, tests, requirements sync, licence gate
```

## 3. Git

The repository was created on 2026-11-24 with branch `main` (OD-18). The commit identity is set for this repository only (`git config --local`). `.gitattributes` keeps `*.sh` files at LF line endings, because this machine has `core.autocrlf=true`. The CI provider and remote hosting are still open (OD-18).
