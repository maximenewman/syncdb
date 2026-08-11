import pytest
from sqlalchemy import create_engine

from dialects import Dialect, MySQLDialect, PostgresDialect, get_dialect


@pytest.fixture
def mysql():
    return MySQLDialect()


@pytest.fixture
def postgres():
    return PostgresDialect()


class TestRegistry:
    """get_dialect keys off SQLAlchemy's backend name, not the URL scheme."""

    @pytest.mark.parametrize(
        "url, expected",
        [
            ("mysql+pymysql://u:p@h:3306/d", MySQLDialect),
            ("postgresql+psycopg://u:p@h:5432/d", PostgresDialect),
        ],
    )
    def test_resolves_backend(self, url, expected):
        assert isinstance(get_dialect(create_engine(url)), expected)

    @pytest.mark.parametrize("dialect", [MySQLDialect, PostgresDialect])
    def test_name_matches_sqlalchemy_backend_name(self, dialect):
        # The registry is keyed on engine.dialect.name, which is the backend
        # ("postgresql"), not the driver ("psycopg"). If these drift apart,
        # every URL for that backend falls through to "Unsupported".
        assert dialect.name in {"mysql", "postgresql"}

    def test_driver_must_be_named_for_postgres_urls(self):
        # syncdb depends on psycopg 3; a bare postgresql:// URL makes
        # SQLAlchemy reach for psycopg2 and fail at create_engine time.
        # Documented here so the README's +psycopg guidance has a test.
        with pytest.raises(ModuleNotFoundError, match="psycopg2"):
            create_engine("postgresql://u:p@h:5432/d")

    def test_rejects_unsupported_backend(self):
        with pytest.raises(ValueError, match="Unsupported database backend"):
            get_dialect(create_engine("sqlite://"))

    def test_both_dialects_are_concrete(self):
        # Instantiating proves no abstract method was left unimplemented.
        for dialect in (MySQLDialect(), PostgresDialect()):
            assert isinstance(dialect, Dialect)


class TestQuoteIdentifier:
    def test_mysql_uses_backticks(self, mysql):
        assert mysql.quote_identifier("users") == "`users`"

    def test_postgres_uses_double_quotes(self, postgres):
        assert postgres.quote_identifier("users") == '"users"'

    def test_mysql_escapes_embedded_backtick(self, mysql):
        assert mysql.quote_identifier("we`ird") == "`we``ird`"

    def test_postgres_escapes_embedded_double_quote(self, postgres):
        assert postgres.quote_identifier('we"ird') == '"we""ird"'

    def test_postgres_preserves_case(self, postgres):
        # Quoting is what stops Postgres folding a mixed-case MySQL table
        # name to lowercase, so the quoted form must round-trip verbatim.
        assert postgres.quote_identifier("UserAccounts") == '"UserAccounts"'


class TestInsertSkippingDuplicates:
    def test_mysql_uses_insert_ignore(self, mysql):
        sql = mysql.insert_skipping_duplicates_sql("users", ["id", "email"])
        assert sql == (
            "INSERT IGNORE INTO `users` (`id`, `email`) VALUES (:id, :email)"
        )

    def test_postgres_uses_on_conflict_do_nothing(self, postgres):
        sql = postgres.insert_skipping_duplicates_sql("users", ["id", "email"])
        assert sql == (
            'INSERT INTO "users" ("id", "email") '
            "VALUES (:id, :email) ON CONFLICT DO NOTHING"
        )

    @pytest.mark.parametrize("dialect", [MySQLDialect(), PostgresDialect()])
    def test_placeholders_match_column_count(self, dialect):
        columns = ["a", "b", "c", "d"]
        sql = dialect.insert_skipping_duplicates_sql("t", columns)
        for column in columns:
            assert f":{column}" in sql


class TestReadSql:
    """select_all_sql and count_rows_sql are shared, quoting is not."""

    def test_mysql_select_all(self, mysql):
        assert mysql.select_all_sql("orders") == "SELECT * FROM `orders`"

    def test_postgres_select_all(self, postgres):
        assert postgres.select_all_sql("orders") == 'SELECT * FROM "orders"'

    def test_mysql_count_rows(self, mysql):
        assert mysql.count_rows_sql("orders") == "SELECT COUNT(*) FROM `orders`"

    def test_postgres_count_rows(self, postgres):
        assert postgres.count_rows_sql("orders") == 'SELECT COUNT(*) FROM "orders"'
