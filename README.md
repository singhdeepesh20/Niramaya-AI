# Niramaya-AI

**A Python backend foundation for a healthcare-oriented AI project.**

Niramaya-AI is a learning-stage application built with FastAPI, asynchronous SQLAlchemy, and PostgreSQL. It includes a small authenticated user-profile workflow and a same-origin browser interface.

> **Current scope:** authentication, profile data, and database health checks are implemented. AI/ML inference, patient records, and clinical workflows are not. Do not enter real patient information or use this project to make clinical decisions.

## Contents

- [Project status](#project-status)
- [Features](#features)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [API reference](#api-reference)
- [Browser interface](#browser-interface)
- [Security and limitations](#security-and-limitations)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)


## Project status

This repository is a developer prototype. It demonstrates how a browser can call an asynchronous API, how the API can store users in PostgreSQL, and how bearer-token authentication can protect account data.

The project does not include an AI model, clinical decision support, patient data storage, or production operations. Its authentication is a foundation for learning and local development, not a complete identity platform.


## Features

- FastAPI application serves the API and the browser interface from one origin.
- Async database access uses SQLAlchemy's `AsyncSession` and the `asyncpg` PostgreSQL driver.
- Registration creates accounts with unique usernames and emails.
- Passwords are stored as Argon2 hashes.
- Login exchanges a username and password for a signed, expiring JWT access token.
- Protected endpoints resolve the token to a database user and limit profile reads to that user.
- Alembic tracks schema changes, including password hashes and usernames.
- A health endpoint checks whether PostgreSQL can be reached.

