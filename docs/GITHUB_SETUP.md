# GitHub repository setup (manual, one time)

The repository is created and pushed **by you**: nothing is pushed automatically.
Steps checked against the GitHub documentation on 2026-09-30:
[secret scanning](https://docs.github.com/en/code-security/secret-scanning/enabling-secret-scanning-features/enabling-secret-scanning-for-your-repository),
[push protection](https://docs.github.com/en/code-security/secret-scanning/enabling-secret-scanning-features/enabling-push-protection-for-your-repository).

## 1. Check before publishing

From the repository root (Windows PowerShell or macOS Terminal, same commands):

```bash
git status                     # must be clean, no .env listed
git log --format="%an <%ae>"   # every author email must end with @users.noreply.github.com
uv run python -m pre_commit run --all-files
```

## 2. Create the empty repository on GitHub

Option A — website:
1. Go to <https://github.com/new>.
2. Repository name: `outreach-agents`. Visibility: **Public**.
3. Do **not** add a README, `.gitignore` or license (they already exist locally).
4. Click **Create repository**.

Option B — GitHub CLI (already installed and logged in on the Windows machine):

```bash
gh repo create outreach-agents --public --source . --remote origin
```

## 3. Push

```bash
git remote add origin https://github.com/yaskaa-lgtm/outreach-agents.git   # skip if option B
git push -u origin main
```

Then open the **Actions** tab: the `CI` workflow must turn green.

## 4. Enable Secret Protection and Push protection

1. On the repository page, click **Settings**.
2. In the sidebar, under **Security and quality**, click **Advanced Security**.
3. Next to **Secret Protection**, click **Enable**, then confirm with
   **Enable Secret Protection**.
4. Next to **Push protection**, click **Enable**.

Push protection makes GitHub refuse a `git push` that contains a known secret format:
a second safety net after the local gitleaks hook.

## 5. Recommended extras

- **Private vulnerability reporting**: same **Advanced Security** page → enable
  *Private vulnerability reporting* (referenced by [SECURITY.md](SECURITY.md)).
- **Protect `main`**: **Settings → Branches → Add branch ruleset** → target `main`, require
  a pull request and the `CI` status checks before merging, block force pushes.

## 6. Second machine (macOS or Windows)

```bash
git clone https://github.com/yaskaa-lgtm/outreach-agents.git
cd outreach-agents
git config user.name "yaskaa-lgtm"
git config user.email "305951491+yaskaa-lgtm@users.noreply.github.com"
uv sync
uv run python -m pre_commit install
cp .env.example .env            # Windows PowerShell: Copy-Item .env.example .env
docker compose up --build
```

The `git config` lines matter: without them, commits would use the machine's global
identity, which may contain a personal email address.
