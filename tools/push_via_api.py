# 通过 GitHub API 推送（github.com 的 git 端口在国内常被墙，api.github.com 通常可用）
# 用法：python push-via-api.py "提交说明"
import base64, json, subprocess, sys, urllib.request

REPO = "wangjiabin001/LiveCaptionZH"
TOKEN = subprocess.check_output(["gh", "auth", "token"], text=True, encoding="utf-8", errors="replace").strip()

def api(method, path, payload=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json",
        "User-Agent": "push-via-api", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())

def git(*a):
    return subprocess.check_output(["git", *a], text=True, encoding="utf-8", errors="replace").strip()

msg = sys.argv[1] if len(sys.argv) > 1 else "update"
head = api("GET", "/git/ref/heads/master")["object"]["sha"]
base_tree = api("GET", f"/git/commits/{head}")["tree"]["sha"]
print("远端当前:", head[:8])

items = []
for f in git("-c", "core.quotepath=false", "ls-files").splitlines():
    content = open(f, "rb").read()
    blob = api("POST", "/git/blobs", {"content": base64.b64encode(content).decode(), "encoding": "base64"})
    items.append({"path": f, "mode": "100644", "type": "blob", "sha": blob["sha"]})
print(f"上传 {len(items)} 个文件")

# 本地已删除的文件，也要从远端树里移除（API 的 tree 合并只增不删）
local = {i["path"] for i in items}
remote_files = [x["path"] for x in api("GET", f"/git/trees/{base_tree}?recursive=1")["tree"] if x["type"] == "blob"]
for path in remote_files:
    if path not in local:
        items.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
        print("  删除远端:", path)

tree = api("POST", "/git/trees", {"base_tree": base_tree, "tree": items})
commit = api("POST", "/git/commits", {"message": msg, "tree": tree["sha"], "parents": [head]})
api("PATCH", "/git/refs/heads/master", {"sha": commit["sha"], "force": False})
print("推送成功:", commit["sha"])
