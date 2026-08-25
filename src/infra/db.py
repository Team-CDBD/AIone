from contracts.infra import DbQueryError,DbTimeout,DbUnavailable
class PostgresDb:
    def __init__(self,dsn:str):
        try:
            from psycopg_pool import ConnectionPool
            from pgvector.psycopg import register_vector
            self.pool=ConnectionPool(
                dsn,min_size=1,max_size=10,kwargs={"autocommit":True},
                configure=register_vector,
            )
        except Exception as exc: raise DbUnavailable(str(exc)) from exc
    def fetch_dicts(self,sql,params=()):
        try:
            from psycopg.rows import dict_row
            with self.pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur: cur.execute("SET statement_timeout='5s'");cur.execute(sql,params);return list(cur.fetchall())
        except Exception as exc:
            if "timeout" in str(exc).lower():raise DbTimeout(str(exc)) from exc
            raise DbQueryError(str(exc)) from exc
    def fetch(self,sql,params=()):return [tuple(row.values()) for row in self.fetch_dicts(sql,params)]

def probe_dsn(dsn:str,timeout:float=3.0)->None:
    """접속만 확인한다. 풀을 쓰지 않는 이유는 풀 대기(기본 30초)가 판정을 그만큼 늦추기 때문이다."""
    import psycopg
    try:
        with psycopg.connect(dsn,connect_timeout=int(timeout)) as conn:
            with conn.cursor() as cur:cur.execute("SELECT 1");cur.fetchone()
    except Exception as exc:raise DbUnavailable(str(exc)) from exc
