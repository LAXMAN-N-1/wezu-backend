"""
Gunicorn configuration file.

Ensures structured logging is re-initialised **after** the worker process
has been forked so every worker writes to its own stderr handle.
"""

import os


def post_fork(server, worker):
    """Called in each newly-forked worker process."""
    # Re-initialise logging so the worker has a fresh stderr handler.
    from app.core.logging import setup_logging

    setup_logging()
    server.log.info("Worker %s (pid %s) logging initialised", worker.pid, os.getpid())


# Allow all settings to be overridden by environment variables;
# the Dockerfile CMD already passes most of these via CLI flags,
# so this file only adds the post_fork hook.
