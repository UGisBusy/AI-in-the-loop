# Setting up the PR review bot

The bot runs on GitHub Actions. When an allowed user comments `/review` on a pull request, a workflow runs the review script and posts the report in the comment and stores it into `bot-reports` branch.

For what's built so far and what's still open, see [PROGRESS.md](PROGRESS.md).

## Requirements

- Admin access to the repository where the bot should run. You need it to change repository variables and secrets.
- An Anthropic API key from the [Claude Console](https://platform.claude.com/). API usage is billed separately from a Claude.ai subscription.

## Steps

### 1. Copy the bot files into the repository

Copy these files into the target repository and keep the same paths:

| File                           | Purpose                                         |
| ------------------------------ | ----------------------------------------------- |
| `.github/workflows/review.yml` | Listens for `/review` comments and runs the bot |
| `bot/review.py`                | The review script                               |
| `bot/github_context.py`        | Reads the PR and repository through the GitHub API |
| `bot/claude_review.py`         | Asks Claude to judge each point                 |
| `bot/report.py`                | Turns a report into the PR comment              |
| `bot/criteria.json`            | The parts and points the bot checks             |
| `bot/requirements.txt`         | Python packages the bot needs                   |
| `bot/sample_report.json`       | Sample results for `--dummy` test runs          |

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

### 3. Add the Anthropic API key

1. Open **Settings → Secrets and variables → Actions**.
2. On the **Secrets** tab, click **New repository secret**.
3. Name: `ANTHROPIC_API_KEY`, value: your API key.

With the GitHub CLI: `gh secret set ANTHROPIC_API_KEY --repo OWNER/REPO` (it asks for the value).

Set a monthly spend limit in the Claude Console. A review sends the PR description, the diff, the full changed files and the repository guides, up to about 100k tokens, so one review costs roughly $0.05 to $0.50 depending on the PR's size. The size limits are at the top of `bot/github_context.py`.

### 4. Check that Actions is allowed to run

In **Settings → Actions → General**, make sure Actions is enabled for the repository.

## Using the bot

1. Open any pull request in the repository.
2. Post one of these comments:

   | Comment | What happens |
   |---|---|
   | `/review` | Full review with Claude |
   | `/review --dry-run` | Collects the context without calling Claude, so it costs nothing. Posts a summary of what would be sent; the full prompt is attached to the workflow run as `prompt.txt` |
   | `/review --dummy` | Posts a sample report. No GitHub context or API calls |

3. After a minute or two, the bot replies with a comment.

If you aren't in `REVIEW_BOT_USERS`, nothing happens. GitHub skips the run without an error, and you'll see it as "skipped" in the **Actions** tab.

If the review fails, for example because the API key is wrong, the bot posts a short comment with a link to the run log.

## Testing locally

You need the [GitHub CLI](https://cli.github.com/) logged in (`gh auth login`), and `pip install -r bot/requirements.txt`.

```bash
# Render the sample report. No API calls.
python bot/review.py --dummy

# Collect the real context of a PR and print the prompt. No Claude call, no cost.
python bot/review.py --repo OWNER/REPO --pr 123 --dry-run

# Full review. Needs ANTHROPIC_API_KEY set. Prints the comment, doesn't post it.
python bot/review.py --repo OWNER/REPO --pr 123 --report-out report.json
```
