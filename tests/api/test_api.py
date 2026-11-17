from __future__ import annotations

from datetime import timedelta

import pytest
from api_fakes import FakeCriterion, FakeSpec, FakeVerdict
from conftest import API_KEY, KEY_ENV, make_profile
from fastapi.testclient import TestClient

from agent0.api import create_app
from agent0.config import Settings
from agent0.core.types import Artifact, RunStatus, utcnow

BASE = "/api/v1"


def test_auth_required(env):
    anon = TestClient(env.app)
    for headers in ({}, {"Authorization": "Bearer nope"}, {"Authorization": "Basic " + API_KEY}):
        r = anon.get(f"{BASE}/runs", headers=headers)
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"
    assert anon.get(f"{BASE}/runs", headers={"Authorization": f"Bearer {API_KEY}"}).status_code == 200


def test_auth_covers_streams_and_secrets(env):
    anon = TestClient(env.app)
    for path in ("/stream", "/secrets", "/runs/x/stream", "/model-profiles"):
        assert anon.get(BASE + path).status_code == 401


def test_cloud_refuses_default_key():
    with pytest.raises(RuntimeError):
        create_app(build_deps=lambda: None, settings=Settings(_env_file=None, env="cloud", api_key="dev-key"))


def test_cors_allowlist(env):
    ok = env.client.options(
        f"{BASE}/runs",
        headers={"Origin": "http://dash.example", "Access-Control-Request-Method": "GET"},
    )
    assert ok.headers["access-control-allow-origin"] == "http://dash.example"
    bad = env.client.options(
        f"{BASE}/runs", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"}
    )
    assert "access-control-allow-origin" not in bad.headers


def test_error_shape(client):
    r = client.get(f"{BASE}/runs/missing")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "run missing not found"}}
    r = client.post(f"{BASE}/tasks", json={})
    assert r.status_code == 422
    assert set(r.json()["error"]) == {"code", "message"}
    assert client.get(f"{BASE}/runs?limit=0").status_code == 422
    assert client.get(f"{BASE}/runs?cursor=!!!").json()["error"]["code"] == "invalid_cursor"


