"""Tenant-uploaded tabular files (ADR-018, ADR-019).

Upload, profiling, admin review and Parquet publication live here and in the
ingest worker; chat reads published contracts through `capability`. Metadata is
control-plane (`public.tabular_files`, `public.tabular_file_versions`) and is
read and written through platform sessions only.
"""
