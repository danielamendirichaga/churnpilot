"""Config loading & validation — reads churn.yaml (data source + column mapping).

Skeleton only. Implemented in build slice 1 (config + init + generate). The config is
what makes the tool domain-agnostic: the user declares their target/date/id/feature
columns here instead of hardcoding names. See WORKFLOW.md.
"""

from __future__ import annotations
