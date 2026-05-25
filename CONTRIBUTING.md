# Contributing to AtlasLens

Thank you for your interest in contributing to AtlasLens. This document explains the contribution process and requirements.

## Developer Certificate of Origin (DCO)

This project uses the [Developer Certificate of Origin (DCO)](https://developercertificate.org/) to certify that contributors have the right to submit their work. All commits must include a `Signed-off-by` line with your real name and email address.

### How to sign off

Add `-s` (or `--signoff`) to your git commit command:

```bash
git commit -s -m "Add feature X"
```

This produces a commit message like:

```
Add feature X

Signed-off-by: Your Name <your.email@example.com>
```

If you have already made commits without the sign-off, you can amend the most recent:

```bash
git commit --amend -s
```

Or rebase to add sign-offs to multiple commits:

```bash
git rebase --signoff HEAD~N
```

**Commits without a valid DCO sign-off will not be accepted.**

## Getting Started

1. Fork the repository and clone your fork.
2. Create a feature branch from `main`.
3. Set up the development environment:

```bash
docker compose up -d mongo
pip install -e ".[dev]"
cd frontend && npm install
```

4. Make your changes with tests.
5. Ensure all checks pass:

```bash
pytest -q
ruff check .
mypy .
cd frontend && npm run lint && npm test
```

6. Commit with DCO sign-off and open a pull request.

## Pull Request Guidelines

- Keep PRs focused on a single change.
- Include tests for new functionality.
- Update documentation if behaviour changes.
- Ensure CI passes before requesting review.
- Reference any related issues in the PR description.

## Code Style

- **Python:** formatted with `black`, linted with `ruff`, type-checked with `mypy`.
- **TypeScript:** formatted with `prettier`, linted with `eslint`.
- Avoid adding comments unless the *why* is non-obvious.

## Reporting Issues

Use GitHub Issues. Include:

- Steps to reproduce (for bugs).
- Expected vs actual behaviour.
- Environment details (OS, Python/Node version, MongoDB version).

## Security Vulnerabilities

If you discover a security vulnerability, please report it privately via GitHub Security Advisories rather than opening a public issue.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
