# Spec: Orchestration Logging Hardening

## Overview
Add WARNING/INFO logs to all silent failure paths in the orchestration pipeline.

## Requirements

### REQ-LOG-001: Data-loss path warnings
Every function returning empty when data expected logs WARNING with reason.

### REQ-LOG-002: Pipeline flow INFO logs  
Dispatch summary, gate pipeline summary, coverage check result — one line each.

### REQ-LOG-003: ANOMALY prefix for sentinel detection
Conditions that should never happen get `[ANOMALY]` prefix in log message.

### REQ-LOG-004: NullProfile warning
NullProfile loaded when project-type.yaml exists = WARNING, not DEBUG.

### REQ-LOG-005: Exception specificity
Replace bare `except Exception: pass` with specific types + WARNING log.
