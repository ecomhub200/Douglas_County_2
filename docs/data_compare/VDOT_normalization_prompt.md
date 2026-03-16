# CRASH LENS — Virginia Data Normalization Update

## Context
VDOT recently changed their CrashData_Basic dataset format on virginiaroads.org. The CRASH LENS frontend expects the OLD column names and labeled values. The new dataset uses numeric codes instead of descriptive labels. We need to update the data normalization layer so the new raw data gets transformed into the format the frontend already expects.

## Rules
- Do NOT change the frontend code. The frontend expects the OLD format exactly.
- Update ONLY the data pipeline / normalization step that transforms raw VDOT data before it reaches the frontend.
- The normalization must be idempotent — if someone feeds in old-format data, it should pass through unchanged.

## Column Rename Mapping (NEW → OLD)
These columns were renamed in the new dataset. Rename them back:

```
"Senior Driver?" → "Senior?"
"Young Driver?" → "Young?"
"Hitrun?" stays OR "Hit & Run?" → "Hitrun?"
"Lgtruck?" stays OR "Large Vehicle?" → "Lgtruck?"
"Unrestrained?" stays OR "UnBelted?" → "Unrestrained?"
"Route or Street Name" → this is a NEW column, keep it but don't break anything
"Local Case CD" → this is a NEW column, keep it
"LAT" → new column (keep, but frontend uses x/y)
"LON" → new column (keep, but frontend uses x/y)
```

## Boolean Value Mapping (NEW → OLD)
These columns changed from "Yes"/"No" to "1"/"0". Map them back:

```
Columns: Alcohol?, Animal Related?, Bike?, Distracted?, Drowsy?, Drug Related?,
         Guardrail Related?, Hitrun? (or Hit & Run?), Lgtruck? (or Large Vehicle?),
         Motorcycle?, Pedestrian?, Speed?, Senior?, Young?, Mainline?, Night?

Mapping: "1" → "Yes", "0" → "No"

Special case for Unrestrained? (or UnBelted?):
  "1" → "Unbelted", "0" → "Belted"
```

## Labeled Value Mappings (NEW numeric → OLD labeled)
VDOT stripped descriptive labels and left only numeric codes. Map them back:

### Collision Type
```
"0" → "Not Applicable"
"1" → "1. Rear End"
"2" → "2. Angle"
"3" → "3. Head On"
"4" → "4. Sideswipe - Same Direction"
"5" → "5. Sideswipe - Opposite Direction"
"6" → "6. Fixed Object in Road"
"7" → "7. Train"
"8" → "8. Non-Collision"
"9" → "9. Fixed Object - Off Road"
"10" → "10. Deer"
"11" → "11. Other Animal"
"12" → "12. Ped"
"13" → "13. Bicyclist"
"14" → "14. Motorcyclist"
"15" → "15. Backed Into"
"16" → "16. Other"
"99" → "Not Provided"
```

### Weather Condition
```
"1" → "1. No Adverse Condition (Clear/Cloudy)"
"3" → "3. Fog"
"4" → "4. Mist"
"5" → "5. Rain"
"6" → "6. Snow"
"7" → "7. Sleet/Hail"
"8" → "8. Smoke/Dust"
"9" → "9. Other"
"10" → "10. Blowing Sand, Soil, Dirt, or Snow"
"11" → "11. Severe Crosswinds"
"99" → "Not Applicable"
```

### Light Condition
```
"1" → "1. Dawn"
"2" → "2. Daylight"
"3" → "3. Dusk"
"4" → "4. Darkness - Road Lighted"
"5" → "5. Darkness - Road Not Lighted"
"6" → "6. Darkness - Unknown Road Lighting"
"7" → "7. Unknown"
"99" → "Not Applicable"
```

