## ADDED Requirements

## IN SCOPE
- Collect all screenshots from a run and post as gallery on completion
- Respect Discord file limits (10 per message, 25MB total)
- Batch into multiple messages if needed

## OUT OF SCOPE
- Thumbnail generation
- Screenshot deduplication

### Requirement: Screenshot gallery on run completion
When an orchestration run completes, the system SHALL collect all smoke and E2E screenshots from the run and post them as a gallery message in the run thread.

#### Scenario: Run completes with screenshots
- **WHEN** a run transitions to `done` or `failed` status
- **AND** screenshots exist across smoke and E2E directories
- **THEN** a gallery message is posted to the run thread with all screenshots
- **AND** Discord renders them in its native image grid layout

#### Scenario: More than 10 screenshots
- **WHEN** the total screenshot count exceeds 10
- **THEN** screenshots are batched into multiple messages of up to 10 each

#### Scenario: Total size exceeds 25MB
- **WHEN** the combined size of all screenshots exceeds 25MB
- **THEN** only screenshots fitting within the limit are uploaded
- **AND** a text message notes how many were skipped

#### Scenario: No screenshots in run
- **WHEN** a run completes with no screenshots collected
- **THEN** no gallery message is posted

### Requirement: Image size management
Individual screenshots exceeding 1MB SHALL be resized before upload if Pillow is installed. If Pillow is not available, oversized images are skipped with a warning.

#### Scenario: Large screenshot with Pillow
- **WHEN** a screenshot is larger than 1MB
- **AND** Pillow is installed
- **THEN** the image is resized to fit within 1MB before upload

#### Scenario: Large screenshot without Pillow
- **WHEN** a screenshot is larger than 1MB
- **AND** Pillow is not installed
- **THEN** the screenshot is skipped and a warning is logged
