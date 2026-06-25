# GitHub Population Status Updater

Updates your GitHub user status to the current estimated world population:

```text
1 / 8,262,216,721
```

The population estimate comes from Population.io:

```text
https://d6wn6bmjj722w.population.io/1.0/population/World/YYYY-MM-DD/
```

## Setup

1. Create a GitHub personal access token that can update your user status.
   A classic token with the `user` scope is the simplest option.

2. Add the token to this repository:

   ```text
   Settings -> Secrets and variables -> Actions -> New repository secret
   Name: GH_STATUS_TOKEN
   Value: your token
   ```

3. Enable GitHub Actions for the repository.

4. Run `Update GitHub status` manually once from the Actions tab.

The workflow also runs daily at `02:17 UTC`.

## Local Dry Run

```bash
GH_STATUS_TOKEN=dummy DRY_RUN=1 python3 scripts/update_status.py
```

To test a fixed date:

```bash
GH_STATUS_TOKEN=dummy DRY_RUN=1 STATUS_DATE=2026-06-24 python3 scripts/update_status.py
```

## Keeping Scheduled Workflows Active

GitHub may automatically disable scheduled workflows in public repositories
after 60 days with no repository activity. There is no repository setting that
turns that off.

This repo includes an optional `Keep scheduled workflows active` workflow. It
uses the repository `GITHUB_TOKEN` to commit a timestamp to
`.github/keepalive.txt` once a month, which keeps the repository visibly active.
If you do not want automatic commits, delete
`.github/workflows/keepalive.yml` and manually touch the repo every couple of
months instead.

For private repositories this specific public-repo inactivity rule is less of a
concern, but scheduled workflows can still be delayed and are not guaranteed to
run at the exact minute in the cron expression.
