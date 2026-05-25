import io
import zipfile
import traceback
import requests
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse

app = FastAPI()

HEADERS = {"User-Agent": "Mozilla/5.0"}

NO_PROXIES = {"http": None, "https": None}


def detect_branch(owner, repo):
    """Авто-определение main/master"""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    r = requests.get(url, headers=HEADERS, timeout=20)

    if r.status_code != 200:
        return "main"

    data = r.json()
    return data.get("default_branch", "main")


@app.get("/")
def home():
    return {"status": "ok"}


@app.get("/zip")
def create_zip(path: str, owner: str, repo: str):

    try:
        print(f"ZIP REQUEST: {path}")

        zip_buffer = io.BytesIO()

        branch = detect_branch(owner, repo)

        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"

        response = requests.get(tree_url, headers=HEADERS, proxies=NO_PROXIES, timeout=120)

        if response.status_code != 200:
            return JSONResponse(
                {"error": "github_api_error", "status": response.status_code},
                status_code=500
            )

        tree = response.json().get("tree", [])

        added = 0

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:

            for item in tree:

                try:
                    item_path = item.get("path", "")

                    if item.get("type") != "blob":
                        continue

                    if not item_path.startswith(path + "/"):
                        continue

                    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{item_path}"

                    file_res = requests.get(raw_url, headers=HEADERS, timeout=120)

                    if file_res.status_code != 200:
                        continue

                    archive_name = item_path.replace(path + "/", "")

                    zip_file.writestr(archive_name, file_res.content)
                    added += 1

                except Exception as e:
                    print("FILE ERROR:", e)
                    continue

        if added == 0:
            return JSONResponse({"error": "empty_folder"}, status_code=404)

        zip_buffer.seek(0)

        filename = path.split("/")[-1] + ".zip"

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception:
        traceback.print_exc()
        return JSONResponse({"error": "server_crash"}, status_code=500)
