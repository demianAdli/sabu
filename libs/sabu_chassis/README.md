# jugs-chassis

`jugs-chassis` is a shared JUGS library that provides reusable utilities for multiple services.

It is designed for cross-cutting concerns that should be imported directly by services (for example: logging setup and shared runtime conventions), instead of being exposed as a standalone service.

## Why this package exists

In JUGS, some capabilities are best delivered as code dependencies rather than API calls.

Using `jugs-chassis` as a dependency makes it easier to:

- Reuse the same behavior across services.
- Keep service internals consistent.
- Ship functionality (not inter-service data exchange) in a versioned Python package.

## Current scope

At the moment, the primary implemented utility is logging configuration.

The logging setup is currently tuned for one service context. As the microservices chassis effort progresses, this will be normalized so all JUGS services can use a common logging standard in later versions.

## Installation

### Dockerizing and using in services independently

```bash
pip install jugs-chassis
```

### Installing as a dependency (e.g., inside Dockerized services)

```bash
cd libs/jugs_chassis
pip install .
```

### Developing locally (cloning the repository)

```python
from jugs_chassis.logging import configure_logging, set_request_id

configure_logging()
set_request_id('req-123')
```

Optional environment variables commonly used by the logging module include:

- `LOG_LEVEL`
- `WERKZEUG_LEVEL`
- `LOG_SERVICE`
- `LOG_ENV`
- `LOG_DIR_BASE`

## JUGS

JUGS is a sector-based carbon-emission evaluation framework built with a microservices architecture.

Each module runs as an independent service (a "jug"). Current services focus on building life-cycle assessment and city-scale geospatial cleaning/validation workflows. Alongside services, JUGS also includes shared Python libraries such as `jugs-chassis` to provide reusable internal functionality.

## Roadmap note

`jugs-chassis` will continue to grow as a shared library for JUGS services, with future versions expanding beyond logging into additional standardized service utilities.
