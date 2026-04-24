These migrations are archived from active Alembic resolution.

Why:
- They were imported from divergent branch histories.
- Several revisions referenced missing ancestors and created multiple heads.
- Some scripts perform destructive table rebuilds that conflict with the current canonical schema.

Policy:
- Keep archived files for reference only.
- Do not place these files back under `alembic/versions` unless they are reconciled into the canonical chain.
