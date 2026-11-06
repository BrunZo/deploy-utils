"""Tests for deploy-utils/fs auth, core, and HTTP routes."""

import io
import os
from pathlib import Path
import tempfile
import unittest

os.environ["FS_SKIP_INIT_DB"] = "1"

from app import create_app
import auth
import engine


class FsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp.name)
        self.root = tmp_path / "root"
        self.root.mkdir()
        db_file = tmp_path / "auth.db"

        os.environ["ROOT_DIR"] = str(self.root)
        os.environ["AUTH_DSN"] = f"sqlite:///{db_file.as_posix()}"
        engine.reset_engine()

        app = create_app(init_db=True)
        app.config["TESTING"] = True
        self.client = app.test_client()

        auth.create_user("alice", "secret123")
        self.api_key = auth.issue_token("test-key", "alice")

    def tearDown(self) -> None:
        engine.reset_engine()
        self._tmp.cleanup()

    def test_unauthenticated_rejected(self) -> None:
        c = self.client
        self.assertEqual(c.get("/api/me").status_code, 401)
        self.assertEqual(c.get("/api/fs").status_code, 401)
        self.assertEqual(c.get("/").status_code, 200)

    def test_cookie_login_and_logout(self) -> None:
        c = self.client
        res = c.post("/api/login", json={"username": "alice", "password": "wrong"})
        self.assertEqual(res.status_code, 401)

        res = c.post("/api/login", json={"username": "alice", "password": "secret123"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"username": "alice"})

        me = c.get("/api/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json(), {"username": "alice"})

        out = c.post("/api/logout")
        self.assertEqual(out.status_code, 200)
        self.assertEqual(c.get("/api/me").status_code, 401)

    def test_ls_upload_download_rename_delete(self) -> None:
        c = self.client
        headers = {"X-Api-Key": self.api_key}

        res = c.get("/api/fs", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json(), {"path": "", "entries": []})

        data = {
            "path": "raw/santander",
            "mkdir": "1",
            "file": (io.BytesIO(b"%PDF-1.4 sample"), "2026-01.pdf"),
        }
        up = c.post("/api/fs/upload", data=data, headers=headers, content_type="multipart/form-data")
        self.assertEqual(up.status_code, 201)
        self.assertEqual(up.get_json(), {"uploaded": ["raw/santander/2026-01.pdf"]})

        dup = c.post(
            "/api/fs/upload",
            data={"path": "raw/santander", "file": (io.BytesIO(b"new"), "2026-01.pdf")},
            headers=headers,
            content_type="multipart/form-data",
        )
        self.assertEqual(dup.status_code, 409)

        ow = c.post(
            "/api/fs/upload",
            data={
                "path": "raw/santander",
                "overwrite": "1",
                "file": (io.BytesIO(b"%PDF-1.4 updated"), "2026-01.pdf"),
            },
            headers=headers,
            content_type="multipart/form-data",
        )
        self.assertEqual(ow.status_code, 201)

        ls_sub = c.get("/api/fs?path=raw/santander", headers=headers)
        self.assertEqual(ls_sub.status_code, 200)
        entries = ls_sub.get_json()["entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["name"], "2026-01.pdf")
        self.assertEqual(entries[0]["path"], "raw/santander/2026-01.pdf")
        self.assertEqual(entries[0]["type"], "file")
        self.assertEqual(entries[0]["size"], len(b"%PDF-1.4 updated"))

        dl = c.get("/api/fs/download?path=raw/santander/2026-01.pdf", headers=headers)
        self.assertEqual(dl.status_code, 200)
        self.assertEqual(dl.data, b"%PDF-1.4 updated")

        ren = c.post(
            "/api/fs/rename",
            json={"path": "raw/santander/2026-01.pdf", "new_name": "2026-02.pdf"},
            headers=headers,
        )
        self.assertEqual(ren.status_code, 200)
        self.assertEqual(ren.get_json()["path"], "raw/santander/2026-02.pdf")

        rm = c.delete("/api/fs?path=raw/santander/2026-02.pdf", headers=headers)
        self.assertEqual(rm.status_code, 200)
        self.assertEqual(rm.get_json(), {"deleted": "raw/santander/2026-02.pdf"})

        rm_dir = c.delete("/api/fs?path=raw", headers=headers)
        self.assertEqual(rm_dir.status_code, 200)
        self.assertEqual(rm_dir.get_json(), {"deleted": "raw"})

    def test_path_traversal_blocked(self) -> None:
        c = self.client
        headers = {"X-Api-Key": self.api_key}

        self.assertEqual(c.get("/api/fs?path=../../etc", headers=headers).status_code, 400)
        self.assertEqual(c.get("/api/fs/download?path=../auth.db", headers=headers).status_code, 400)
        self.assertEqual(c.delete("/api/fs?path=..", headers=headers).status_code, 400)
        self.assertEqual(c.delete("/api/fs?path=.", headers=headers).status_code, 400)


if __name__ == "__main__":
    unittest.main()
