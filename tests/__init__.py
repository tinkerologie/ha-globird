"""Tests for the GloBird integration."""

from .fixtures.deprecations import install_deprecation_report_handler

# Before any test module imports the integration, so import-time reports are
# caught too.
install_deprecation_report_handler()
