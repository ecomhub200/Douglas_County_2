/**
 * CrashLens Signal Warrant Math — Node.js ES module port
 * Ported from app/modules/warrants/signal.js
 */

/**
 * Interpolate minor street threshold from MUTCD curve given major street volume.
 */
export function interpolateThreshold(curve, majorVol) {
  if (majorVol <= curve[0].major) return curve[0].minor;
  if (majorVol >= curve[curve.length - 1].major) return curve[curve.length - 1].minor;

  for (let i = 0; i < curve.length - 1; i++) {
    if (majorVol >= curve[i].major && majorVol <= curve[i + 1].major) {
      const ratio = (majorVol - curve[i].major) / (curve[i + 1].major - curve[i].major);
      return Math.round(curve[i].minor + ratio * (curve[i + 1].minor - curve[i].minor));
    }
  }

  return curve[curve.length - 1].minor;
}

/**
 * Calculate street volumes from hourly TMC data.
 */
export function calculateStreetVolumes(hourlyData, majorDirection, approaches) {
  const isMajorEW = majorDirection === 'EW';
  let majorTotal = 0, minorTotal = 0;

  for (const approach of approaches) {
    const data = hourlyData[approach] || {};
    const sumMovements = (data.L || 0) + (data.T || 0) + (data.R || 0) + (data.U || 0);
    const approachTotal = sumMovements > 0 ? sumMovements : (data.total || 0);

    if ((isMajorEW && (approach === 'EB' || approach === 'WB')) ||
        (!isMajorEW && (approach === 'NB' || approach === 'SB'))) {
      majorTotal += approachTotal;
    } else {
      minorTotal += approachTotal;
    }
  }

  return { major: majorTotal, minor: minorTotal };
}

/**
 * Get lane configuration string.
 */
export function getLaneConfig(majorLanes, minorLanes) {
  const major = majorLanes >= 2 ? '2' : '1';
  const minor = minorLanes >= 2 ? '2' : '1';
  return major + 'x' + minor;
}

/**
 * Get reduction factor based on population and speed limit.
 */
export function getReductionFactor(config) {
  if (config.apply70pct) return 'p70';
  if (config.communityPop < 10000 || config.speedLimit > 40) return 'p70';
  if (config.communityPop < 50000) return 'p80';
  return 'p100';
}

// MUTCD Warrant 1 threshold curves (Table 4C-1)
export const WARRANT_1_CURVES = {
  '1x1': {
    p100: [
      { major: 300, minor: 200 }, { major: 350, minor: 175 }, { major: 400, minor: 150 },
      { major: 500, minor: 130 }, { major: 600, minor: 115 }, { major: 700, minor: 100 }
    ],
    p80: [
      { major: 240, minor: 160 }, { major: 280, minor: 140 }, { major: 320, minor: 120 },
      { major: 400, minor: 104 }, { major: 480, minor: 92 }, { major: 560, minor: 80 }
    ],
    p70: [
      { major: 210, minor: 140 }, { major: 245, minor: 123 }, { major: 280, minor: 105 },
      { major: 350, minor: 91 }, { major: 420, minor: 81 }, { major: 490, minor: 70 }
    ]
  },
  '2x1': {
    p100: [
      { major: 400, minor: 200 }, { major: 450, minor: 175 }, { major: 500, minor: 150 },
      { major: 600, minor: 130 }, { major: 700, minor: 115 }, { major: 800, minor: 100 }
    ],
    p80: [
      { major: 320, minor: 160 }, { major: 360, minor: 140 }, { major: 400, minor: 120 },
      { major: 480, minor: 104 }, { major: 560, minor: 92 }, { major: 640, minor: 80 }
    ],
    p70: [
      { major: 280, minor: 140 }, { major: 315, minor: 123 }, { major: 350, minor: 105 },
      { major: 420, minor: 91 }, { major: 490, minor: 81 }, { major: 560, minor: 70 }
    ]
  }
};
