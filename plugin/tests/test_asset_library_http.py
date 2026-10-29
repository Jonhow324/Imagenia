"""Public asset listing contract and stable cursor behavior without external services."""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from src.imagenia_plugin import FakeImageProvider, create_app  # noqa: E402


def jpeg_bytes(width: int, height: int) -> bytes:
    app0 = b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    frame = (b"\xff\xc0\x00\x11\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big")
             + b"\x03\x01\x11\x00\x02\x11\x00\x03\x11\x00")
    return b"\xff\xd8" + app0 + frame + b"\xff\xd9"


@pytest.mark.anyio
async def test_keyset_paging_and_filtered_listing_across_insertions(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    app = create_app(tmp_path / "data", provider=FakeImageProvider())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        assert (await http.get("/api/imagenia/assets")).json() == {"items": [], "next_cursor": None}
        for number in range(35):
            queued = await http.post("/api/imagenia/jobs/generate", json={"prompt": f"view {number}"})
            assert queued.status_code == 202
            assert app.worker.process_next()
        rows = app.database.execute("SELECT id FROM image_assets ORDER BY created_at DESC, id DESC").fetchall()
        # #8 implements mutations; seed existing favorite/edited records for listing contract.
        for index, row in enumerate(rows):
            app.database.execute("UPDATE image_assets SET is_favorite=?, kind=? WHERE id=?",
                (int(index % 2 == 0), "edited" if index % 3 == 0 else "generated", row["id"]))
        app.database.commit()
        first = (await http.get("/api/imagenia/assets")).json()
        assert len(first["items"]) == 30 and first["next_cursor"]
        assert [item["id"] for item in first["items"]] == [row["id"] for row in rows[:30]]
        # Newest insertion must not shift the second page or duplicate entries.
        await http.post("/api/imagenia/jobs/generate", json={"prompt": "new view"})
        app.worker.process_next()
        second = (await http.get("/api/imagenia/assets", params={"cursor": first["next_cursor"]})).json()
        assert [item["id"] for item in second["items"]] == [row["id"] for row in rows[30:]]
        assert second["next_cursor"] is None
        short = (await http.get("/api/imagenia/assets", params={"limit": "2"})).json()
        assert [item["id"] for item in short["items"]] == [row["id"] for row in app.database.execute(
            "SELECT id FROM image_assets ORDER BY created_at DESC, id DESC LIMIT 2")]
        assert short["next_cursor"]
        full = (await http.get("/api/imagenia/assets", params={"limit": "100"})).json()
        assert len(full["items"]) == 36 and full["next_cursor"] is None
        short_next = (await http.get("/api/imagenia/assets", params={"limit": "2", "cursor": short["next_cursor"]})).json()
        assert len(short_next["items"]) == 2
        assert not {item["id"] for item in short["items"]} & {item["id"] for item in short_next["items"]}
        baseline = (await http.get("/api/imagenia/assets", params={"limit": "2"})).json()
        for cursor in ("", "null"):
            assert (await http.get("/api/imagenia/assets", params={"limit": "2", "cursor": cursor})).json() == baseline
        favorites = (await http.get("/api/imagenia/assets", params={"favorite": "true"})).json()
        assert len(favorites["items"]) == 18 and all(item["is_favorite"] for item in favorites["items"])
        edited = (await http.get("/api/imagenia/assets", params={"kind": "edited", "favorite": "true"})).json()
        assert len(edited["items"]) == 6 and all(item["kind"] == "edited" for item in edited["items"])
        assert (await http.get("/api/imagenia/assets", params={"kind": "edited", "favorite": "false"})).status_code == 200


@pytest.mark.anyio
async def test_invalid_filters_and_cursors_never_echo_input_or_execute_sql(tmp_path):
    app = create_app(tmp_path / "data", provider=FakeImageProvider())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        for query in ("kind=other", "favorite=1", "cursor=secret-key", "limit=0", "limit=200", "limit=abc", "limit=-1",
                      "limit=2.5", "limit=", "limit=1&limit=2", "kind=generated&kind=edited",
                      "kind=generated%27%20OR%201%3D1", "page=2", "favorite=true&cursor=WzEsMl0"):
            result = await http.get("/api/imagenia/assets?" + query)
            assert result.status_code == 422
            assert "secret-key" not in result.text
        assert (await http.get("/api/imagenia/assets")).status_code == 200


@pytest.mark.anyio
async def test_prompt_search_is_a_literal_casefolded_substring(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    app = create_app(tmp_path / "data", provider=FakeImageProvider())
    prompts = ("Rainy alley neon", "sunny greenhouse", "100% silk", "a_b pattern", "雨后的弄堂", "token alpha", "token beta", "token gamma")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        for prompt in prompts:
            assert (await http.post("/api/imagenia/jobs/generate", json={"prompt": prompt})).status_code == 202
            assert app.worker.process_next()
        app.database.execute("UPDATE image_assets SET prompt=? WHERE prompt=?", ("path\\name", "sunny greenhouse"))
        app.database.commit()

        async def found(**params: str) -> list[str]:
            body = (await http.get("/api/imagenia/assets", params=params)).json()
            return [item["prompt"] for item in body["items"]]

        assert await found(q="rainy") == ["Rainy alley neon"]
        assert await found(q="RAINY") == ["Rainy alley neon"]
        assert await found(q="弄堂") == ["雨后的弄堂"]
        assert await found(q="%") == ["100% silk"]
        assert await found(q="_") == ["a_b pattern"]
        assert await found(q="\\") == ["path\\name"]
        assert await found(q="' OR 1=1 --") == []
        assert await found(q="   ") == await found()
        rain_id = next(item["id"] for item in (await http.get("/api/imagenia/assets")).json()["items"] if item["prompt"] == "Rainy alley neon")
        assert (await http.patch(f"/api/imagenia/assets/{rain_id}", json={"is_favorite": True})).status_code == 200
        assert await found(q="alley", favorite="true") == ["Rainy alley neon"]
        assert await found(q="弄堂", favorite="true") == []
        seen: list[str] = []
        cursor = None
        for _ in range(4):
            params = {"q": "token", "limit": "1"}
            if cursor:
                params["cursor"] = cursor
            page = (await http.get("/api/imagenia/assets", params=params)).json()
            seen.extend(item["prompt"] for item in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert sorted(seen) == ["token alpha", "token beta", "token gamma"]
        long = "x" * 81
        too_long = await http.get("/api/imagenia/assets", params={"q": long})
        newline = await http.get("/api/imagenia/assets", params={"q": "a\nb"})
        duplicate = await http.get("/api/imagenia/assets?q=a&q=b")
        for result, secret in ((too_long, long), (newline, "a\nb"), (duplicate, "q=b")):
            assert result.status_code == 422
            assert secret not in result.text
            assert result.json()["error"]["code"] == "invalid_filter"


@pytest.mark.anyio
async def test_mixed_jpeg_and_png_library_lists_and_serves_original_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAGENIA_OPENAI_API_KEY", "sk-fake")
    app = create_app(tmp_path / "data", provider=FakeImageProvider())
    jpeg = jpeg_bytes(1024, 1024)
    relative = "images/2026/10/jpeg-asset.jpg"
    target = app.data_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(jpeg)
    with app.database:
        app.database.execute("""INSERT INTO image_assets
            (id,kind,prompt,model,size,quality,width,height,file_path,mime_type,file_size,created_at,updated_at)
            VALUES ('jpeg-asset','generated','mixed library','image-01','square','standard',1024,1024,?,
                    'image/jpeg',?,'2026-10-22T05:00:00+00:00','2026-10-22T05:00:00+00:00')""",
            (relative, len(jpeg)))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as http:
        queued = await http.post("/api/imagenia/jobs/generate", json={"prompt": "png asset"})
        assert app.worker.process_next()
        png_id = (await http.get(f"/api/imagenia/jobs/{queued.json()['job_id']}")).json()["result_asset_id"]
        listing = await http.get("/api/imagenia/assets", params={"limit": "20"})
        assert listing.status_code == 200
        items = {item["id"]: item for item in listing.json()["items"]}
        assert set(items) == {png_id, "jpeg-asset"}
        assert (items["jpeg-asset"]["width"], items["jpeg-asset"]["height"]) == (1024, 1024)
        for asset_id, mime, expected in (("jpeg-asset", "image/jpeg", jpeg),
                                         (png_id, "image/png", FakeImageProvider.image_bytes)):
            content = await http.get(f"/api/imagenia/assets/{asset_id}/content")
            assert content.status_code == 200
            assert content.headers["content-type"] == mime
            assert content.content == expected
