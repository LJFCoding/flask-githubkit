# Changelog

## 0.1.5

- Link the docs and README to the PyPI project page.
- Add a PyPI entry to the project URLs.
- Update the pinned-version examples.

## 0.1.4

- Added html_meta myst description to improve SEO
- Canonical link to reduce SEO splittage

## 0.1.3

- Add a Sphinx documentation site with installation, quick start,
  configuration, examples and API reference pages.
- Configure Read the Docs to build the documentation from the repository.
- Add the documentation URL to package metadata.

## 0.1.2

- Clear the request-cached GitHubKit client on logout, so logging out
  takes effect immediately in the same request.
- Keep request-cached clients separate for each `GitHub` extension
  instance.

## 0.1.1

- `@github.login` marks the view it decorates, and an expired refresh
  token redirects there. A blueprint view needs no `login_view` setting.
- The login view is chosen from the `login_view` argument, then
  `GITHUB_LOGIN_VIEW`, then the decorated view, then `login`.

## 0.1.0

First release.

- `GitHub` extension with `@github.login`, `@github.callback`, `client()`
  and `logout()`
- OAuth `state` check on the callback
- Expiring tokens are refreshed by GitHubKit and saved back to
  `flask.session`
- `scope` and `login_view` can be passed to `GitHub(...)` or set with
  `GITHUB_SCOPE` and `GITHUB_LOGIN_VIEW`
- A GitHub outage during the code exchange returns a 502
- Examples for a single file, an app factory, a blueprint and API calls

Not verified yet: a real GitHub exchange and refresh, Redis, and
Flask-Session TTL behaviour.
