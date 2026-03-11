/**
 * CrashLens EPDO Calculation — Node.js ES module port
 * Ported from app/modules/core/epdo.js
 */

import { STATE_EPDO_WEIGHTS, EPDO_WEIGHTS_DEFAULT } from './constants.js';

export function getStateEPDOWeights(stateFips) {
  const padded = String(stateFips).padStart(2, '0');
  return STATE_EPDO_WEIGHTS[padded] || STATE_EPDO_WEIGHTS['_default'];
}

export function calcEPDO(severityObj, weights) {
  const w = weights || EPDO_WEIGHTS_DEFAULT;
  return (severityObj.K || 0) * w.K +
         (severityObj.A || 0) * w.A +
         (severityObj.B || 0) * w.B +
         (severityObj.C || 0) * w.C +
         (severityObj.O || 0) * w.O;
}

/** Helper: check if a field value means "Yes" */
export function isYes(val) {
  if (!val) return false;
  const s = String(val).trim();
  return s === 'Yes' || s === 'Y' || s === '1' || s === 'true';
}
