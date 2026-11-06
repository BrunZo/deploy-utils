"""Flask HTTP routes for authentication, single-file UI, and filesystem operations."""

from pathlib import Path

from flask import Blueprint, Response, g, jsonify, redirect, request, send_file

import auth
import core

bp = Blueprint("fs", __name__)

INDEX_HTML = Path(__file__).resolve().parent / "index.html"
PUBLIC_ENDPOINTS = {"fs.index", "fs.healthz", "fs.login_route", "fs.logout_route"}


@bp.before_request
def authenticate_request() -> tuple[Response, int] | None:
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None
    token = request.cookies.get(auth.COOKIE_NAME)
    api_key = request.headers.get("X-Api-Key")
    user = auth.require_user(token, api_key)
    if user is None:
        return jsonify({"detail": "not authenticated"}), 401
    g.user = user
    return None


@bp.errorhandler(core.FsError)
def handle_fs_error(err: core.FsError) -> tuple[Response, int]:
    return jsonify({"detail": str(err)}), err.status_code


@bp.get("/")
def index() -> Response:
    return send_file(INDEX_HTML, mimetype="text/html")


@bp.get("/healthz")
def healthz() -> tuple[dict, int]:
    return {"status": "ok"}, 200


@bp.get("/api/me")
def me() -> Response:
    return jsonify({"username": g.user.username})


@bp.post("/api/login")
@bp.post("/login")
def login_route() -> tuple[Response, int] | Response:
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    try:
        token = auth.login(username, password)
    except auth.AuthError as e:
        return jsonify({"detail": str(e)}), 401

    resp = (
        jsonify({"username": username})
        if request.path.startswith("/api/") or request.is_json
        else redirect("/", code=303)
    )
    resp.set_cookie(
        auth.COOKIE_NAME,
        token,
        max_age=int(auth.SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="Lax",
        secure=_is_https(),
    )
    return resp


@bp.post("/api/logout")
@bp.post("/logout")
def logout_route() -> Response:
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        auth.logout(token)
    resp = (
        jsonify({"ok": True})
        if request.path.startswith("/api/") or request.is_json
        else redirect("/", code=303)
    )
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


@bp.get("/api/fs")
def ls_route() -> Response:
    rel_arg = request.args.get("path", "")
    return jsonify(core.list_dir(rel_arg))


@bp.get("/api/fs/download")
def download_route() -> Response:
    rel_arg = request.args.get("path", "")
    target = core.resolve_download(rel_arg)
    return send_file(target, as_attachment=True, download_name=target.name)


@bp.post("/api/fs/upload")
def upload_route() -> tuple[Response, int]:
    rel_dir = request.form.get("path") if "path" in request.form else request.args.get("path", "")
    overwrite = _flag("overwrite")
    mkdir = _flag("mkdir")
    files = request.files.getlist("file") or request.files.getlist("files")
    uploaded = core.upload_files(rel_dir or "", files, overwrite=overwrite, mkdir=mkdir)
    return jsonify({"uploaded": uploaded}), 201


@bp.post("/api/fs/rename")
def rename_route() -> tuple[Response, int]:
    body = request.get_json(silent=True) or request.form
    src_arg = body.get("path") or ""
    new_arg = body.get("new_name") or body.get("to") or ""
    return jsonify(core.rename_entry(src_arg, new_arg)), 200


@bp.delete("/api/fs")
def delete_route() -> tuple[Response, int]:
    body = request.get_json(silent=True) or {}
    rel_arg = request.args.get("path") or body.get("path") or ""
    deleted = core.delete_entry(rel_arg)
    return jsonify({"deleted": deleted}), 200


@bp.post("/api/fs/mkdir")
def mkdir_route() -> tuple[Response, int]:
    body = request.get_json(silent=True) or request.form
    rel_arg = body.get("path") or request.args.get("path") or ""
    created = core.make_dir(rel_arg)
    return jsonify({"path": created}), 201


def _is_https() -> bool:
    return request.is_secure or request.headers.get("X-Forwarded-Proto") == "https"


def _flag(name: str) -> bool:
    raw = request.form.get(name) or request.args.get(name) or ""
    return raw.lower() in ("1", "true", "yes")
