# Contributing

Thank you for improving Portico.

## Prepare the repository

1. Fork and clone the repository.
2. Run `task setup` from the repository root.
3. Run `task demo` to open the app with synthetic data.

Do not put financial records, Google Sheet URLs, webhook URLs, or credentials in commits, issues, screenshots, or logs.

## Make a change

Keep each change focused. Add tests for changed behavior. Update the documentation when you change commands, configuration, or visible behavior.

Run these commands before you open a pull request:

```console
task privacy:check
task lint
task test
```

Describe the user-visible result and the tests in the pull request. Use demo data for screenshots.
