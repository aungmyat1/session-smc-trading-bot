"""Deprecated compatibility import for the neutral infrastructure adapter."""

from infrastructure.google_cloud import GCSArtifactAdapter, GoogleCloudError, KMSAsymmetricAdapter, parse_gs_uri

__all__ = ["GCSArtifactAdapter", "GoogleCloudError", "KMSAsymmetricAdapter", "parse_gs_uri"]
