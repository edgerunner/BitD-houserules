## Writing

Add any name.en.md or name.tr.md, including inside subdirectories.
Push to main to propose the matching language in a PR. Conflicting changes
to the same passage produce an issue. Review and merge the translation PR;
your review edits are accepted without reverse translation.

## Automation setup

Add OPENAI_API_KEY in Settings → Secrets and variables → Actions.
OpenAI API usage is billed to that key's API project.
Enable “Allow GitHub Actions to create and approve pull requests” in
Settings → Actions → General. The workflow never approves or merges PRs.
Use Bilingual sync → Run workflow to retry manually. No polling is configured.

Every run fetches the dictionary from:
https://github.com/edgerunner/BitD-tr/blob/development/dictionary.md
A reference snapshot and blob SHA in .translation/ provide a fallback.
Fallback use is disclosed in the PR; without a snapshot, fetch failure stops.
Dictionary changes receive a separate terminology PR, potentially editing
both languages. After merging it, run the workflow to handle pending content.
Nothing is installed in the dictionary repository.

The dictionary repository is private. For live updates, add DICTIONARY_TOKEN
as an Actions repository secret: a fine-grained GitHub token limited to
edgerunner/BitD-tr with Contents: Read access. The built-in token only has
access to this repository; without DICTIONARY_TOKEN the saved snapshot is used.
The reference snapshot is visible in this public repository.

Reserve translation-sync for automation. An open PR is refreshed on subsequent
pushes, so make final manual edits immediately before merging. Do not remove
the PR's translation-sync marker. Stale runs refuse publication.
Model output requires human review.
