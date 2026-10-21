# AirSent Flight Console — ASC v2

**Read [`ASC_V2_START_HERE.md`](ASC_V2_START_HERE.md) for the latest implementation, limitations, tests, deployment order and current 64-check catalog.**

This version restores the original compact ASC top strip and adds a CHECKS dropdown *on the existing `failsafe.html` page*. No ASC webpage, FC action or second MAVLink reader is introduced.

Prior v1 documents remain for context. In particular, the previous GUIDED velocity-command timeout change still requires SITL/HIL validation before flight.
