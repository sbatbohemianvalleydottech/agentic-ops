"""Price a Terraform plan, check it against deterministic rules, and gate on it.

No model is called here, on purpose. A price is arithmetic and a missing
autoscaling block is a fact about a document, so there is no judgement to
delegate. The other two artifacts in this repository route genuine judgement
through two raters and a blind judge; this one demonstrates the other half of
that discipline, which is knowing when not to call a model at all.

Everything it reads is a file. Catalogue and budget responses arrive as saved
output from commands the operator runs, so it needs no credential, makes no
network call while judging, and runs the same way on a laptop and in CI.
"""