### Roadway Surface Condition
```
"0" → "Not Applicable"
"1" → "1. Dry"
"2" → "2. Wet"
"3" → "3. Snowy"
"4" → "4. Icy"
"5" → "5. Muddy"
"6" → "6. Oil/Other Fluids"
"7" → "7. Other"
"8" → "8. Natural Debris"
"9" → "9. Water (Standing, Moving)"
"10" → "10. Slush"
"11" → "11. Sand, Dirt, Gravel"
"99" → "Not Provided"
```

### Relation To Roadway
```
"0" → "Not Applicable"
"1" → "1. Main-Line Roadway"
"2" → "2. Acceleration/Deceleration Lanes"
"3" → "3. Gore Area (b/w Ramp and Highway Edgelines)"
"4" → "4. Collector/Distributor Road"
"5" → "5. On Entrance/Exit Ramp"
"6" → "6. Intersection at end of Ramp"
"7" → "7. Other location not listed above within an interchange area (median, shoulder , roadside)"
"8" → "8. Non-Intersection"
"9" → "9. Within Intersection"
"10" → "10. Intersection Related - Within 150 Feet"
"11" → "11. Intersection Related - Outside 150 Feet"
"12" → "12. Crossover Related"
"13" → "13. Driveway, Alley-Access - Related"
"14" → "14. Railway Grade Crossing"
"15" → "15. Other Crossing (Crossing for Bikes, School, etc.)"
"99" → "Not Provided"
```

### Roadway Alignment
```
"1" → "1. Straight - Level"
"2" → "2. Curve - Level"
"3" → "3. Grade - Straight"
"4" → "4. Grade - Curve"
"5" → "5. Hillcrest - Straight"
"6" → "6. Hillcrest - Curve"
"7" → "7. Dip - Straight"
"8" → "8. Dip - Curve"
"9" → "9. Other"
"10" → "10. On/Off Ramp"
"99" → "Not Applicable"  (new value not in old set)
```

### Roadway Surface Type
```
"1" → "1. Concrete"
"2" → "2. Blacktop, Asphalt, Bituminous"
"3" → "3. Brick or Block"
"4" → "4. Slag, Gravel, Stone"
"5" → "5. Dirt"
"6" → "6. Other"
"99" → "Not Applicable"
```

### Roadway Defect
```
"0" → "Not Applicable"
"1" → "1. No Defects"
"2" → "2. Holes, Ruts, Bumps"
"3" → "3. Soft or Low Shoulder"
"4" → "4. Under Repair"
"5" → "5. Loose Material"
"6" → "6. Restricted Width"
"7" → "7. Slick Pavement"
"8" → "8. Roadway Obstructed"
"9" → "9. Other"
"10" → "10. Edge Pavement Drop Off"
"99" → "Not Provided"
```

### Roadway Description
```
"0" → "Not Applicable"
"1" → "1. Two-Way, Not Divided"
"2" → "2. Two-Way, Divided, Unprotected Median"
"3" → "3. Two-Way, Divided, Positive Median Barrier"
"4" → "4. One-Way, Not Divided"
"5" → "5. Unknown"
"99" → "Not Provided"
```

### Intersection Type
```
"0" → "Not Applicable"
"1" → "1. Not at Intersection"
"2" → "2. Two Approaches"
"3" → "3. Three Approaches"
"4" → "4. Four Approaches"
"5" → "5. Five-Point, or More"
"6" → "6. Roundabout"
"99" → "Not Provided"
```

### Traffic Control Type
```
"1" → "1. No Traffic Control"
"2" → "2. Officer or Flagger"
"3" → "3. Traffic Signal"
"4" → "4. Stop Sign"
"5" → "5. Slow or Warning Sign"
"6" → "6. Traffic Lanes Marked"
"7" → "7. No Passing Lines"
"8" → "8. Yield Sign"
"9" → "9. One Way Road or Street"
"10" → "10. Railroad Crossing With Markings and Signs"
"11" → "11. Railroad Crossing With Signals"
"12" → "12. Railroad Crossing With Gate and Signals"
"13" → "13. Other"
"14" → "14. Ped Crosswalk"
"15" → "15. Reduced Speed - School Zone"
"16" → "16. Reduced Speed - Work Zone"
"17" → "17. Highway Safety Corridor"
"99" → "Not Applicable"
```

