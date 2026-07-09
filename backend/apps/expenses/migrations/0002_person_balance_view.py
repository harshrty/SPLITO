from django.db import migrations

# Derived balance (SCOPE.md). net_minor > 0 => person is owed money.
# Settlement signs: money SENT pays down debt (+sent); money RECEIVED increases it (-recv).
VIEW_SQL = """
CREATE VIEW person_balance AS
SELECT p.id       AS person_id,
       p.group_id AS group_id,
       COALESCE(paid.total, 0)
       - COALESCE(owed.total, 0)
       + COALESCE(sent.total, 0)
       - COALESCE(recv.total, 0) AS net_minor
FROM person p
LEFT JOIN (
    SELECT paid_by_id AS pid, SUM(amount_base_minor) AS total
    FROM expense WHERE status = 'active' GROUP BY paid_by_id
) paid ON paid.pid = p.id
LEFT JOIN (
    SELECT es.person_id AS pid, SUM(es.computed_owed_minor) AS total
    FROM expense_share es
    JOIN expense e ON e.id = es.expense_id
    WHERE e.status = 'active' GROUP BY es.person_id
) owed ON owed.pid = p.id
LEFT JOIN (
    SELECT from_person_id AS pid, SUM(amount_minor) AS total
    FROM settlement GROUP BY from_person_id
) sent ON sent.pid = p.id
LEFT JOIN (
    SELECT to_person_id AS pid, SUM(amount_minor) AS total
    FROM settlement GROUP BY to_person_id
) recv ON recv.pid = p.id;
"""

DROP_SQL = "DROP VIEW IF EXISTS person_balance;"


class Migration(migrations.Migration):
    dependencies = [
        ("expenses", "0001_initial"),
        ("groups", "0001_initial"),
    ]
    operations = [migrations.RunSQL(VIEW_SQL, reverse_sql=DROP_SQL)]
