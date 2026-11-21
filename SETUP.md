# Setting up the PR review bot

The bot runs on GitHub Actions, so there is no server to host. When an allowed user comments `/review` on a pull request, a workflow runs the review script and posts the result as a comment on the PR.

> **Current state:** the review script is a placeholder that posts a dummy comment. Use it to check that the setup works.

## Requirements

- Admin access to the repository where the bot should run. You need it to change repository variables.
- Optional: the [GitHub CLI](https://cli.github.com/) (`gh`), if you prefer the terminal to the web UI.

## Steps

### 1. Copy the bot files into the repository

Copy these files into the target repository and keep the same paths:

| File | Purpose |
|---|---|
| `.github/workflows/review.yml` | Listens for `/review` comments and runs the bot |
| `bot/review.py` | The review script |

Merge them into the **default branch** (usually `main`). GitHub runs workflows triggered by comments only from the default branch, so the bot does nothing while the files sit only on a feature branch.

### 2. Choose who can trigger the bot

Only the GitHub usernames in the repository variable `REVIEW_BOT_USERS` can trigger a review. If the variable is missing or empty, nobody can trigger the bot.

**On the web:**

1. Open the repository, then **Settings → Secrets and variables → Actions**.
2. Open the **Variables** tab and click **New repository variable**.
3. Name: `REVIEW_BOT_USERS`
4. Value: a JSON array of usernames, for example:

   ```json
   ["stickerdaniel","UGisBusy"]
   ```

**With the GitHub CLI:**

```bash
gh variable set REVIEW_BOT_USERS --repo OWNER/REPO --body '["stickerdaniel","UGisBusy"]'
```

To add or remove someone later, edit the variable. The workflow file stays as it is. Usernames are matched without regard to case.

### 3. Check that Actions is allowed to run

In **Settings → Actions → General**, make sure Actions is enabled for the repository. You don't need to change any token permissions, because the workflow sets its own.

## Using the bot

1. Open any pull request in the repository.
2. Post a comment that starts with `/review`.
3. After a minute or two, the bot replies with a review comment.

If you aren't in `REVIEW_BOT_USERS`, nothing happens. GitHub skips the run without an error, and you'll see it as "skipped" in the **Actions** tab.

## Troubleshooting

| Problem | What to check |
|---|---|
| No run appears in the **Actions** tab | The workflow file isn't on the default branch yet. |
| The run shows as **skipped** | Your username isn't in `REVIEW_BOT_USERS`, the variable isn't valid JSON, or the comment doesn't start with `/review`. |
| The run fails at "Post comment on PR" | Actions may be limited to read-only tokens by an organization policy. Check **Settings → Actions → General → Workflow permissions**. |
| You commented on an issue | The bot only reviews pull requests, so comments on plain issues are ignored. |