### Traffic Control Status
```
"0" → "Not Applicable"
"1" → "1. Yes - Working"
"2" → "2. Yes - Working and Obscured"
"3" → "3. Yes - Not Working"
"4" → "4. Yes - Not Working and Obscured"
"5" → "5. Yes - Missing"
"6" → "6. No Traffic Control Device Present"
"99" → "Not Provided"
```

### Work Zone Related
```
"0" → "Not Applicable"
"1" → "1. Yes"
"2" → "2. No"
"99" → "Not Provided"
```

### Work Zone Location
```
"0" → (empty/null — no work zone)
"1" → "1. Advance Warning Area"
"2" → "2. Transition Area"
"3" → "3. Activity Area"
"4" → "4. Termination Area"
"99" → (empty/null)
```

### Work Zone Type
```
"0" → (empty/null)
"1" → "1. Lane Closure"
"2" → "2. Lane Shift/Crossover"
"3" → "3. Work on Shoulder or Median"
"4" → "4. Intermittent or Moving Work"
"5" → "5. Other"
"99" → (empty/null)
```

### School Zone
```
"0" → "Not Applicable"
"1" → "1. Yes"
"2" → "2. Yes - With School Activity"
"3" → "3. No"
"99" → "Not Provided"
```

### First Harmful Event
```
"1" → "1. Bank Or Ledge"
"2" → "2. Trees"
"3" → "3. Utility Pole"
"4" → "4. Fence Or Post"
"5" → "5. Guard Rail"
"6" → "6. Parked Vehicle"
"7" → "7. Tunnel, Bridge, Underpass, Culvert, etc."
"8" → "8. Sign, Traffic Signal"
"9" → "9. Impact Cushioning Device"
"10" → "10. Other"
"11" → "11. Jersey Wall"
"12" → "12. Building/Structure"
"13" → "13. Curb"
"14" → "14. Ditch"
"15" → "15. Other Fixed Object"
"16" → "16. Other Traffic Barrier"
"17" → "17. Traffic Sign Support"
"18" → "18. Mailbox"
"19" → "19. Ped"
"20" → "20. Motor Vehicle In Transport"
"21" → "21. Train"
"22" → "22. Bicycle"
"23" → "23. Animal"
"24" → "24. Work Zone Maintenance Equipment"
"25" → "25. Other Movable Object"
"26" → "26. Unknown Movable Object"
"27" → "27. Other"
"28" → "28. Ran Off Road"
"29" → "29. Jack Knife"
"30" → "30. Overturn (Rollover)"
"31" → "31. Downhill Runaway"
"32" → "32. Cargo Loss or Shift"
"33" → "33. Explosion or Fire"
"34" → "34. Separation of Units"
"35" → "35. Cross Median"
"36" → "36. Cross Centerline"
"37" → "37. Equipment Failure (Tire, etc)"
"38" → "38. Immersion"
"39" → "39. Fell/Jumped From Vehicle"
"40" → "40. Thrown or Falling Object"
"41" → "41. Non-Collision Unknown"
"42" → "42. Other Non-Collision"
```

### First Harmful Event Loc
```
"0" → "Not Applicable"
"1" → "1. On Roadway"
"2" → "2. Shoulder"
"3" → "3. Median"
"4" → "4. Roadside"
"5" → "5. Gore"
"6" → "6. Separator"
"7" → "7. In Parking Lane or Zone"
"8" → "8. Off Roadway, Location Unknown"
"9" → "9. Outside Right-of-Way"
"99" → "Not Provided"
```

### RoadDeparture Type
```
"0" → "NOT_RD"
"1" → "RD_LEFT"
"2" → "RD_RIGHT"
"3" → "RD_UNKNOWN"
```

