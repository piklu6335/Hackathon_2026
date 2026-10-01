# MySQL setup

Create a MySQL 8 database, then run `schema.sql` against it. Configure the app with `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`; do not commit credentials. Render's custom MySQL deployment is a separate private service with a persistent disk mounted at `/var/lib/mysql`.

The schema prepares the planned users, sessions, analyses, and extension scan records. The current API does not yet write analysis history or provide account endpoints; wire those features before enabling login UI in production.
