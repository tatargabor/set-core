## ADDED Requirements

### Requirement: Operator-specific integrations live behind plugin seams
The public repository SHALL contain only behaviour useful to any user of the framework. An
integration that serves one operator's own tooling, clients or company processes SHALL live
in a separately installed package registered through the existing plugin entry points, and
the public core SHALL work, with that integration absent, without an error or a WARNING.

#### Scenario: The operator plugin is not installed
- **WHEN** the public core runs on a machine without the operator's private package
- **THEN** every public command and the dashboard start and run without an error or a WARNING naming the missing package

#### Scenario: A new operator-specific feature
- **WHEN** a feature only the operator's company uses is proposed
- **THEN** its change places it in the private package, and the public change adds at most a generic seam
