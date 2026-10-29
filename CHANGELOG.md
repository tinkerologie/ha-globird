# Changelog

All notable changes to this project are documented in this file.

This project uses Home Assistant's calendar versioning scheme (`YYYY.M.P`, for example `2026.10.0`).

## [Unreleased]

### Changed

- Releases ship the integration as `globird.zip`, with a `SHA256SUMS` file and a signed build provenance attestation. `hacs.json` sets `zip_release` and `filename`, so from the next release HACS and the Marketplace install the zip and show the latest release's download count; choosing an older release without the zip can then fail to download. `script/build_release_zip.py` builds the zip reproducibly, pull requests check that two builds match byte for byte, and the release workflow publishes through a draft so it works with immutable releases. The README covers manual installation from the zip and how to verify it ([#31](https://github.com/tinkerologie/ha-globird/issues/31)).
- Tests fail on deprecated use by the integration: deprecation warnings raised from its modules are errors, Home Assistant's own deprecation reports that name `globird` fail the test that logged them, and a clean-interpreter import of every module runs against the pinned Home Assistant. A weekly, non-blocking HA Next workflow runs the import check, tests and Hassfest against the newest Home Assistant (beta included) and Core `dev`, keeping one `ha-next` issue per channel, and a weekly developer blog watch opens an `ha-dev-blog` issue for each post that deprecates code the integration uses. `script/hassfest` supports Home Assistant 2026.11's packaged validator and Core commit SHAs ([#32](https://github.com/tinkerologie/ha-globird/issues/32)).

### Fixed

- Align the Python package version with the `2026.10.5` integration manifest, restoring CI version validation and the frontend resource registration test after the release bump.

## [2026.10.5] - 2026-10-26

### Added

- Four bundled GloBird dashboard cards: usage and cost, electricity usage with daily charts, latest-day usage or gas meter reading, and account summary. Cards include accessible visual editors, Home Assistant theme support, service selection, Sections sizing, and clear pending, incomplete and stale data notices ([#27](https://github.com/tinkerologie/ha-globird/issues/27)).
- Recorder-excluded `globird_sensor_key` and `statistic_id` discovery metadata. Existing sensor values and statistics are unchanged. Optional history reads existing daily recorder changes, with no additional portal requests.
- Automatic, cache-versioned card loading through supported asynchronous HTTP and frontend helpers, plus TypeScript 7.0.2 build, unit/browser tests and CI verification of the bundled module.

### Fixed

- Avoid fresh-tab configuration errors caused by extra modules registering cards before Home Assistant replaces its custom-element registry. Storage dashboards now use a managed Lovelace module resource; YAML resource setup is documented.
- Preserve all incomplete-day markers in longer recorder history, avoid attributing an ambiguous connection failure to the selected account, and provision Chromium in the full local frontend check.

## [2026.10.4] - 2026-10-17

### Fixed

- **2026.10.3 failed to set up after a restart** ([#23](https://github.com/tinkerologie/ha-globird/issues/23)): sensors uploaded their long-term statistics during entity setup and waited for the recorder to commit each one, but the recorder does not commit until Home Assistant has finished starting, so setup hit the 5-minute bootstrap timeout and was cancelled. Statistics uploads now start in a background task owned by the config entry once Home Assistant has started (or straight away when the entry is reloaded), and never block setup. Gas history uploads now run one at a time and wait for the recorder commit, like the electricity statistics, so a refresh during the first upload cannot overwrite newer rows with an older snapshot.

## [2026.10.3] - 2026-10-17

### Added

- Sensors and long-term statistics per usage register ([#18](https://github.com/tinkerologie/ha-globird/issues/18)): when a service has more than one register of the same kind, such as the `E1` *Offpeak*, *Peak* and *Shoulder* time-of-use windows or the two `B1` feed-in windows, each gets a *Recent `<register>`* sensor (kWh) with its `time_periods`, and a `globird:<entry>_service_<id>_register_<register>` statistic for the Energy dashboard. Flat-rate accounts get no new sensors. Sensors are added when the portal starts returning a register and become unavailable if it stops.
- *Recent Controlled Load Total* and *Latest Day Controlled Load* sensors and the `globird:<entry>_service_<id>_controlled_load_total` statistic, created only for services that return a controlled-load register (`chargeCategoryCode` `CONTROL`) (part of [#19](https://github.com/tinkerologie/ha-globird/issues/19)). Not yet confirmed against a real controlled-load account.

### Changed

- Pull requests get path labels and at most one type label, `bug` or `enhancement`, from the shared tinkerologie PR labeler. Dependabot pull requests whose largest update is a patch or minor version merge automatically once the checks and commit statuses on their head commit have finished without a failure (a Codecov check that is still pending is not waited for; a Codecov failure blocks); majors, and pull requests with open review threads, stay for review.
- Release workflows hardened (least-privilege job permissions, no expressions in shell scripts, no persisted checkout credentials, no dependency caches); scheduled workflows run on Australia/Brisbane time. New CI workflow runs lint and tests on every pull request. LICENSE now contains the complete Apache License 2.0 text.
- Tinkerologie-Bot governance report updated to v1.4.3: an older run can no longer post a stale report after a newer run passed. Workflow formatting tidied.
- Repository standardised to the tinkerologie layout (STANDARDS.md in tinkerologie/.github): workflows renamed to the standard set (CI, Validate, Release, PR Governance, ...), every action pinned to a commit SHA, shared Dependabot, `.editorconfig`, `.gitattributes` and `CODEOWNERS` files, and organization-wide labels and community files.
- Tinkerologie-Bot's comment is now a readable "Pull request checklist": each problem is a numbered heading with plain-English guidance and its items listed underneath, and report updates for a pull request are serialised so an older run can never overwrite a newer one.
- Contribution governance: issues without a `bug` or `enhancement` label are labeled automatically when their type can be determined (issues labeled `question`, `duplicate`, `invalid`, `wontfix`, or `no-type` are skipped), so CodeRabbit can plan them. Pull requests that conflict with the default branch are labeled, and their authors are notified in a comment. Stale issues and pull requests are labeled after 14 days without activity and closed 30 days later. PR governance now re-validates a human-authored, non-draft PR when a bot such as CodeRabbit edits its description, instead of skipping the check and reporting a pass, only maintainers with write access may use `None` instead of linking an issue, and a link to an issue that does not exist now fails the check.
- Tinkerologie-Bot now posts one comment on pull requests that fail PR governance, listing every problem to fix, and updates it once they are fixed. PR governance runs from the default branch's workflow (`pull_request_target`), so a pull request cannot change its own check.
- Update repository URLs and documentation references to tinkerologie organization.

### Fixed

- **Usage and export totals change:** ZEROHERO reward and add-on registers are no longer counted twice ([#17](https://github.com/tinkerologie/ha-globird/issues/17)). The `ZeroHero` row (`LOW_USAGE_REWARD_PER_DAY`, 18:00–21:00) only repeats part of *Peak Usage*, and `Super Export top up` (`ADDON_FEED_IN`, 18:00–21:00) only repeats part of the 4pm–11pm feed-in, so *Recent Usage Total*, *Latest Day Usage*, *Recent Solar Export Total*, *Latest Day Solar Export*, their `daily` attributes and the `globird:…_usage_total` / `…_solar_export_total` statistics were too high. Totals now count only the energy categories GloBird's portal totals (`USAGE`, `CONTROL`, `CLIMATE`, `SOLAR`, or no category); other rows stay listed in the `registers` attribute with `usage_class: tracking`. Expect *Recent Usage Total* to drop by the ZeroHero window's usage (about 9% on a sample account). Statistics are corrected for the 31 days the portal still returns; older stored days keep their old values. Costs and credits are unchanged.
- **Controlled load is no longer part of general import:** rows with `chargeCategoryCode` `CONTROL` move from *Recent Usage Total* to the new controlled-load sensors ([#19](https://github.com/tinkerologie/ha-globird/issues/19)). Accounts without such rows are not affected.
- *Latest Day Usage*'s `latest_intervals` attribute counted each interval once per time-of-use row; the portal repeats the meter's full-day interval data on every row, so it is now counted once per meter register.
- Daily electricity and cost statistics (`…_usage_total`, `…_solar_export_total`, `…_cost_total`, `…_solar_export_credit_total`) no longer lose earlier usage when the portal's 31-day window moves past the oldest day ([#21](https://github.com/tinkerologie/ha-globird/issues/21)). Each import now continues the running total from the last stored row before the window, the same way the gas statistic does. If the recorder cannot be read, the import is skipped for that refresh. Days that were already wrong before this fix are not repaired.
- Gas meter index no longer shows up as gas usage in the Energy dashboard ([#16](https://github.com/tinkerologie/ha-globird/issues/16)):
  - The imported gas statistic `globird:<entry>_service_<id>_latest_gas_reading` now starts its sum at 0 at the first meter read. Before, the sum started at the meter index, and Home Assistant counted that whole index as gas used on the first read day. Each refresh imports the reads from the last 365 days again, so existing statistics are corrected on the next refresh. Once older reads leave that 365-day window, the sum continues from the last stored row before the window instead of starting again at 0. Stored rows that are already outside the window and still carry the old meter-index sum are rewritten once with the index removed.
  - *Latest Gas Reading* is now `unknown` until the first meter read is published, instead of `0.0`.
  - *Latest Gas Reading* no longer has a state class (it was `total_increasing`), so Home Assistant no longer records its own long-term statistics for it. A basic gas meter is read about every three months, and those statistics put each read's full jump into a single hour. **Action needed:** if your Energy dashboard uses the `sensor.…_latest_gas_reading_<mirn>` entity as the gas source, replace it with the `globird:…_latest_gas_reading` statistic (shown as *Latest Gas Reading (<mirn>)*). Home Assistant may then offer to fix the entity's old statistics under **Developer tools > Statistics**.

## [2026.10.2] - 2026-09-28

### Fixed
- Defaulted cumulative Energy Dashboard sensors (`Recent Usage Total`, `Recent Solar Export Total`, `Recent Cost Total`, `Recent Solar Export Credit Total`, `Billing Period Cost`, and `Latest Gas Reading`) to `0.0` when a newly onboarded service has no meter reads yet, ensuring Home Assistant's Recorder immediately registers their long-term statistics metadata without `statistics_not_defined` or `entity_unavailable` warnings.

## [2026.10.1] - 2026-09-28

### Fixed
- Relaxed `pydantic` requirement in `custom_components/globird/manifest.json` from `pydantic>=2.13.5` to `pydantic>=2.0.0` so it resolves cleanly against Home Assistant Core's pinned `package_constraints.txt` (`pydantic==2.13.4`) when loading the config flow.

## [2026.10.0] - 2026-09-28

### Added
- **Home Assistant Energy Dashboard Support**:
  - Enabled `SensorStateClass.TOTAL` and `last_reset` tracking across electricity and gas cost sensors (`Recent Cost Total`, `Latest Daily Cost`, `Billing Period Cost`) so they can be selected directly in the Energy Dashboard under *Use an entity tracking the total costs*.
  - Added `Recent Solar Export Credit Total` and `Latest Daily Solar Export Credit` (`AUD`, `SensorDeviceClass.MONETARY`, `SensorStateClass.TOTAL`) to track solar feed-in compensation in the Energy Dashboard under *Return to grid*.
  - Added `last_reset` support on `Latest Day Usage` and `Latest Day Solar Export` sensors so daily meter cycles reset cleanly at midnight in Home Assistant's Recorder.
  - Added full cost and readiness sensor coverage (`Recent Cost Total`, `Latest Daily Cost`, `Billing Period Cost`, `Expected Monthly Cost`, `Billing Period Days`, `Latest Data Date`, `Latest Data Status`) for Gas services in addition to Electricity services.
  - Added automatic Recorder long-term external statistics (`globird:*`) backfilling for daily electricity consumption (`kWh`), solar export (`kWh`), net cost (`AUD`), and solar export credits (`AUD`) alongside serial-aware gas meter statistics (`m³`).
- **Home Assistant Integration Quality Scale (Platinum)**:
  - Implemented `ConfigEntry.runtime_data` (`GloBirdConfigEntry`) for typed coordinator storage (`runtime-data`).
  - Added UI Re-authentication (`async_step_reauth` / `async_step_reauth_confirm`) and UI Reconfiguration (`async_step_reconfigure`) flows (`reauthentication-flow`, `reconfiguration-flow`).
  - Raised `ConfigEntryAuthFailed` with translatable exception keys on authentication failures (`test-before-setup`, `exception-translations`).
  - Added `icons.json` for entity and state icon translations (`icon-translations`), `EntityCategory.DIAGNOSTIC` classifications (`entity-category`), `PARALLEL_UPDATES = 0` (`parallel-updates`), and `quality_scale.yaml`.
- **Automated Release Workflow**:
  - Added `.github/workflows/release.yaml` to monitor `custom_components/globird/manifest.json` and `CHANGELOG.md`, validate Home Assistant versioning (`YYYY.M.P`), and automatically publish GitHub Releases with extracted changelog notes.

### Changed

- Update repository URLs and documentation references to tinkerologie organization.
- **Client Architecture & Pydantic v2**:
  - Renamed `custom_components/globird/api/api.py` to `custom_components/globird/api/client.py` and exposed `custom_components/globird/client.py`.
  - Upgraded `custom_components/globird/api/models.py` to use Pydantic v2 (`ConfigDict`, `@field_validator`, `Literal` types, `CostDailyTotalRow`, `BillingPeriodProjection`, and import/export cost breakdown fields).
  - Updated `./script/query-api` to automatically resolve `accountId` from `current_user` for account-scoped endpoints (`dashboard`, `balance`, `signup_info`) and handle newly transferring accounts without active meter data gracefully.

### Fixed
- Resolved all strict `pyright` type-checking diagnostics across `config_flow.py` and `sensor.py` (`0 errors, 0 warnings`).