async def test_pagination_runs(env):
    for i in range(5):
        run = await env.repos.seed_run()
        run.started_at = utcnow() + timedelta(seconds=i)
    seen, cursor = [], None
    while True:
        r = env.client.get(f"{BASE}/runs", params={"limit": 2, **({"cursor": cursor} if cursor else {})})
        body = r.json()
        assert len(body["items"]) <= 2
        seen += [i["id"] for i in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 5


async def test_pagination_tasks_and_filters(env):
    for i in range(3):
        await env.repos.seed_run(title=f"job {i}", source="telegram" if i else "api")
    page = env.client.get(f"{BASE}/tasks?limit=2").json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = env.client.get(f"{BASE}/tasks", params={"limit": 2, "cursor": page["next_cursor"]}).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    only = env.client.get(f"{BASE}/tasks?source=api&q=JOB").json()["items"]
    assert [t["title"] for t in only] == ["job 0"]
    assert env.client.get(f"{BASE}/tasks?status=bogus").status_code == 422


async def test_create_task_and_retry(env):
    r = env.client.post(
        f"{BASE}/tasks",
        json={"prompt": "build a thing", "budget": {"max_usd": 0.5}, "notify_level": "everything"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["task"]["title"] == "build a thing"
    assert body["task"]["budget"]["max_usd"] == 0.5
    assert body["task"]["source"] == "api"
    assert body["run"]["task_id"] == body["task"]["id"]
    assert env.orchestrator.calls[0] == ("submit", body["task"]["id"])
    assert env.client.post(f"{BASE}/tasks", json={"prompt": "x", "agent": "nope"}).status_code == 422
    retry = env.client.post(f"{BASE}/tasks/{body['task']['id']}/retry")
    assert retry.json()["run"]["attempt"] == 2
    assert env.client.post(f"{BASE}/tasks/nope/retry").status_code == 404
    detail = env.client.get(f"{BASE}/tasks/{body['task']['id']}").json()
    assert detail["task"]["attempts"] == 2 and len(detail["runs"]) == 2


async def test_run_detail_checks_from_verdicts(env):
    run = await env.repos.seed_run(RunStatus.VERIFYING)
    env.repos.task_specs.rows[run.task_id] = FakeSpec(
        goal="g", criteria=[FakeCriterion(id="a"), FakeCriterion(id="b"), FakeCriterion(id="c")]
    )
    env.repos.verdicts.rows[run.id] = [
        FakeVerdict(check_id="a", status="pass"),
        FakeVerdict(check_id="b", status="fail", evidence="nope"),
    ]
    env.repos.artifacts.rows["x"] = Artifact(id="x", run_id=run.id, path="out.txt", kind="text", size=3)
    body = env.client.get(f"{BASE}/runs/{run.id}").json()
    assert (body["run"]["checks_total"], body["run"]["checks_passed"]) == (3, 1)
    assert {v["check_id"]: v["status"] for v in body["verdicts"]} == {
        "a": "pass",
        "b": "fail",
        "c": "pending",
    }
    assert body["spec"]["goal"] == "g"
    assert body["artifacts"][0]["url"] == f"{BASE}/runs/{run.id}/artifacts/x"
    listed = env.client.get(f"{BASE}/runs?status=verifying").json()["items"]
    assert listed[0]["checks_total"] == 3


async def test_events_stop_stats(env):
    run = await env.repos.seed_run()
    env.repos.add_events(run.id, 5)
    items = env.client.get(f"{BASE}/runs/{run.id}/events?after_seq=2").json()["items"]
    assert [e["seq"] for e in items] == [3, 4, 5]
    assert items[0]["type"] == "tool.call" and "created_at" in items[0]
    assert len(env.client.get(f"{BASE}/events?type=tool.call&agent=executor").json()["items"]) == 5
    assert env.client.get(f"{BASE}/events?agent=other").json()["items"] == []
    stats = env.client.get(f"{BASE}/stats/overview").json()
    assert stats["running"] == 1 and stats["spend_today_usd"] == 0
    assert env.client.post(f"{BASE}/runs/{run.id}/stop").json()["run"]["status"] == "stopped"
    assert env.client.post(f"{BASE}/runs/{run.id}/stop").status_code == 409


async def test_approvals(env):
    run = await env.repos.seed_run(RunStatus.WAITING_APPROVAL)
    row = env.repos.add_approval(run.id)
    assert env.client.get(f"{BASE}/approvals?status=pending").json()["items"][0]["id"] == row["id"]
    r = env.client.post(f"{BASE}/approvals/{row['id']}", json={"decision": "approve", "note": "go"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved" and r.json()["note"] == "go"
    assert env.orchestrator.calls[-1][2:] == ("approve", "dashboard", "go")
    assert env.client.post(f"{BASE}/approvals/{row['id']}", json={"decision": "reject"}).status_code == 409
    assert env.client.post(f"{BASE}/approvals/zzz", json={"decision": "reject"}).status_code == 404
    assert env.client.post(f"{BASE}/approvals/{row['id']}", json={"decision": "maybe"}).status_code == 422
    assert env.client.get(f"{BASE}/approvals?status=approved").json()["items"][0]["status"] == "approved"


async def test_artifact_download_and_confinement(env):
    run = await env.repos.seed_run()
    ws = env.settings.workspace_root / run.id
    ws.mkdir(parents=True)
    (ws / "out.txt").write_text("hello")
    (env.settings.workspace_root / "secret.txt").write_text("top secret")
    arts = env.repos.artifacts.rows
    arts["ok"] = Artifact(id="ok", run_id=run.id, path="/workspace/out.txt")
    arts["esc"] = Artifact(id="esc", run_id=run.id, path="../secret.txt")
    arts["abs"] = Artifact(id="abs", run_id=run.id, path="C:/Windows/win.ini")
    arts["gone"] = Artifact(id="gone", run_id=run.id, path="missing.txt")
    r = env.client.get(f"{BASE}/runs/{run.id}/artifacts/ok")
    assert r.status_code == 200 and r.text == "hello"
    assert env.client.get(f"{BASE}/runs/{run.id}/artifacts/esc").status_code == 403
    assert env.client.get(f"{BASE}/runs/{run.id}/artifacts/abs").status_code == 403
    assert env.client.get(f"{BASE}/runs/{run.id}/artifacts/gone").status_code == 404
    assert env.client.get(f"{BASE}/runs/other/artifacts/ok").status_code == 404


def test_model_profiles_and_router(env, monkeypatch):
    items = env.client.get(f"{BASE}/model-profiles").json()["items"]
    assert {p["id"] for p in items} == {"fast", "vis"}
    assert all(p["key_configured"] is False for p in items)
    assert [p["id"] for p in env.client.get(f"{BASE}/model-profiles?capability=vision").json()["items"]] == [
        "vis"
    ]
    assert env.client.get(f"{BASE}/router/preview?capability=chat").json()["profile"] is None
    monkeypatch.setenv(KEY_ENV, "sk-env-secret-value")
    items = env.client.get(f"{BASE}/model-profiles").json()["items"]
    assert all(p["key_configured"] for p in items)
    assert "sk-env-secret-value" not in str(items)
    prev = env.client.get(f"{BASE}/router/preview?capability=chat&prefer=cheap").json()
    assert prev["profile"]["id"] == "fast" and "fast" in prev["reason"]
    assert env.client.get(f"{BASE}/router/preview?capability=nope").status_code == 422


def test_model_profile_crud(env):
    new = make_profile("extra", key_env="EXTRA_KEY").model_dump(mode="json")
    assert env.client.post(f"{BASE}/model-profiles", json=new).status_code == 201
    assert env.client.post(f"{BASE}/model-profiles", json=new).status_code == 409
    r = env.client.put(f"{BASE}/model-profiles/fast", json={"enabled": False})
    assert r.json()["enabled"] is False and r.json()["model"] == "fast"
    assert env.registry.get("fast").enabled is False
    assert env.client.put(f"{BASE}/model-profiles/nope", json={}).status_code == 404
    assert env.client.delete(f"{BASE}/model-profiles/extra").status_code == 204
    assert env.client.delete(f"{BASE}/model-profiles/vis").json()["error"]["code"] == "builtin_profile"
    assert env.client.delete(f"{BASE}/model-profiles/ghost").status_code == 404


def test_extensions(env):
    items = env.client.get(f"{BASE}/extensions").json()["items"]
    assert [(e["id"], e["kind"]) for e in items] == [("skill:demo", "skill")]
    assert env.client.get(f"{BASE}/extensions?kind=mcp").json()["items"] == []
    assert env.client.get(f"{BASE}/extensions?kind=bogus").status_code == 422
    assert "body text" in env.client.get(f"{BASE}/extensions/skill:demo").json()["config"]["body"]
    r = env.client.put(f"{BASE}/extensions/skill:demo", json={"enabled": False})
    assert r.json()["enabled"] is False
    assert env.client.get(f"{BASE}/extensions").json()["items"][0]["enabled"] is False
    assert env.client.post(f"{BASE}/extensions/skill:demo/test").status_code == 422
    assert env.client.get(f"{BASE}/extensions/mcp:none").status_code == 404


def test_agents_schedules_usage_and_stubs(env):
    assert env.client.get(f"{BASE}/agents").json()["items"][0]["name"] == "executor"
    assert env.client.get(f"{BASE}/agents/executor/versions").json()["items"][0]["version"] == 1
    assert env.client.get(f"{BASE}/agents/nope").status_code == 404
    assert env.client.put(f"{BASE}/agents/executor").status_code == 501
    assert env.client.get(f"{BASE}/memory/search?q=x").status_code == 501
    s = env.client.post(f"{BASE}/schedules", json={"agent": "executor", "cron": "0 9 * * 1", "prompt": "p"})
    assert s.status_code == 201
    sid = s.json()["id"]
    assert (
        env.client.post(
            f"{BASE}/schedules", json={"agent": "executor", "cron": "bad", "prompt": "p"}
        ).status_code
        == 422
    )
    put = env.client.put(
        f"{BASE}/schedules/{sid}", json={"agent": "executor", "cron": "0 8 * * *", "prompt": "q"}
    )
    assert put.json()["cron"] == "0 8 * * *"
    assert len(env.client.get(f"{BASE}/schedules").json()["items"]) == 1
    assert env.client.delete(f"{BASE}/schedules/{sid}").status_code == 204
    assert env.client.delete(f"{BASE}/schedules/{sid}").status_code == 404
    summary = env.client.get(f"{BASE}/usage/summary?group_by=provider").json()
    assert summary["items"][0]["provider"] == "groq"
    assert env.client.get(f"{BASE}/usage/summary?group_by=zzz").status_code == 422
    assert env.client.get(f"{BASE}/usage").status_code == 501