### Intersection Analysis
```
"0" → "Not Intersection"
"1" → "Urban Intersection"
"2" → "VDOT Intersection"
```

### VDOT District
```
"1" → "1. Bristol"
"2" → "2. Salem"
"3" → "3. Lynchburg"
"4" → "4. Richmond"
"5" → "5. Hampton Roads"
"6" → "6. Fredericksburg"
"7" → "7. Culpeper"
"8" → "8. Staunton"
"9" → "9. Northern Virginia"
```

### Physical Juris Name
The old dataset had format "043. Henrico County". The new dataset has just the numeric code "43".
Build a lookup from Juris Code → full labeled name using this reference:
```
"0" → "000. Arlington County"
"1" → "001. Accomack County"
"2" → "002. Albemarle County"
"3" → "003. Alleghany County"
... (use the complete list from the old dataset's Physical Juris Name column)
```
The Juris Code column values are identical between old and new. Use Juris Code to rebuild Physical Juris Name.

### Functional Class
```
"INT" → "1-Interstate (A,1)"
"OFE" → "2-Principal Arterial - Other Freeways and Expressways (B)"
"OPA" → "3-Principal Arterial - Other (E,2)"
"MIA" → "4-Minor Arterial (H,3)"
"MAC" → "5-Major Collector (I,4)"
"MIC" → "6-Minor Collector (5)"
"LOC" → "7-Local (J,6)"
```

### Facility Type
```
"OUD" → "1-One-Way Undivided"
"OWD" → "2-One-Way Divided"
"TUD" → "3-Two-Way Undivided"
"TWD" → "4-Two-Way Divided"
"REX" → "5-Reversible Exclusively (e.g. 395R)"
```

### Area Type
```
"0" → "Rural"
"1" → "Urban"
```

### SYSTEM
```
"1" → "NonVDOT primary"
"2" → "NonVDOT secondary"
"3" → "VDOT Interstate"
"4" → "VDOT Primary"
"5" → "VDOT Secondary"
```

### Ownership
```
"1" → "1. State Hwy Agency"
"2" → "2. County Hwy Agency"
"3" → "3. City or Town Hwy Agency"
"4" → "4. Federal Roads"
"5" → "5. Toll Roads Maintained by Others"
"6" → "6. Private/Unknown Roads"
```

### Planning District
```
"1" → "Accomack-Northampton"
"2" → "George Washington Regional"
"3" → "Northern Neck"
"4" → "Middle Peninsula"
"5" → "Richmond Regional"
"6" → "Crater"
"7" → "Southside"
"8" → "West Piedmont"
"9" → "Region 2000"
"10" → "Central Shenandoah"
"11" → "Roanoke Valley-Alleghany"
"12" → "New River Valley"
"13" → "Cumberland Plateau"
"14" → "Lenowisco"
"15" → "Hampton Roads"
"16" → "Thomas Jefferson"
"17" → "Northern Shenandoah Valley"
"18" → "Rappahannock - Rapidan"
"19" → "Northern Virginia"
"22" → "Mount Rogers"
"23" → "Culpeper" (verify — may be missing from old set)
"5,12" → "Richmond Regional" (or split — verify)
"15,19" → "Hampton Roads" (or "Crater, Hampton Roads")
"18,23" → "Rappahannock - Rapidan"
"19,23" → "Northern Virginia"
```

## Implementation Notes
1. Apply normalization AFTER downloading raw CSV, BEFORE storing in R2 or serving to frontend
2. Make the mapping tables configurable (JSON file) so future VDOT changes are easy to update
3. Detect which format the data is in (check if "Collision Type" contains labels like "1. Rear End" or just "1") and only normalize if needed
4. Log any unmapped values so we catch new codes VDOT adds
5. Preserve all NEW columns (Local Case CD, Route or Street Name, LAT, LON) — the frontend will ignore them but they're useful for analysis
