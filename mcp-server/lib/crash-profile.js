/**
 * CrashLens Crash Profile Builders — Node.js ES module port
 * Ported from app/modules/analysis/crash-profile.js
 */

import { COL, EPDO_WEIGHTS_DEFAULT } from './constants.js';
import { calcEPDO, isYes } from './epdo.js';

/**
 * Build simple crash profile for a location's crashes.
 * @param {Array} crashes - Array of crash row objects
 * @param {Object} [weights] - EPDO weights to use
 * @returns {Object}
 */
export function buildLocationCrashProfile(crashes, weights) {
  if (!crashes || crashes.length === 0) {
    return { total: 0, K: 0, A: 0, B: 0, C: 0, O: 0, anglePercent: 0, pedCount: 0, bikeCount: 0, epdo: 0 };
  }

  const profile = { total: crashes.length, K: 0, A: 0, B: 0, C: 0, O: 0 };
  let angleCount = 0, pedCount = 0, bikeCount = 0;

  for (const c of crashes) {
    const sev = (c[COL.SEVERITY] || '').charAt(0).toUpperCase();
    if (profile[sev] !== undefined) profile[sev]++;

    const collision = (c[COL.COLLISION] || '').toLowerCase();
    if (collision.includes('angle')) angleCount++;

    if (isYes(c[COL.PED])) pedCount++;
    if (isYes(c[COL.BIKE])) bikeCount++;
  }

  profile.anglePercent = (angleCount / crashes.length * 100).toFixed(1);
  profile.pedCount = pedCount;
  profile.bikeCount = bikeCount;
  profile.epdo = calcEPDO(profile, weights);

  return profile;
}

/**
 * Build detailed location profile with severity, collision, weather, light distributions.
 * @param {Array} crashes - Array of crash row objects
 * @param {Object} [weights] - EPDO weights to use
 * @returns {Object}
 */
