-- Disposable Compose environment only. These are public development passwords,
-- never reuse them outside this isolated local PostgreSQL volume.
CREATE ROLE niramaya_migrator LOGIN PASSWORD 'niramaya_migrator_only';
CREATE ROLE niramaya_runtime LOGIN PASSWORD 'niramaya_runtime_only';

GRANT CONNECT ON DATABASE niramaya_dev TO niramaya_migrator, niramaya_runtime;
GRANT USAGE, CREATE ON SCHEMA public TO niramaya_migrator;
GRANT USAGE ON SCHEMA public TO niramaya_runtime;

ALTER DEFAULT PRIVILEGES FOR ROLE niramaya_migrator IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO niramaya_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE niramaya_migrator IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO niramaya_runtime;
