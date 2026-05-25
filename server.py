from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse
import requests
import zipfile
import io

app = FastAPI()


@app.get("/")
def home():
    return {"status": "ok"}


@app.get("/zip")
def zip_repo(path: str, owner: str, repo: str):

    try:
        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
        r = requests.get(tree_url, timeout=30)

        if r.status_code != 200:
            tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1"
            r = requests.get(tree_url, timeout=30)

        if r.status_code != 200:
            return JSONResponse({"error": "github_error"}, status_code=500)

        tree = r.json().get("tree", [])

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:

            for item in tree:

                if item.get("type") != "blob":
                    continue

                file_path = item["path"]

                if not file_path.startswith(path + "/"):
                    continue

                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{file_path}"
                content = requests.get(raw_url, timeout=30).content

                z.writestr(file_path.replace(path + "/", ""), content)

        zip_buffer.seek(0)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{path.split("/")[-1]}.zip"'
            }
        )

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
