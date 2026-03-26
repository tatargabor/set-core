## finding-issue-sync

### Requirements

- REQ-1: DetectionBridge must mark findings as "pipeline" status after registering an issue
- REQ-2: DetectionBridge must persist _processed_findings to disk to survive restarts
- REQ-3: When issue resolves, the source finding must be marked "fixed"
- REQ-4: Sentinel must skip findings with status "pipeline" when doing Tier 3 fixes

### Scenarios

**finding-marked-pipeline**
GIVEN a sentinel finding with status "open"
WHEN DetectionBridge registers it as an issue
THEN the finding status in findings.json is updated to "pipeline"

**processed-survives-restart**
GIVEN DetectionBridge has processed findings F001 and F002
WHEN the manager service restarts
THEN F001 and F002 are not re-registered as duplicate issues

**sentinel-skips-pipeline-findings**
GIVEN a finding with status "pipeline"
WHEN sentinel evaluates Tier 3 fixes
THEN sentinel does NOT attempt to fix this finding
