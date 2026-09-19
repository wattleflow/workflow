# WattleFlow Workflow
![WattleFlow Logo](https://raw.githubusercontent.com/wattleflow/core/default/src/wattleflow/logo/wattleflow.png)

[![PyPI version](https://img.shields.io/pypi/v/wattleflow-workflow.svg)](https://pypi.org/project/wattleflow-workflow/)
[![Python versions](https://img.shields.io/pypi/pyversions/wattleflow-workflow.svg)](https://pypi.org/project/wattleflow-workflow/)
[![License](https://img.shields.io/pypi/l/wattleflow-workflow.svg)](https://github.com/wattleflow/workflow/blob/default/LICENSE)

---

*WattleFlow — graceful flow,*
*modular, scaled with purpose,*
*patterns guide the stream,*
*extensible, clear design,*
*built to last and grow.*

---

| Characteristic | Value |
| --- | --- |
| **Version** | [![PyPI version](https://img.shields.io/pypi/v/wattleflow-workflow.svg)](https://pypi.org/project/wattleflow-workflow/) |
| **Licence** | Apache-2.0 |
| **Python** | 3.11 – 3.13 |
| **Maturity** | Production/Stable |
| **Dependencies** | [wattleflow](https://github.com/wattleflow/core) only; nothing outside the standard library |
| **Documentation** | [wattleflow/documentation](https://github.com/wattleflow/documentation) |

# What it is

`wattleflow-workflow` is the data-engineering framework of WattleFlow: over the interfaces in
`wattleflow` it builds the generic implementations from which pipelines are composed —
workflow → pipeline → processor → strategy — for acquiring, transforming and storing data.

| Package | Carries |
| --- | --- |
| `concrete` | generic implementations of every core interface: workflow, pipeline, processor, driver, repository, blackboard, strategy, connection, document |
| `helpers` | audit records, the run monitor (operations, resources, thresholds, report), configuration, routing |
| `managers`, `orchestrators`, `schedulers` | composition and execution of workflows |
| `enums`, `constants`, `decorators` | the controlled vocabularies the framework uses |

The import closure is the standard library plus `wattleflow`; that is what makes the
distribution zero-trust. Every third-party integration lives in
[blackwattle](https://github.com/wattleflow/blackwattle).

# Installation

```bash
pip install wattleflow-workflow
```

# Licence

Apache-2.0 — see [LICENSE](LICENSE).
