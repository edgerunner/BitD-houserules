"""Prepare translation context and publish validated model output."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

MARKER = "<!-- translation-sync -->"
BRANCH = "translation-sync"
RUN = Path(".run")
SNAPSHOT = Path(".translation/dictionary.md")
VERSION = Path(".translation/dictionary.sha")


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def api(path, method="GET", data=None):
    args = ["gh", "api", path, "--method", method]
    if data is not None:
        args += ["--input", "-"]
    result = subprocess.run(args, input=json.dumps(data) if data is not None else None,
                            text=True, check=True, capture_output=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def pages(path):
    result = subprocess.run(["gh", "api", "--paginate", "--slurp", path],
                            text=True, check=True, capture_output=True)
    return [item for page in json.loads(result.stdout) for item in page]


def bilingual(path):
    p = PurePosixPath(path)
    return (not p.is_absolute() and ".." not in p.parts
            and not any(part.startswith(".") for part in p.parts)
            and (path.endswith(".en.md") or path.endswith(".tr.md")))


def counterpart(path):
    return path[:-6] + (".tr.md" if path.endswith(".en.md") else ".en.md")


def metadata(pr):
    body = pr.get("body") or ""
    if MARKER not in body or pr.get("head", {}).get("ref") != BRANCH:
        return None
    for line in body.splitlines():
        if line.startswith("<!-- sync-data: ") and line.endswith(" -->"):
            return json.loads(line[16:-4])
    return None


def output(key, value):
    with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
        stream.write(f"{key}={value}\n")


def git_blob(text):
    raw = text.encode()
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def prepare():
    RUN.mkdir(exist_ok=True)
    repo = os.environ["GITHUB_REPOSITORY"]
    head = git("rev-parse", "HEAD")
    prs = pages(f"repos/{repo}/pulls?state=closed&base=main&per_page=100")
    accepted = [p for p in prs if p.get("merged_at") and metadata(p)
                and metadata(p)["mode"] == "content"]
    accepted.sort(key=lambda p: p["merged_at"], reverse=True)
    baseline = accepted[0]["merge_commit_sha"] if accepted else git("rev-list", "--max-parents=0", "HEAD").splitlines()[0]
    fallback = False
    try:
        source = api("repos/edgerunner/BitD-tr/contents/dictionary.md?ref=development")
        dictionary = base64.b64decode(source["content"]).decode("utf-8")
        sha = source["sha"]
        assert git_blob(dictionary) == sha, "Dictionary hash mismatch"
    except (subprocess.CalledProcessError, KeyError, ValueError, AssertionError) as error:
        if not SNAPSHOT.exists() or not VERSION.exists():
            raise RuntimeError("Dictionary unavailable and no fallback snapshot exists") from error
        dictionary, sha = SNAPSHOT.read_text(), VERSION.read_text().strip()
        fallback = True
        assert git_blob(dictionary) == sha, "Fallback dictionary hash mismatch"
    old_sha = VERSION.read_text().strip() if VERSION.exists() else None
    if accepted and head == baseline and old_sha == sha:
        output("needed", "false")
        return
    files = [f for f in git("ls-files").splitlines() if bilingual(f)]
    changed = [f for f in git("diff", "--name-only", baseline, head).splitlines() if bilingual(f)]
    # When both sides are gone, there is nothing left to translate or review.
    remaining = set(files)
    changed = [f for f in changed if f in remaining or counterpart(f) in remaining]
    if not changed and old_sha == sha:
        output("needed", "false")
        return
    mode = "terminology" if old_sha != sha else "content"
    context = dict(head=head, baseline=baseline, mode=mode, files=files,
                   changed=changed, dictionary=dictionary, dictionary_sha=sha,
                   fallback=fallback)
    (RUN / "context.json").write_text(json.dumps(context, ensure_ascii=False, indent=2))
    output("needed", "true")
    output("translate", "true" if changed or (files and mode == "terminology") else "false")
    (RUN / "result.json").write_text(json.dumps(dict(files=[], conflicts=[], summary="Sözlük referansı güncellendi.")))


def validate(result, context):
    assert set(result) == {"files", "conflicts", "summary"}, "Unexpected output keys"
    assert isinstance(result["summary"], str)
    assert isinstance(result["conflicts"], list) and all(isinstance(s, str) for s in result["conflicts"])
    allowed = set(context["files"]) | {counterpart(f) for f in context["files"]}
    seen = set()
    for entry in result["files"]:
        path = entry["path"]
        assert set(entry) == {"path", "content"}
        assert bilingual(path) and path in allowed and path not in seen, f"Invalid output path: {path}"
        assert isinstance(entry["content"], str)
        assert not any(p.is_symlink() for p in [Path(path), *Path(path).parents]), "Symlink output"
        seen.add(path)


def publish():
    context = json.loads((RUN / "context.json").read_text())
    result = json.loads((RUN / "result.json").read_text())
    validate(result, context)
    assert git_blob(context["dictionary"]) == context["dictionary_sha"]
    repo = os.environ["GITHUB_REPOSITORY"]
    if api(f"repos/{repo}/git/ref/heads/main")["object"]["sha"] != context["head"]:
        raise RuntimeError("main changed during this run; retry the latest workflow")
    assert git("rev-parse", "HEAD") == context["head"]
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    body = result["summary"] + "\n\n" + MARKER
    body += "\n<!-- sync-data: " + json.dumps({k: context[k] for k in ("mode", "head", "baseline")}) + " -->"
    body += f"\n\nDictionary: edgerunner/BitD-tr@development, blob {context['dictionary_sha']}."
    if context["fallback"]:
        body += "\n\n**Not:** Güncel sözlüğe ulaşılamadı; son bilinen sözlük kullanıldı."
    if result["conflicts"]:
        issue_body = "\n\n".join(result["conflicts"])
        issue_body += f"\n\nSource: {context['head']}\n{MARKER}"
        issues = pages(f"repos/{repo}/issues?state=open&per_page=100")
        title = "Çeviri: iki dilde çelişen değişiklikler"
        existing = next((i for i in issues if not i.get("pull_request") and i["title"] == title and MARKER in (i.get("body") or "")), None)
        if existing:
            api(f"repos/{repo}/issues/{existing['number']}", "PATCH", {"body": issue_body})
        else:
            api(f"repos/{repo}/issues", "POST", {"title": title, "body": issue_body})
        body += "\n\nÇelişkili bölümler değiştirilmedi; inceleme için issue açıldı/güncellendi."
    paths = []
    for entry in result["files"]:
        p = Path(entry["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(entry["content"])
        paths.append(str(p))
    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(context["dictionary"])
    VERSION.write_text(context["dictionary_sha"] + "\n")
    paths += [str(SNAPSHOT), str(VERSION)]
    git("add", "--", *paths)
    if not git("diff", "--cached", "--name-only"):
        return
    git("checkout", "-B", BRANCH)
    title = "Sözlük: terimleri güncelle" if context["mode"] == "terminology" else "Çeviri: İngilizce ve Türkçe metinleri eşitle"
    git("commit", "-m", title)
    git("push", "--force", "github", f"HEAD:refs/heads/{BRANCH}")
    prs = api(f"repos/{repo}/pulls?state=open&head={repo.split('/')[0]}:{BRANCH}&base=main")
    if prs:
        pr = api(f"repos/{repo}/pulls/{prs[0]['number']}", "PATCH", {"title": title, "body": body})
    else:
        pr = api(f"repos/{repo}/pulls", "POST", {"title": title, "body": body, "head": BRANCH, "base": "main"})
    print(pr["html_url"])


if __name__ == "__main__":
    {"prepare": prepare, "publish": publish}[sys.argv[1]]()
