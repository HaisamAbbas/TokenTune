# Environment means deployment stage, not customer/tenant

`Environment` (prod/staging/dev) is scoped per Project and is *not* how we'd represent "which customer's deployment this is" if a client's AI application is run separately per customer. That's a distinct concept (a Tenant or Customer model) this platform doesn't build in V1. Conflating the two would make Environment's meaning ambiguous the moment a multi-tenant Project shows up, and would be a breaking schema change to unwind later. If multi-tenant support is needed, it should be added as a new concept, not folded into Environment.
