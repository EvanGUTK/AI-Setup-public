# Local review record

Two CodeRabbit CLI reviews completed locally before publication. The initial working-diff review reported one major finding: failed review reports could approve a push. A subsequent committed review of `76f8bd1ba31f6a67613530202389665220688035` reported four findings: malformed sync frontmatter, a host-dependent NVM test, and two duplicate reports about overwriting learned skills. All distinct findings were corrected and regression-tested; the final exact-commit approval includes independent validation of these corrections. CodeRabbit did not produce a zero-finding result, and command success was not treated as approval.

| Finding | Correction and evidence |
| --- | --- |
| Failed or legacy report can approve a commit | Structured JSON verdict, matching authority/SHA and passing checks required both when recording and when checking. Failed/legacy report regressions pass. |
| Fetch destination differs from actual push destination | Reject mismatched/multiple fetch/push URLs and URL rewrites; validate and push the same exact destination. Regression passes. |
| Named remote indirection can redirect a push | Reject a URL that names another configured remote; canonicalize local destinations. Regression passes. |
| Sync discards local configuration without backup | Back up each changed file under private WSL backup storage; idempotent sync regression preserves original native role content. |
| Malformed Claude frontmatter interrupts partial sync | Preflight every managed agent before the first write; malformed-input regression confirms no mutations. |
| Executable test depends on host NVM | Use an isolated fake NVM home and restored environment. Regression passes without a real NVM installation. |
| Reinstall overwrites learned skills | Seed templates only when absent; preserve canonical skill, role, rule, model and bootstrap edits. Reinstall regression checks active content and Windows propagation. |

The local suite at that point contained 22 meaningful behavioral tests (later increments add more; run `python3 -m unittest discover -s tests -v` for the current set). Skill metadata validation passed for all 120 personal skills. Native config parsing, independent installer-preservation fixtures and Windows profile/argument forwarding checks are described in INSTALLATION.md. No remote CI workflows were created.

Limitations: native full interactive model-team startup was not exercised end-to-end; model access and native tools remain provider-dependent. The push helper is a local policy tool and does not authenticate reviewer identities or intercept raw Git. Windows native memory is reconciled to WSL before snapshot synchronization. User approval controls merge.

Issue #5 (one-prompt install): review evidence for the installer, doctor and install tests is recorded in the linked PR after local CodeRabbit and Validator review of the exact commit; this file does not pre-claim it.
