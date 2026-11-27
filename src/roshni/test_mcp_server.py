import json

import duckdb

from roshni import mcp_server
from roshni.ask import semantic


def _bundle(tmp_path):
    layer = semantic.load()
    t = layer.tables["mart_ke_ibc_equity"]
    con = duckdb.connect()
    cols = ", ".join(f"cast(null as varchar) as {c}" for c in t.columns)
    con.execute(f"create table x as select {cols} from range(0)")
    con.execute("insert into x (ibc) values ('IBC A'), ('IBC B')")
    con.execute(f"copy x to '{(tmp_path / 'e.parquet').as_posix()}' (format parquet)")
    ctx = {"built_at": "2026-11-27 08:00 PKT", "tables": {t.name: {"file": "e.parquet", "rows": 2}}}
    (tmp_path / "context.json").write_text(json.dumps(ctx), encoding="utf-8")
    return mcp_server.open_bundle(tmp_path)


def test_query_runs_through_the_guard(tmp_path):
    con, ctx = _bundle(tmp_path)
    tools = mcp_server.Roshni(con, ctx)
    assert [t["table"] for t in tools.list_tables()] == ["mart_ke_ibc_equity"]
    r = tools.query("select ibc from mart_ke_ibc_equity order by ibc")
    assert r["ok"] and r["rows"] == [["IBC A"], ["IBC B"]]
    assert r["label"].startswith("Scheduled") and r["data_built_at"].startswith("2026")


def test_query_refuses_what_ask_roshni_refuses(tmp_path):
    con, ctx = _bundle(tmp_path)
    tools = mcp_server.Roshni(con, ctx)
    assert not tools.query("drop table mart_ke_ibc_equity")["ok"]
    assert not tools.query("select * from read_csv('x.csv')")["ok"]
    assert not tools.query("select * from mart_ke_ibc_equity")["ok"]  # name the columns


def test_files_are_off_after_loading(tmp_path):
    con, _ = _bundle(tmp_path)
    try:
        con.execute(f"select * from read_parquet('{(tmp_path / 'e.parquet').as_posix()}')")
        raise AssertionError("file access should be off")
    except duckdb.Error:
        pass
