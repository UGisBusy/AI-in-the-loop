# Setting up the PR review bot

The bot runs on GitHub Actions. When an allowed user comments `/review` on a pull request, a workflow runs the review script and posts the report in the comment and stores it into `bot-reports` branch.

TODO:
- review script is a placeholder that posts a dummy comment.
- create, comment, and store report
- TBD

## Requirements

- Admin access to the repository where the bot should run. You need it to change repository variables.

## Steps

### 1. Copy the bot files into the repository

Copy these files into the target repository and keep the same paths:

| File                           | Purpose                                         |
| ------------------------------ | ----------------------------------------------- |
| `.github/workflows/review.yml` | Listens for `/review` comments and runs the bot |
| `bot/review.py`                | The review script                               |
| `bot/report.py`                | Turns a report into the PR comment              |
| `bot/criteria.json`            | The parts and points the bot checks             |
| `bot/sample_report.json`       | Dummy results used until real checks exist      |

Merge them into the **default branch** (usually `main`). GitHub runs workflows triggered by comments only from the default branch.

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

In **Settings → Actions → General**, make sure Actions is enabled for the repository.

## Using the bot

1. Open any pull request in the repository.
2. Post a comment that starts with `/review`.
3. After a minute or two, the bot replies with a review comment.

If you aren't in `REVIEW_BOT_USERS`, nothing happens. GitHub skips the run without an error, and you'll see it as "skipped" in the **Actions** tab.
