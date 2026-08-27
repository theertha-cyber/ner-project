## ADDED Requirements

### Requirement: The batch extraction request carries a processing mode

The Batch Extraction flow SHALL transmit the selected processing mode with the extraction request rather than holding it only in client state. The mode SHALL be one of `bert_only` or `bert_llm_postprocess`, and SHALL default to `bert_only`. The control SHALL live in the existing Batch Extraction document-selection modal, alongside the document selection it applies to, and SHALL follow the modal's existing design language. The client SHALL NOT enforce the mode — the server is the authority — and the client SHALL surface the server's rejection when a mode is unavailable.

*This change specifies the contract only; the UI control is implemented in a subsequent change.*

#### Scenario: Default mode is transmitted when the user changes nothing

- **GIVEN** the Batch Extraction modal opened with no explicit mode selection
- **WHEN** the user confirms the run
- **THEN** the request SHALL carry `processing_mode = 'bert_only'`

#### Scenario: The selected mode reaches the server

- **GIVEN** the user selects BERT + LLM post-processing in the modal
- **WHEN** the run is confirmed
- **THEN** the request body SHALL carry `processing_mode = 'bert_llm_postprocess'`
- **AND** the mode SHALL accompany the same request as the selected document ids

#### Scenario: An unavailable mode surfaces the server's rejection

- **GIVEN** a deployment with no post-processor configured
- **WHEN** the user confirms a run requesting post-processing
- **THEN** the client SHALL surface the server's 422 rejection
- **AND** no run SHALL appear in the batch run list

#### Scenario: The run list reports the mode each run used

- **GIVEN** completed runs executed under different processing modes
- **WHEN** the Batch Runs tab lists them
- **THEN** each run SHALL display the processing mode it actually used
- **AND** a run degraded by post-processing failure SHALL be visually distinguishable from one that completed with post-processing applied
