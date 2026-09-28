-- Pre-seed deterministic API key for testo local ReportPortal validation (idempotent).
-- Bearer token (REPORTPORTAL_TOKEN):
--   testo-local-validation_ERERERERQRGBEREREREREV2jef5txhXfGyP3Fw17h7wSbX5dgz7RhFB1P7mNawIW
-- Generated with fixed UUID salt 11111111-1111-4111-8111-111111111111 (ReportPortal 5.15 format).

DELETE FROM api_keys WHERE name = 'testo-local-validation';

INSERT INTO api_keys (name, hash, created_at, user_id)
SELECT 'testo-local-validation',
       'E846623B6D0635FB5507A1C36CC8373CA522F7D554FCFEBB62A30159694599CC',
       now(),
       id
FROM users
WHERE login = 'superadmin';
