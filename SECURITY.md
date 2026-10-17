# Security and private data

Never publish `app/data/`, session cookies, API tokens, database backups or real-account test artifacts. The data directory contains authentication material and personal saved content. Source exports deliberately exclude these files, model files and machine-specific runtime paths.

The backend binds to loopback. Do not expose it through a public proxy. Use the extension in one primary browser profile per library. Remote inference endpoints change where evidence is sent.

For security reports, describe the issue without credentials or personal content. Use GitHub private vulnerability reporting if available; otherwise establish a private contact with the maintainer before sharing sensitive details. Revoke an Instagram session if its cookies are exposed.
