## Summary

The `get_session_status` row was the only entry in the README tool table that wrapped onto a second line. It now uses the same short form as the other rows: it checks your saved login and browser state without opening a browser. A browser is the only way the server reaches LinkedIn, so not opening one also means it does not contact LinkedIn.

| README tool table | Before | After |
| --- | --- | --- |
| 1280 px, rendered by GitHub | ![Before](https://github.com/user-attachments/assets/071adcca-0e51-4eda-9fc7-bdf186e7207f) | ![After](https://github.com/user-attachments/assets/1e97f062-fcd6-41ac-9feb-d3542126eaa1) |

## Synthetic prompt

> Shorten the get_session_status description in the README tool table so it fits on one line like the other rows.

Implemented with Claude Opus 5.5 (effort unknown) in Claude Code via T3 Code.


<!-- Macroscope's pull request summary starts here -->
<!-- Macroscope will only edit the content between these invisible markers, and the markers themselves will not be visible in the GitHub rendered markdown. -->
<!-- If you delete either of the start / end markers from your PR's description, Macroscope will append its summary at the bottom of the description. -->
> [!NOTE]
> ### Shorten the `get_session_status` row in the README table
> Condenses the README table description for `get_session_status` to a shorter wording: it now says the command checks saved login and browser state without opening a browser. Docs-only change; the command itself is untouched.
>
> <!-- Macroscope's review summary starts here -->
>
> <sup><a href="https://app.macroscope.com">Macroscope</a> summarized 6fd208b.</sup>
> <!-- Macroscope's review summary ends here -->
>
<!-- Macroscope's pull request summary ends here -->
