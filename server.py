import io
import zipfile
import traceback
import requests

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def safe_get(url, timeout=20):
    try:
        return requests.get(url, headers=HEADERS, timeout=timeout)
    except Exception as e:
        print("REQUEST ERROR:", url, e)
        return None


def get_git_tree(owner, repo):
    for branch in ["master", "main"]:
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"

        res = safe_get(url)
        if res and res.status_code == 200:
            return res.json().get("tree", []), branch

    return None, None


def get_raw_file(owner, repo, branch, path):
    for br in [branch, "main", "master"]:
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{br}/{path}"
        res = safe_get(url)

        if res and res.status_code == 200:
            return res

    return None


@app.get("/")
def home():
    return {"status": "ok"}


@app.get("/zip")
def create_zip(path: str, owner: str, repo: str):

    try:
        print(f"ZIP REQUEST: {owner}/{repo} -> {path}")

        tree, branch = get_git_tree(owner, repo)

        if not tree:
            return JSONResponse(
                {"error": "github_api_error"},
                status_code=500
            )

        zip_buffer = io.BytesIO()
        added = 0

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:

            for item in tree:

                try:
                    item_path = item.get("path", "")

                    if item.get("type") != "blob":
                        continue

                    if not item_path.startswith(path + "/"):
                        continue

                    file_res = get_raw_file(owner, repo, branch, item_path)

                    if not file_res:
                        continue

                    archive_name = item_path.replace(path + "/", "")

                    zip_file.writestr(archive_name, file_res.content)
                    added += 1

                except Exception as e:
                    print("FILE ERROR:", e)
                    continue

        if added == 0:
            return JSONResponse(
                {"error": "empty_folder"},
                status_code=404
            )

        zip_buffer.seek(0)

        filename = path.split("/")[-1] + ".zip"

        print(f"ZIP READY: {filename}")

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        print("CRITICAL ERROR:")
        traceback.print_exc()

        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )
