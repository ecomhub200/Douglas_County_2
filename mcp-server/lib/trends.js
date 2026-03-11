/**
 * CrashLens Trend Analysis Library
 * Severity trends, temporal patterns, and year-over-year change analysis.
 */

import { COL } from './constants.js';

/**
 * Calculate severity trend by comparing recent vs older halves of data.
 */
export function calculateSeverityTrend(crashesByYear) {
  const years = Object.keys(crashesByYear).sort();
  if (years.length < 2) {
    return { trend: 0, direction: 'stable', olderAvg: 0, recentAvg: 0, years: years.length };
  }

  const mid = Math.floor(years.length / 2);
  const olderYears = years.slice(0, mid);
  const recentYears = years.slice(mid);

  const olderTotal = olderYears.reduce((sum, y) => sum + (crashesByYear[y] || 0), 0);
  const recentTotal = recentYears.reduce((sum, y) => sum + (crashesByYear[y] || 0), 0);

  const olderAvg = olderTotal / olderYears.length;
  const recentAvg = recentTotal / recentYears.length;

  const pctChange = olderAvg > 0 ? ((recentAvg - olderAvg) / olderAvg) * 100 : 0;

  let direction = 'stable';
  if (pctChange > 5) direction = 'worsening';
  else if (pctChange < -5) direction = 'improving';

  return {
    trend: +pctChange.toFixed(1),
    direction,
    olderAvg: +olderAvg.toFixed(1),
    recentAvg: +recentAvg.toFixed(1),
    olderPeriod: `${olderYears[0]}-${olderYears[olderYears.length - 1]}`,
    recentPeriod: `${recentYears[0]}-${recentYears[recentYears.length - 1]}`,
    years: years.length
  };
}

/**
 * Analyze temporal patterns: time-of-day, day-of-week, monthly distributions.
 */
export function analyzeTemporalPatterns(crashes) {
  const hourly = {};
  const dayOfWeek = { Sun: 0, Mon: 0, Tue: 0, Wed: 0, Thu: 0, Fri: 0, Sat: 0 };
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const monthly = {};
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  let weekday = 0, weekend = 0;

  for (let i = 0; i < 24; i++) hourly[i] = 0;
  for (let i = 1; i <= 12; i++) monthly[monthNames[i - 1]] = 0;

  for (const row of crashes) {
    // Hour
    const time = row[COL.TIME] || '';
    if (time) {
      const hour = parseInt(time.substring(0, 2)) || parseInt(time.split(':')[0]) || 0;
      if (hour >= 0 && hour < 24) hourly[hour]++;
    }

    // Day of week and month
    const dateVal = row[COL.DATE];
    if (dateVal) {
      const d = new Date(Number(dateVal) || dateVal);
      if (!isNaN(d.getTime())) {
        const dow = d.getDay();
        dayOfWeek[dayNames[dow]]++;
        if (dow === 0 || dow === 6) weekend++;
        else weekday++;

        const month = d.getMonth();
        monthly[monthNames[month]]++;
      }
    }
  }

  // Find peaks
  const peakHour = Object.entries(hourly).sort((a, b) => b[1] - a[1])[0];
  const peakDay = Object.entries(dayOfWeek).sort((a, b) => b[1] - a[1])[0];
  const peakMonth = Object.entries(monthly).sort((a, b) => b[1] - a[1])[0];

  return {
    hourly,
    dayOfWeek,
    monthly,
    peakHour: peakHour ? { hour: +peakHour[0], count: peakHour[1] } : null,
    peakDay: peakDay ? { day: peakDay[0], count: peakDay[1] } : null,
    peakMonth: peakMonth ? { month: peakMonth[0], count: peakMonth[1] } : null,
    weekdayVsWeekend: {
      weekday,
      weekend,
      weekdayRate: weekday / Math.max(5, 1),
      weekendRate: weekend / Math.max(2, 1)
    }
  };
}

/**
 * Calculate year-over-year change for each year transition.
 */
export function calculateYearOverYearChange(crashesByYear) {
  const years = Object.keys(crashesByYear).sort();
  if (years.length < 2) return [];

  const result = [];
  for (let i = 0; i < years.length; i++) {
    const year = years[i];
    const count = crashesByYear[year] || 0;

    if (i === 0) {
      result.push({ year, count, change: 0, pctChange: 0 });
    } else {
      const prevCount = crashesByYear[years[i - 1]] || 0;
      const change = count - prevCount;
      const pctChange = prevCount > 0 ? +((change / prevCount) * 100).toFixed(1) : 0;
      result.push({ year, count, change, pctChange });
    }
  }

  return result;
}
