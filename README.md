# BitD house rules / Ev kuralları

English and Turkish house rules. No rules have been added yet.
İngilizce ve Türkçe ev kuralları. Henüz kural eklenmedi.

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

Reserve translation-sync for automation. An open PR is refreshed on subsequent
pushes, so make final manual edits immediately before merging. Do not remove
the PR's translation-sync marker. Stale runs refuse publication.
Model output requires human review.

## License and attribution

Original rule text in both languages: © 2026 edgerunner, CC BY 4.0.
https://creativecommons.org/licenses/by/4.0/ — see LICENSE.
Automation code: MIT, see .github/LICENSE.
Third-party references retain their own licenses; this does not relicense
the dictionary or upstream SRD material.

This work is based on Blades in the Dark (https://www.bladesinthedark.com/),
product of One Seven Design, developed and authored by John Harper, and licensed
for our use under the Creative Commons Attribution 3.0 Unported license
(https://creativecommons.org/licenses/by/3.0/).

Unofficial; not endorsed by One Seven Design. The SRD license does not cover
non-SRD book text, setting or artwork.
