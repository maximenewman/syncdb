from dialects.mysql import MySQLDialect


def test_insert_skipping_duplicates_sql_single_column():
    sql = MySQLDialect().insert_skipping_duplicates_sql("users", ["id"])
    assert sql == "INSERT IGNORE INTO `users` (`id`) VALUES (:id)"


def test_insert_skipping_duplicates_sql_multiple_columns():
    sql = MySQLDialect().insert_skipping_duplicates_sql("orders", ["id", "user_id", "total"])
    assert sql == (
        "INSERT IGNORE INTO `orders` (`id`, `user_id`, `total`) "
        "VALUES (:id, :user_id, :total)"
    )


def test_insert_skipping_duplicates_sql_quotes_every_identifier():
    sql = MySQLDialect().insert_skipping_duplicates_sql("t", ["a", "b"])
    assert "`a`" in sql and "`b`" in sql
    assert ":a" in sql and ":b" in sql
