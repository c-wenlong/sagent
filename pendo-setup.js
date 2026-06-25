// Boot Pendo with an anonymous visitor. The SDK resolves the previous
// visitor from cookies/localStorage when available, otherwise it falls
// back to a new anonymous visitor.
pendo.initialize({
  visitor: {
    id: ''
  }
});

/**
 * Call this after sign-in, once the user's identity is available.
 *
 * @param {object} params
 * @param {string} params.userId       - Unique visitor identifier (SAGENT_USER_ID)
 * @param {string} params.startedAt    - ISO 8601 session start timestamp
 * @param {string|null} params.endedAt - ISO 8601 session end timestamp (null while active)
 * @param {boolean} params.active      - Whether the session is currently active
 * @param {string} params.tenantId     - HydraDB tenant identifier (account ID)
 * @param {string} params.subTenantId  - HydraDB sub-tenant identifier
 */
function pendoIdentify(params) {
  pendo.identify({
    visitor: {
      id: params.userId,
      startedAt: params.startedAt,
      endedAt: params.endedAt,
      active: params.active
    },
    account: {
      id: params.tenantId,
      subTenantId: params.subTenantId
    }
  });
}

/**
 * Call this on sign-out to reset Pendo to a fresh anonymous visitor.
 */
function pendoClearSession() {
  pendo.clearSession();
}
