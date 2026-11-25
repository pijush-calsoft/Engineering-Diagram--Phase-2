# Local environment setup

The platform runs locally (OD-2). This guide sets up the container runtime and the Python workspace on a Windows machine.

## 1. Container runtime: not used (OD-21)

**Superseded 2026-11-25:** the project owner decided "no need for container" for the POC. Nothing in this section needs installing. GPL tools run as separate local processes. The original choice is kept below for reference.

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

## 2. LibreDWG for DWG input (OD-49)

DWG files are converted by LibreDWG's `dwg2dxf` (GPLv3), which runs only as a separate process (plan §9).

**Preferred: LibreDWG 0.14.** Download https://github.com/LibreDWG/libredwg/releases/download/0.14/libredwg-0.14-win64.zip (signature: the same URL with `.sig`) and extract it to `tools/libredwg-0.14-win64/`, so that `tools/libredwg-0.14-win64/dwg2dxf.exe` exists. This network blocks GitHub release files for command-line tools, so download it in a browser.

**Fallback: 0.11 from conda-forge**, installed into an isolated environment under the git-ignored `tools/` folder (the base conda environment is not touched). Its DWG writer produces files 0.14 cannot read (OD-49):

```bash
conda create -y -p tools/conda-libredwg --override-channels -c conda-forge libredwg
```

The parser finds `tools/libredwg-0.14-win64/dwg2dxf.exe`, then `tools/conda-libredwg/Library/bin/dwg2dxf.exe`, by itself; elsewhere, set `EDP_DWG2DXF` to the executable. Without it, DWG inputs fail with `DWG_CONVERSION_FAILED`, and the DWG tests are skipped.

## 3. Python workspace

Python 3.11 or newer.

```bash
cp .env.example .env              # then add OPENAI_API_KEY; never commit .env
uv sync                           # or: pip install -r requirements-dev.txt (from the repo root)
bash scripts/ci/run_ci.sh         # lint, types, tests, requirements sync, licence gate
```

## 4. Git

The repository was created on 2026-11-24 with branch `main` (OD-18). The commit identity is set for this repository only (`git config --local`). `.gitattributes` keeps `*.sh` files at LF line endings, because this machine has `core.autocrlf=true`. The CI provider and remote hosting are still open (OD-18).