export function buildDetailedLocationProfile(crashes, weights) {
  const w = weights || EPDO_WEIGHTS_DEFAULT;
  const profile = {
    total: crashes.length,
    severityDist: {},
    collisionTypes: {},
    contributingFactors: {},
    weatherDist: {},
    lightDist: {},
    pedInvolved: 0,
    bikeInvolved: 0,
    epdo: 0,
    extended: {
      surfaceConditions: {},
      roadAlignment: {},
      roadDefect: 0,
      relationToRoadway: {},
      firstHarmfulEventLoc: {},
      unrestrained: 0, drowsy: 0, drugRelated: 0, hitrun: 0,
      senior: 0, young: 0, motorcycle: 0, lgtruck: 0,
      guardrailRelated: 0, roadDeparture: 0,
      speedDiffs: [],
      peakPeriods: { am: 0, midday: 0, pm: 0, evening: 0, night: 0 },
      weekday: 0, weekend: 0,
      byYear: {},
      workZone: 0, schoolZone: 0
    }
  };

  for (const row of crashes) {
    const sev = row[COL.SEVERITY] || 'O';
    profile.severityDist[sev] = (profile.severityDist[sev] || 0) + 1;
    profile.epdo += w[sev] || 0;

    // Collision types
    const collType = (row[COL.COLLISION] || '').trim();
    if (collType && collType !== 'Unknown') {
      profile.collisionTypes[collType] = (profile.collisionTypes[collType] || 0) + 1;
    }

    // Contributing factors
    if (isYes(row[COL.ALCOHOL])) profile.contributingFactors['Alcohol'] = (profile.contributingFactors['Alcohol'] || 0) + 1;
    if (isYes(row[COL.SPEED])) profile.contributingFactors['Speed'] = (profile.contributingFactors['Speed'] || 0) + 1;
    if (isYes(row[COL.DISTRACTED])) profile.contributingFactors['Distracted'] = (profile.contributingFactors['Distracted'] || 0) + 1;
    if (isYes(row[COL.DROWSY])) profile.contributingFactors['Drowsy'] = (profile.contributingFactors['Drowsy'] || 0) + 1;
    if (row[COL.UNRESTRAINED] === 'Unbelted' || isYes(row[COL.UNRESTRAINED])) {
      profile.contributingFactors['Unrestrained'] = (profile.contributingFactors['Unrestrained'] || 0) + 1;
    }

    // Weather & Light
    const weather = (row[COL.WEATHER] || '').trim();
    if (weather && weather !== 'Unknown') profile.weatherDist[weather] = (profile.weatherDist[weather] || 0) + 1;
    const light = (row[COL.LIGHT] || '').trim();
    if (light && light !== 'Unknown') profile.lightDist[light] = (profile.lightDist[light] || 0) + 1;

    // Ped/Bike
    if (isYes(row[COL.PED])) profile.pedInvolved++;
    if (isYes(row[COL.BIKE])) profile.bikeInvolved++;

    // Extended data
    const surfaceCond = row[COL.SURFACE] || 'Unknown';
    profile.extended.surfaceConditions[surfaceCond] = (profile.extended.surfaceConditions[surfaceCond] || 0) + 1;

    const alignment = row[COL.ALIGNMENT] || 'Unknown';
    profile.extended.roadAlignment[alignment] = (profile.extended.roadAlignment[alignment] || 0) + 1;

    const defect = row[COL.ROAD_DEFECT] || '';
    if (defect && !defect.toLowerCase().includes('no defect')) profile.extended.roadDefect++;

    const relation = row[COL.RELATION_TO_ROAD] || 'Unknown';
    profile.extended.relationToRoadway[relation] = (profile.extended.relationToRoadway[relation] || 0) + 1;

    const harmfulLoc = row[COL.FIRST_HARMFUL_LOC] || 'Unknown';
    profile.extended.firstHarmfulEventLoc[harmfulLoc] = (profile.extended.firstHarmfulEventLoc[harmfulLoc] || 0) + 1;

    if (row[COL.UNRESTRAINED] === 'Yes' || row[COL.UNRESTRAINED] === 'Unbelted') profile.extended.unrestrained++;
    if (isYes(row[COL.DROWSY])) profile.extended.drowsy++;
    if (isYes(row[COL.DRUG])) profile.extended.drugRelated++;
    if (isYes(row[COL.HITRUN])) profile.extended.hitrun++;
    if (isYes(row[COL.SENIOR])) profile.extended.senior++;
    if (isYes(row[COL.YOUNG])) profile.extended.young++;
    if (isYes(row[COL.MOTORCYCLE])) profile.extended.motorcycle++;
    if (isYes(row[COL.LGTRUCK])) profile.extended.lgtruck++;
    if (isYes(row[COL.GUARDRAIL])) profile.extended.guardrailRelated++;

    const rdType = row[COL.ROAD_DEPARTURE] || '';
    if (rdType && rdType !== 'NOT_RD' && rdType.trim() !== '') profile.extended.roadDeparture++;

    const speedDiff = parseFloat(row[COL.MAX_SPEED_DIFF]);
    if (!isNaN(speedDiff) && speedDiff > 0) profile.extended.speedDiffs.push(speedDiff);

    // Temporal
    const time = row[COL.TIME] || '';
    if (time) {
      const hour = parseInt(time.substring(0, 2)) || parseInt(time.split(':')[0]) || 0;
      if (hour >= 6 && hour < 9) profile.extended.peakPeriods.am++;
      else if (hour >= 9 && hour < 15) profile.extended.peakPeriods.midday++;
      else if (hour >= 15 && hour < 19) profile.extended.peakPeriods.pm++;
      else if (hour >= 19 && hour < 22) profile.extended.peakPeriods.evening++;
      else profile.extended.peakPeriods.night++;
    }

    const dateVal = row[COL.DATE];
    if (dateVal) {
      const crashDate = new Date(Number(dateVal) || dateVal);
      if (!isNaN(crashDate.getTime())) {
        const dow = crashDate.getDay();
        if (dow === 0 || dow === 6) profile.extended.weekend++;
        else profile.extended.weekday++;
      }
    }

    const year = row[COL.YEAR];
    if (year) profile.extended.byYear[year] = (profile.extended.byYear[year] || 0) + 1;

    const workZone = row[COL.WORKZONE] || '';
    if (workZone === 'Yes' || workZone === '1' || workZone === '1. Yes') profile.extended.workZone++;
    const schoolZone = row[COL.SCHOOL] || '';
    if (schoolZone === 'Yes' || schoolZone === '1' || schoolZone === '1. Yes') profile.extended.schoolZone++;
  }

  // Average speed diff
  if (profile.extended.speedDiffs.length > 0) {
    profile.extended.avgSpeedDiff = +(profile.extended.speedDiffs.reduce((a, b) => a + b, 0) / profile.extended.speedDiffs.length).toFixed(1);
  } else {
    profile.extended.avgSpeedDiff = null;
  }

  return profile;
}
